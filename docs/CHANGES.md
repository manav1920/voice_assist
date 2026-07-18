# Conversation Management + Memory Retrieval - What Changed

Nothing about auth, onboarding, or the DB schema was touched. The
`conversations`, `messages`, and `memory` tables already existed in
`voice_assist_sql.sql` - they just weren't being used. This patch wires
them up.

## New files

- `app/services/conversation_service.py` - all conversation/message
  orchestration (create, load, list, rename, delete, save turns,
  format history for prompts, auto-title logic).
- `app/services/memory_manager.py` - loads a user's `memory` rows,
  filters them down to what's relevant to the current message
  (simple keyword overlap today - swap `search_relevant()` for
  embeddings later without touching anything else), and formats them
  into a prompt-ready block.
- `app/services/prompt_builder.py` - combines system prompt + memory
  + history + latest message into the single string Gemini receives.

## Changed files

- `app/database.py` - added CRUD for `conversations` and `messages`,
  all scoped to `user_id` so one account can never touch another's
  data. No changes to existing methods.
- `app/gemini_service.py` - `generate()` used to build its own prompt
  from raw history text and know nothing about memory. It's now
  `generate_reply(prompt)`, which just sends whatever PromptBuilder
  handed it - no prompt construction, no SQL. Added `generate_title()`
  for auto-naming conversations.
- `app/server.py`:
  - Removed the old in-memory `dict[user_id -> ConversationManager]`
    (wiped on every restart, never touched MySQL).
  - `/api/converse` now takes an optional `conversation_id` form
    field, saves the user message immediately, retrieves history +
    relevant memory, builds one prompt, saves the assistant reply,
    and auto-titles the conversation on its first turn.
  - Added: `GET /api/conversations/active`, `GET /api/conversations`,
    `POST /api/conversations`, `GET /api/conversations/{id}`,
    `PATCH /api/conversations/{id}`, `DELETE /api/conversations/{id}`.
  - Removed: `GET /api/history`, `POST /api/reset` (superseded by the
    endpoints above).
- `static/index.html` - added a ChatGPT-style sidebar (grouped
  Today / Yesterday / Previous 7 Days / Older, active-item highlight,
  rename/delete, mobile toggle). Chat history now loads from the
  backend instead of `localStorage`; every voice turn sends
  `conversation_id` and syncs the sidebar from the response.

## Not changed (on purpose)

- `app/conversation_manager.py` is no longer imported anywhere but
  was left in place rather than deleted, per "don't rewrite/remove
  things unnecessarily." Safe to delete once you've confirmed nothing
  else depends on it.
- Auth, onboarding, database schema: untouched.

## Still manual / future work

- `search_relevant()` in `memory_manager.py` is intentionally simple
  (keyword overlap) - it's structured as a single swappable method so
  real embedding-based semantic search can replace it later.
- No full-text search across conversations yet - `list_conversations()`
  is a single flat query, so adding a `?q=` param later just means one
  more WHERE clause, no restructuring.
- Long conversations: `get_formatted_history()` currently replays the
  *entire* transcript into every prompt. Fine for normal chat length;
  if you expect very long-running conversations, use the `limit`
  param already on `DatabaseManager.get_messages()` to cap it.
