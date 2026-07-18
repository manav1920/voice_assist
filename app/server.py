"""
Manasvi AI - Web Server
========================
Wraps the existing CLI pipeline (Recorder -> Whisper -> Gemini ->
TextPreprocessor -> XTTS) in a FastAPI server so the browser frontend
can talk to it over HTTP instead of the terminal.

Run from the project root (the folder containing this project's
requirements.txt), e.g.:

    uvicorn app.server:app --host 0.0.0.0 --port 8000

Then open http://localhost:8000 in your browser.
"""

import email
import os
import time
import uuid
import logging
import traceback

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Console-only logging (never returned in any API response) so
# MemoryExtractor's "Memory Created / Updated / Ignored" trail is
# visible to whoever is running the server, per the spec.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.whisper_service import WhisperService
from app.gemini_service import GeminiService
from app.services.conversation_service import ConversationService
from app.services.memory_manager import MemoryManager
from app.services.memory_extractor import MemoryExtractor
from app.services.communication_manager import CommunicationManager
from app.services.prompt_builder import PromptBuilder
from app.text_preprocessor import TextPreprocessor
from app.xtts_service import XTTSService
from app.audio_processor import AudioProcessor
from app.auth import get_current_user, get_current_claims, db
from app.config import SUPABASE_URL, SUPABASE_ANON_KEY

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORDINGS_DIR = os.path.join(BASE_DIR, "recordings")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
STATIC_DIR = os.path.join(BASE_DIR, "static")
SPEAKER_WAV = os.path.join(BASE_DIR, "samples", "voice.wav")

os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------
# App + models (loaded once at startup, shared across requests)
# ---------------------------------------------------------------------

