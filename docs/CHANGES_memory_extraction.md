# Automatic Memory Extraction + Updating - What Changed

Nothing about auth, onboarding, the conversation system, memory
retrieval, or the schema was touched. This adds one new, independent
service and one insertion point in the existing pipeline.

## New file

- `app/services/memory_extractor.py` - `MemoryExtractor`:
  - `process_message(user_id, user_message)` - the only public entry
    point. Asks Gemini (via a JSON-only extraction prompt) whether the
    message contains a durable personal fact, validates the response,
    and if so upserts it into the existing `memory` table.
  - Reuses `DatabaseManager.save_memory_bulk()`, which already upserts
    on the existing `UNIQUE(user_id, key_name)` constraint - so
    "update if it exists" needed zero schema or DB-layer changes.
  - If the extracted value is identical to what's already stored, it
    skips the write entirely (no pointless `updated_at` churn).
  - Every failure mode - unreachable Gemini, malformed JSON, missing
    fields, non-boolean `remember` - is caught, logged, and treated
    as "ignore this message." Nothing here can crash a request.
  - Logs `Memory Created` / `Memory Updated` / `Memory Ignored` with
    the reason, at INFO level, server-side only (never in an API
    response).

## Changed file

- `app/server.py`:
  - Added `logging.basicConfig(...)` so the extractor's log lines are
    actually visible (nothing was configured before).
  - Instantiates `MemoryExtractor(db, gemini.client, gemini.model)` -
    it reuses GeminiService's already-initialized client instead of
    creating a second one, so there's still exactly one Gemini client
    in the app.
  - In `/api/converse`, inserted one step, in the exact order from
    the spec's pipeline diagram: right after the user message is
    saved, and *before* memory is retrieved for the prompt. That
    ordering means a correction like "actually my favorite color is
    black" is reflected in the very same reply, not just future ones.
    Wrapped in its own try/except and given its own `timings["memory_extraction"]`
    entry, consistent with the other pipeline stages.

## Not changed (on purpose)

- No new tables, no ranking/importance column, no schema migration.
- `MemoryManager` (retrieval) is untouched - extraction only writes,
  retrieval only reads, and neither knows the other exists.
- `GeminiService` has no memory-extraction logic in it.

## Future hooks already in place

- `category` is stored per-memory today exactly as Gemini labels it,
  so an importance/ranking pass later can key off it without a
  migration.
- `MemoryManager.search_relevant()` already documents itself as the
  swap-in point for semantic search - extraction writes plain
  key/value rows, so it'll work unchanged whenever that lands.
