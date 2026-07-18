"""
ConversationService
====================
Everything about *managing* conversations and messages lives here -
creating, loading, listing, renaming, deleting, and saving turns.

This is the only place (besides database.py itself) that knows a
conversation has a user_id, a title, messages, etc. Nothing above this
layer (server.py, PromptBuilder, GeminiService) touches SQL directly.
"""

from app.database import DatabaseManager

DEFAULT_TITLE = "New Conversation"
MAX_TITLE_WORDS = 5


class ConversationService:

    def __init__(self, db: DatabaseManager):
        self.db = db

    # -----------------------------------------------------------
    # Active conversation
    # -----------------------------------------------------------

    def get_or_create_active_conversation(self, user_id: int) -> dict:
        """
        Called right after login (and as a fallback if the frontend
        somehow doesn't have a conversation_id yet). Returns the most
        recently active conversation, or creates a brand new one if
        the user has none at all.
        """

        conversation = self.db.get_latest_conversation(user_id)

        if conversation is None:
            conversation = self.db.create_conversation(user_id, DEFAULT_TITLE)

        return conversation

    # -----------------------------------------------------------
    # CRUD
    # -----------------------------------------------------------

    def create_conversation(self, user_id: int) -> dict:
        return self.db.create_conversation(user_id, DEFAULT_TITLE)

    def get_conversation(self, conversation_id: int, user_id: int) -> dict | None:
        """
        Returns the conversation row, or None if it doesn't exist or
        doesn't belong to this user - callers should treat None as a
        404, never leak whether the id exists under another account.
        """
        return self.db.get_conversation_by_id(conversation_id, user_id)

    def list_conversations(self, user_id: int) -> list[dict]:
        return self.db.list_conversations(user_id)

    def rename_conversation(self, conversation_id: int, user_id: int, title: str) -> bool:
        title = (title or "").strip()
        if not title:
            title = DEFAULT_TITLE
        return self.db.update_conversation_title(conversation_id, user_id, title)

    def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        return self.db.delete_conversation(conversation_id, user_id)

    # -----------------------------------------------------------
    # Messages
    # -----------------------------------------------------------

    def get_messages(self, conversation_id: int) -> list[dict]:
        return self.db.get_messages(conversation_id)

    def save_user_message(self, conversation_id: int, user_id: int, text: str):
        self.db.add_message(conversation_id, "user", text)
        self.db.touch_conversation(conversation_id, user_id)

    def save_assistant_message(self, conversation_id: int, user_id: int, text: str, model: str = None):
        self.db.add_message(conversation_id, "assistant", text, model=model)
        self.db.touch_conversation(conversation_id, user_id)

    # -----------------------------------------------------------
    # History formatting (for prompts)
    # -----------------------------------------------------------

    def get_formatted_history(self, conversation_id: int, exclude_last: bool = False) -> str:
        """
        Renders prior turns as plain text for PromptBuilder, e.g.:

            User: Hello
            Assistant: Hi there!

        `exclude_last=True` drops the final message - useful when the
        latest user message has already been saved to the DB before
        the prompt is built, so it isn't duplicated (it gets its own
        "Latest User Message" section instead).
        """

        messages = self.db.get_messages(conversation_id)

        if exclude_last and messages:
            messages = messages[:-1]

        lines = []
        for msg in messages:
            role = msg["role"].capitalize()
            lines.append(f"{role}: {msg['message']}")

        return "\n".join(lines)

    # -----------------------------------------------------------
    # Auto-titling
    # -----------------------------------------------------------

    def needs_title(self, conversation: dict) -> bool:
        """
        True only for a conversation that hasn't been given a real
        title yet (still the placeholder, and this is its first
        message pair).
        """
        return not conversation.get("title") or conversation["title"] == DEFAULT_TITLE

    @staticmethod
    def clean_title(raw_title: str) -> str:
        """
        Keeps a generated title short and single-line no matter what
        the model returns - strips quotes/markdown, collapses
        whitespace, and hard-caps at MAX_TITLE_WORDS words.
        """

        if not raw_title:
            return DEFAULT_TITLE

        title = raw_title.strip().strip('"').strip("'").strip()
        title = title.splitlines()[0].strip()

        words = title.split()
        if not words:
            return DEFAULT_TITLE

        title = " ".join(words[:MAX_TITLE_WORDS])
        return title