app = FastAPI(title="Manasvi AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("\nLoading Manasvi pipeline (this can take a while on first run)...\n")

whisper = WhisperService()
gemini = GeminiService()
preprocessor = TextPreprocessor()
xtts = XTTSService()
audio_processor = AudioProcessor()

# Conversations and messages are persisted in MySQL (see
# voice_assist_sql.sql for the `conversations` / `messages` tables),
# so - unlike the old in-memory ConversationManager - history now
# survives server restarts and works the same across every request,
# not just within one process's lifetime.
conversation_service = ConversationService(db)
memory_manager = MemoryManager(db)
memory_extractor = MemoryExtractor(db, gemini.client, gemini.model)
communication_manager = CommunicationManager(db)
prompt_builder = PromptBuilder()


def _resolve_conversation(conversation_id: int | None, user_id: int) -> dict:
    """
    Returns the conversation the frontend meant to talk to. If it
    didn't send one (or sent one that doesn't belong to this user),
    falls back to the user's active conversation, creating one if
    they have none at all.
    """

    if conversation_id is not None:
        conversation = conversation_service.get_conversation(conversation_id, user_id)
        if conversation is not None:
            return conversation

    return conversation_service.get_or_create_active_conversation(user_id)


print("\nManasvi is ready.\n")


# ---------------------------------------------------------------------
# API
# ---------------------------------------------------------------------

@app.post("/api/converse")
async def converse(
    audio: UploadFile = File(...),
    conversation_id: int | None = Form(None),
    user: dict = Depends(get_current_user),
):
    """
    Accepts a recorded audio clip from the browser, runs it through the
    full pipeline, and returns the transcript, the reply text, per-stage
    timings, a URL to the generated cloned-voice audio, and the
    conversation_id / title the frontend should be tracking.

    Requires a valid Supabase-issued Bearer token (see app/auth.py).

    Conversation flow:
        User audio -> Whisper (transcript)
        -> save user message
        -> Conversation History (ConversationService)
           + Relevant Memories (MemoryManager)
           -> Prompt Builder -> Gemini
        -> save assistant message
        -> (first turn only) auto-generate a conversation title
    """

    conversation = _resolve_conversation(conversation_id, user["id"])

    request_id = uuid.uuid4().hex[:8]
    # Browsers record via MediaRecorder as webm/opus; keep the real
    # extension so ffmpeg (used internally by Whisper) decodes it correctly.
    input_path = os.path.join(RECORDINGS_DIR, f"input_{request_id}.webm")
    output_filename = f"response_{request_id}.wav"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    timings = {}
    total_start = time.perf_counter()

    try:
        # -----------------------------------------------------------
        # Save uploaded audio
        # -----------------------------------------------------------
        raw_bytes = await audio.read()
        with open(input_path, "wb") as f:
            f.write(raw_bytes)

        # -----------------------------------------------------------
        # Whisper
        # -----------------------------------------------------------
        start = time.perf_counter()
        user_text = whisper.transcribe(input_path)
        timings["whisper"] = round(time.perf_counter() - start, 2)

        if not user_text.strip():
            raise HTTPException(status_code=422, detail="No speech detected.")

        # -----------------------------------------------------------
        # Save the user message immediately - it must be persisted
        # even if Gemini or a later stage fails.
        # -----------------------------------------------------------
        conversation_service.save_user_message(conversation["id"], user["id"], user_text)

        is_first_turn = conversation_service.needs_title(conversation)

        # -----------------------------------------------------------
        # Memory Extractor - decides whether this message contains a
        # durable fact worth remembering, and stores/updates it before
        # memory is retrieved for the prompt below (so a correction
        # like "actually my favorite color is black" is reflected in
        # the very same reply). Never allowed to break the request.
        # -----------------------------------------------------------
        start = time.perf_counter()
        try:
            memory_extractor.process_message(user["id"], user_text)
        except Exception:
            traceback.print_exc()
        timings["memory_extraction"] = round(time.perf_counter() - start, 2)

        # -----------------------------------------------------------
        # Gemini
        # -----------------------------------------------------------
        start = time.perf_counter()

        history = conversation_service.get_formatted_history(
            conversation["id"], exclude_last=True
        )
        memory_context = memory_manager.get_relevant_memory_context(user["id"], user_text)

        communication_style = communication_manager.detect_conversation_style(
            history, user_text
        )
        communication_instructions = communication_manager.build_communication_instructions(
            communication_style
        )

        prompt = prompt_builder.build(
            system_prompt=gemini.system_prompt,
            user_message=user_text,
            history=history,
            memory_context=memory_context,
            communication_instructions=communication_instructions,
        )

        reply_text = gemini.generate_reply(prompt)
        timings["gemini"] = round(time.perf_counter() - start, 2)

        # Never allowed to break the request - a failure here should
        # cost us a gradual preference update, not the user's reply.
        try:
            communication_manager.update_preferred_language_memory(
                user["id"], communication_style
            )
        except Exception:
            traceback.print_exc()

        conversation_service.save_assistant_message(
            conversation["id"], user["id"], reply_text, model=gemini.model
        )

        # -----------------------------------------------------------
        # Auto-title: only on the conversation's first exchange.
        # -----------------------------------------------------------
        conversation_title = conversation["title"]
        if is_first_turn:
            conversation_title = ConversationService.clean_title(
                gemini.generate_title(user_text)
            )
            conversation_service.rename_conversation(
                conversation["id"], user["id"], conversation_title
            )

        # -----------------------------------------------------------
        # Text Preprocessor
        # -----------------------------------------------------------
        start = time.perf_counter()
        processed_text = preprocessor.preprocess(reply_text)
        timings["preprocess"] = round(time.perf_counter() - start, 2)

        # -----------------------------------------------------------
        # XTTS
        # -----------------------------------------------------------
        start = time.perf_counter()
        xtts.text_to_speech(
            text=processed_text,
            speaker_wav=SPEAKER_WAV,
            output_file=output_path,
            language="en",
        )
        timings["xtts"] = round(time.perf_counter() - start, 2)

        timings["total"] = round(time.perf_counter() - total_start, 2)

        return {
            "user_text": user_text,
            "reply_text": reply_text,
            "audio_url": f"/audio/{output_filename}",
            "timings": timings,
            "conversation_id": conversation["id"],
            "conversation_title": conversation_title,
        }

    except HTTPException:
        raise

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)

    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Audio not found.")

    return FileResponse(path, media_type="audio/wav")


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------

class SyncRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None


@app.get("/api/public-config")
async def public_config():
    """
    Values here are safe to expose to the browser - the Supabase
    anon key is designed to be public (it has no special privileges
    on its own). The JWT secret is NEVER exposed; it only ever lives
    server-side in app/auth.py.
    """
    return {
        "supabase_url": SUPABASE_URL,
        "supabase_anon_key": SUPABASE_ANON_KEY,
    }


@app.post("/api/auth/sync")
async def sync_user(payload: SyncRequest, claims: dict = Depends(get_current_claims)):
    """
    Called by the frontend right after a successful Supabase login or
    signup-then-verify. Finds or creates the matching row in MySQL
    and stamps last_login.
    """

    supabase_user_id = claims.get("sub")
    email = claims.get("email")
    user_metadata = claims.get("user_metadata", {}) or {}

    print("\n========== GOOGLE USER METADATA ==========")
    print(user_metadata)
    print("=========================================\n")

    # First try to find by Supabase ID
    user = db.get_user_by_supabase_id(supabase_user_id)

    if user is None:

        # If not found, try by email
        existing_user = db.get_user_by_email(email)

        if existing_user:
            print("Existing email found. Linking Supabase account...")

            user = db.update_supabase_user_id(
                existing_user["id"],
                supabase_user_id,
            )

        else:
            print("Creating new user...")

            first_name = (
                payload.first_name
                or user_metadata.get("first_name")
                or user_metadata.get("given_name")
                or user_metadata.get("name")
                or user_metadata.get("full_name")
                or "GoogleUser"
            )

            last_name = (
                payload.last_name
                or user_metadata.get("last_name")
                or user_metadata.get("family_name")
                or ""
            )

            user = db.create_user(
                supabase_user_id=supabase_user_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone_number=payload.phone_number,
            )

    return {
        "success": True,
        "user": user,
    }


