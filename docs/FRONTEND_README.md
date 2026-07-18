# Manasvi — Web Frontend

This adds a browser frontend on top of your existing pipeline
(`Recorder → Whisper → Gemini → TextPreprocessor → XTTS`), without
changing how any of your services actually work.

## What was added

- **`app/server.py`** — a FastAPI server that loads Whisper, Gemini,
  the text preprocessor, and XTTS once at startup, and exposes one
  endpoint (`POST /api/converse`) that runs your full pipeline on an
  uploaded audio clip and returns the transcript, reply text, per-stage
  timings, and a URL to the generated cloned-voice audio.
- **`static/index.html`** — the frontend: a mic button, a live pipeline
  status bar (mirroring the stage timings your CLI already prints),
  and a conversation log with audio playback.
- **`requirements-server.txt`** — the extra packages the server needs
  (`fastapi`, `uvicorn`, `python-multipart`) on top of your existing
  `requirements.txt`.

## What was fixed

- **`app/text_preprocessor.py`** had an indentation bug — six of its
  methods (`clean_urls`, `clean_emails`, `normalize_numbers`,
  `expand_abbreviations`, `fix_pronunciation`, `add_pauses`) were
  defined outside the `TextPreprocessor` class body, so
  `preprocessor.preprocess()` would raise an `AttributeError` the
  moment it tried to call them. This is now a normal class with all
  its methods properly indented — no behavior was changed, only the
  structure.

## One thing to know (not changed, just flagging)

Inside `preprocess()`, `expand_symbols()` runs *before* `clean_urls()`
and `clean_emails()`. Since `expand_symbols` turns every `/` into
`" slash "`, a URL like `https://example.com/page` gets its slashes
replaced before `clean_urls` ever sees a `//` to match — so the
"cleaned" version comes out a little garbled (e.g. `https...slash
slash example.com slash page`). It doesn't crash anything, so I left
the order exactly as you had it — but if you want it to read
smoothly, swapping so `clean_urls`/`clean_emails` run before
`expand_symbols` would fix it.

## Running it

1. Install the extra packages (in the same environment as your other
   dependencies):

   ```bash
   pip install -r requirements-server.txt
   ```

2. Make sure `ffmpeg` is installed and on your PATH — Whisper uses it
   internally to decode audio, and the browser records in
   `webm/opus`, not `wav`.

   - Windows: `winget install ffmpeg` (or download from ffmpeg.org)
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

3. From the project root (the folder with `requirements.txt`), start
   the server:

   ```bash
   uvicorn app.server:app --host 0.0.0.0 --port 8000
   ```

   The first run will take a while — it loads Whisper and XTTS-v2
   into memory, same as `run_assistant.py` does.

4. Open **http://localhost:8000** in your browser. Tap the mic,
   speak, tap again to stop. Manasvi will transcribe, think, and
   reply in the cloned voice from `samples/voice.wav`.

## Notes

- Your original `run_assistant.py` (terminal version) still works
  exactly as before — nothing about it was touched.
- The frontend calls `/api/reset` when you click **New conversation**,
  which clears `ConversationManager`'s in-memory history. Conversation
  state resets if you restart the server (it isn't persisted to disk).
- CORS is wide open (`allow_origins=["*"]`) since this is meant to run
  locally. Tighten that if you ever deploy it somewhere reachable by
  others.
