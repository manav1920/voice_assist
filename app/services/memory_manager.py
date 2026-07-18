"""
MemoryManager
==============
The onboarding wizard already stores long-term facts about the user
in the `memory` table (one row per key_name). This service is the
ONLY thing that reads that table and turns it into something Gemini
can use - GeminiService and PromptBuilder never see SQL.

Today's retrieval strategy is a simple keyword-overlap filter: cheap,
dependency-free, and good enough to avoid dumping the user's entire
memory into every single prompt. The public methods are deliberately
narrow (load / search / format) so `search_relevant` can be swapped
for real embedding-based semantic search later without touching
anything above this class.
"""

import re

from app.database import DatabaseManager

# Below this many stored facts, there's no real prompt-bloat problem -
# just send everything and skip the relevance filtering entirely.
RELEVANCE_THRESHOLD = 12

# Words too common to be useful signals for keyword overlap.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "what", "whats",
    "who", "when", "where", "why", "how", "do", "does", "did",
    "my", "your", "i", "you", "me", "to", "of", "in", "on", "for",
    "and", "or", "please", "can", "could", "would", "tell", "about",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


class MemoryManager:

    def __init__(self, db: DatabaseManager):
        self.db = db

    # -----------------------------------------------------------
    # Load
    # -----------------------------------------------------------

    def load_memories(self, user_id: int) -> list[dict]:
        """All stored facts for this user: [{category, key_name, value}, ...]"""
        return self.db.get_memory(user_id)

    # -----------------------------------------------------------
    # Search / relevance
    # -----------------------------------------------------------

    def search_relevant(self, memories: list[dict], query: str) -> list[dict]:
        """
        Returns the subset of `memories` relevant to `query`.

        Strategy (swap-in point for future semantic search): score
        each memory by how many non-stopword tokens it shares with
        the query, across its key_name and value. Anything with at
        least one shared token is considered relevant; if nothing
        matches, fall back to returning everything so the assistant
        never silently loses context it might need (e.g. "preferred
        name" is worth including even on unrelated questions).
        """

        if len(memories) <= RELEVANCE_THRESHOLD:
            return memories

        query_tokens = _tokenize(query)
        if not query_tokens:
            return memories

        scored = []
        for mem in memories:
            haystack = f"{mem.get('key_name', '')} {mem.get('value', '')}"
            mem_tokens = _tokenize(haystack)
            overlap = len(query_tokens & mem_tokens)
            if overlap > 0:
                scored.append((overlap, mem))

        if not scored:
            # Always keep core identity facts even when nothing matches,
            # so the assistant still knows who it's talking to.
            return [
                m for m in memories
                if m.get("category") == "identity"
            ] or memories

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [mem for _, mem in scored]

    # -----------------------------------------------------------
    # Format
    # -----------------------------------------------------------

    def format_memory_context(self, memories: list[dict]) -> str:
        """
        Turns memory rows into a compact, prompt-ready block, grouped
        by category, e.g.:

            [identity]
            preferred_name: Manav

            [preferences]
            favorite_flower: Tulip
        """

        if not memories:
            return ""

        by_category: dict[str, list[dict]] = {}
        for mem in memories:
            by_category.setdefault(mem.get("category", "general"), []).append(mem)

        blocks = []
        for category, items in by_category.items():
            lines = [f"[{category}]"]
            for item in items:
                lines.append(f"{item['key_name']}: {item['value']}")
            blocks.append("\n".join(lines))

        return "\n\n".join(blocks)

    # -----------------------------------------------------------
    # Convenience: load + search + format in one call
    # -----------------------------------------------------------

    def get_relevant_memory_context(self, user_id: int, query: str) -> str:
        """
        Prompt-ready memory text for a given user + latest message.
        Returns "" if the user has no stored memories yet.
        """

        memories = self.load_memories(user_id)
        if not memories:
            return ""

        relevant = self.search_relevant(memories, query)
        return self.format_memory_context(relevant)