@app.get("/api/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """
    Returns the MySQL user row, enriched with `preferred_name` - the
    name the user gave during onboarding ("What should I call you?"),
    which is intentionally stored in `memory` (not `users`) and is
    separate from `first_name` (the Google/signup identity name, which
    is never overwritten). Callers that need to greet the user or
    decide Developer Experience eligibility should use
    `preferred_name`, not `first_name`.
    """
    memory = db.get_memory(user["id"])

    preferred_name = next(
        (
            row["value"] for row in memory
            if row["category"] == "identity" and row["key_name"] == "preferred_name"
        ),
        None,
    )

    return {"user": {**user, "preferred_name": preferred_name}}


# ---------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------
# One-time questionnaire after signup. Answers are stored as individual
# rows in the existing `memory` table (never in `users`), keyed by
# (user_id, key_name). onboarding_completed lives on `users` purely as
# a flag for "has this person finished the flow at all".

class MemoryEntry(BaseModel):
    category: str
    key_name: str
    value: str


class OnboardingSaveRequest(BaseModel):
    entries: list[MemoryEntry]


@app.post("/api/onboarding/save")
async def save_onboarding_step(
    payload: OnboardingSaveRequest,
    user: dict = Depends(get_current_user),
):
    """
    Called after every step of the onboarding wizard (autosave).
    Upserts each answer as one row in `memory`.
    """
    db.save_memory_bulk(
        user["id"],
        [entry.model_dump() for entry in payload.entries],
    )
    return {"status": "saved"}


@app.get("/api/onboarding/memory")
async def get_onboarding_memory(user: dict = Depends(get_current_user)):
    """
    Lets the wizard resume with previously autosaved answers if the
    user left partway through (e.g. closed the tab on step 3).
    """
    return {"memory": db.get_memory(user["id"])}


@app.post("/api/onboarding/complete")
async def complete_onboarding(user: dict = Depends(get_current_user)):
    """
    Marks onboarding as done. After this, /api/auth/me and
    /api/auth/sync will report onboarding_completed = true, and the
    frontend won't show the wizard again.
    """
    db.mark_onboarding_completed(user["id"])
    return {"status": "completed"}


# ---------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------
# Search-ready: list_conversations() is a single flat query today.
# Adding search later just means adding an optional `q` param here
# and a WHERE clause in ConversationService/DatabaseManager - nothing
# about this shape needs to change.

class RenameConversationRequest(BaseModel):
    title: str


@app.get("/api/conversations/active")
async def get_active_conversation(user: dict = Depends(get_current_user)):
    """
    Called once on login. Determines the conversation the frontend
    should treat as active, creating one automatically if the user
    has none yet.
    """
    conversation = conversation_service.get_or_create_active_conversation(user["id"])
    return {"conversation": conversation}


@app.get("/api/conversations")
async def list_conversations(user: dict = Depends(get_current_user)):
    """
    Flat, newest-first list for the sidebar. Grouping into
    Today / Yesterday / Previous 7 Days / Older is done client-side
    from each conversation's updated_at.
    """
    return {"conversations": conversation_service.list_conversations(user["id"])}


@app.post("/api/conversations")
async def create_conversation(user: dict = Depends(get_current_user)):
    """
    "New Conversation" button. Creates a new conversation and returns
    it as the new active one - previous conversations are untouched.
    """
    conversation = conversation_service.create_conversation(user["id"])
    return {"conversation": conversation}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation_messages(conversation_id: int, user: dict = Depends(get_current_user)):
    """
    Loads one conversation's full message history, ordered oldest to
    newest, for the frontend to render exactly like ChatGPT.
    """
    conversation = conversation_service.get_conversation(conversation_id, user["id"])

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = conversation_service.get_messages(conversation_id)
    return {"conversation": conversation, "messages": messages}


@app.patch("/api/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: int,
    payload: RenameConversationRequest,
    user: dict = Depends(get_current_user),
):
    updated = conversation_service.rename_conversation(conversation_id, user["id"], payload.title)

    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    conversation = conversation_service.get_conversation(conversation_id, user["id"])
    return {"conversation": conversation}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, user: dict = Depends(get_current_user)):
    deleted = conversation_service.delete_conversation(conversation_id, user["id"])

    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    return {"status": "deleted"}


# ---------------------------------------------------------------------
# Frontend (static files)
# ---------------------------------------------------------------------

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
