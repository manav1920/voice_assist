"""
MemoryExtractor
=================
Automatic memory extraction + updating. This service is intentionally
independent from GeminiService and MemoryManager:

    - GeminiService only knows how to turn a finished prompt into a
      reply (or a title). It has no idea memory extraction exists.
    - MemoryManager only knows how to *read* memory for prompts.
    - MemoryExtractor is the only thing that *writes* memory outside
      of onboarding, and the only thing that asks "should this
      message become a long-term memory?"

It reuses the existing `memory` table and the existing
`DatabaseManager.save_memory_bulk()` upsert (UNIQUE(user_id, key_name)
already prevents duplicates - "update if it exists" comes for free,
no schema changes needed).

Every public entry point swallows its own errors: a bad Gemini
response, malformed JSON, or an API failure should never break the
conversation the user is actually waiting on.
"""

import json
import logging
import re

from app.database import DatabaseManager

logger = logging.getLogger("manasvi.memory_extractor")


EXTRACTION_INSTRUCTIONS = """You are the memory-extraction module for a personal AI assistant.
Decide whether the user's latest message contains a durable, personal fact worth remembering long-term.

REMEMBER things like: stated preferences, birthday, occupation/study, career goals, hobbies, pets, skills being learned, relationships, location, or explicit corrections to something already known about them.

DO NOT remember: small talk, one-off events, feelings about "today", questions, requests, or anything that won't still be true or useful in a month.

Examples:
- "My birthday is April 20." -> remember (memory_key: birthday)
- "I started learning Rust." -> remember (memory_key: learning_language, value: Rust)
- "My favorite color is Black." -> remember (memory_key: favorite_color, value: Black)
- "I study at ABESIT." -> remember (memory_key: institution, value: ABESIT)
- "I want to become an AI Engineer." -> remember (memory_key: career_goal, value: AI Engineer)
- "I adopted a Golden Retriever." -> remember (memory_key: pet, value: Golden Retriever)
- "I had pizza today." -> do not remember
- "It rained today." -> do not remember
- "I watched a movie." -> do not remember

The user already has some memories stored (listed below, possibly empty). If the new message updates or corrects one of these, reuse that EXACT memory_key so it overwrites the old value instead of creating a duplicate under a different name.

Existing memories:
{existing_memories}

Respond with ONLY valid JSON, no markdown fences, no commentary, matching exactly this shape:
{{
  "remember": true or false,
  "memory_key": "snake_case_key or null",
  "memory_value": "value or null",
  "category": "one short category label or null",
  "reason": "one short sentence explaining the decision"
}}

If "remember" is false, memory_key/memory_value/category may be null.

User's latest message:
{user_message}
"""

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _normalize_key(raw_key: str) -> str:
    """Gemini may return "Favorite Color" instead of "favorite_color" -
    this keeps keys consistent so upserts actually match existing rows."""

    key = raw_key.strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


class MemoryExtractor:

    def __init__(self, db: DatabaseManager, client, model: str):
        """
        `client` / `model` are the same underlying genai client and
        model name GeminiService uses - passed in rather than
        instantiated here so there's exactly one Gemini client for
        the whole app, and so this service never needs to know API
        keys or config on its own.
        """
        self.db = db
        self.client = client
        self.model = model

    # -----------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------

    def process_message(self, user_id: int, user_message: str) -> None:
        """
        Analyzes one user message and, if it contains a durable fact,
        stores or updates it in the memory table. Never raises -
        any failure is logged and swallowed so a flaky extraction
        never breaks the conversation itself.
        """

        try:
            existing_memories = self.db.get_memory(user_id)
        except Exception:
            logger.exception("MemoryExtractor: failed to load existing memories for user %s", user_id)
            return

        decision = self._extract(user_message, existing_memories)

        if decision is None:
            # Invalid/unparseable Gemini response - already logged in _extract.
            return

        if not decision.get("remember"):
            logger.info(
                "Memory Ignored | user=%s | reason=%s",
                user_id, decision.get("reason", "not important"),
            )
            return

        self._store(user_id, decision, existing_memories)

    # -----------------------------------------------------------
    # Gemini extraction
    # -----------------------------------------------------------

    def _extract(self, user_message: str, existing_memories: list[dict]) -> dict | None:

        existing_summary = "\n".join(
            f"- {m['key_name']} = {m['value']} (category: {m['category']})"
            for m in existing_memories
        ) or "(none yet)"

        prompt = EXTRACTION_INSTRUCTIONS.format(
            existing_memories=existing_summary,
            user_message=user_message,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            raw_text = response.text or ""

        except Exception:
            logger.exception("MemoryExtractor: Gemini call failed")
            return None

        return self._parse_response(raw_text)

    @staticmethod
    def _parse_response(raw_text: str) -> dict | None:
        """
        Validates the model actually gave us the JSON shape we asked
        for. Anything else (malformed JSON, missing fields, wrong
        types) is treated as "ignore this turn", not an error.
        """

        cleaned = _JSON_FENCE_RE.sub("", raw_text).strip()

        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            logger.warning("MemoryExtractor: could not parse JSON from Gemini: %r", raw_text[:200])
            return None

        if not isinstance(data, dict) or "remember" not in data:
            logger.warning("MemoryExtractor: unexpected JSON shape: %r", data)
            return None

        if not isinstance(data.get("remember"), bool):
            logger.warning("MemoryExtractor: 'remember' was not a boolean: %r", data.get("remember"))
            return None

        if data["remember"]:
            key = data.get("memory_key")
            value = data.get("memory_value")
            if not key or not str(key).strip() or value is None or not str(value).strip():
                logger.warning("MemoryExtractor: remember=true but key/value missing: %r", data)
                return None

        return data

    # -----------------------------------------------------------
    # Storage
    # -----------------------------------------------------------

    def _store(self, user_id: int, decision: dict, existing_memories: list[dict]) -> None:

        key = _normalize_key(str(decision["memory_key"]))
        value = str(decision["memory_value"]).strip()
        category = (decision.get("category") or "general").strip() or "general"
        reason = decision.get("reason", "")

        if not key or not value:
            logger.warning("Memory Ignored | user=%s | reason=empty key/value after normalization", user_id)
            return

        previous = next((m for m in existing_memories if m["key_name"] == key), None)

        if previous is not None and previous["value"] == value:
            # Nothing actually changed - skip the write so updated_at
            # doesn't churn on repeated mentions of the same fact.
            logger.info(
                "Memory Ignored | user=%s | key=%s | reason=value unchanged",
                user_id, key,
            )
            return

        try:
            self.db.save_memory_bulk(user_id, [
                {"category": category, "key_name": key, "value": value}
            ])
        except Exception:
            logger.exception("MemoryExtractor: failed to save memory for user %s (key=%s)", user_id, key)
            return

        if previous is None:
            logger.info(
                "Memory Created | user=%s | key=%s | value=%s | reason=%s",
                user_id, key, value, reason,
            )
        else:
            logger.info(
                "Memory Updated | user=%s | key=%s | old_value=%s | new_value=%s | reason=%s",
                user_id, key, previous["value"], value, reason,
            )
