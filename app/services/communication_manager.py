"""
CommunicationManager
======================
Manasvi should talk like a real bilingual Indian friend - naturally
mirroring whether the user is writing in English, Hindi, Roman Hindi,
or Hinglish, without ever sounding like a translator forcing one
language.

This service owns everything related to *how* Manasvi should speak in
this reply. It is deliberately separate from:

- MemoryManager   (owns *what* Manasvi knows about the user)
- PromptBuilder   (owns *assembling* the final prompt string)
- GeminiService   (owns *talking to* Gemini - never sees SQL or
                    detection logic)

PromptBuilder just receives a finished instruction block from here and
slots it in; it never needs to know how style was decided.

--------------------------------------------------------------------
Future-ready extension points (NOT implemented yet - see the spec):
    - Tone / emotion detection
    - Conversation mood tracking
    - Humor
    - Formality / relationship-level detection
    - Speaking speed / voice style

Each of those would become its own `detect_x()` method here, feeding
its own line into `build_communication_instructions()`, without
touching PromptBuilder or GeminiService at all.
--------------------------------------------------------------------
"""

import re

from app.database import DatabaseManager

# ---------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_WORD_RE = re.compile(r"[a-zA-Z']+")

# Common Roman-script Hindi/Hinglish function words and everyday verbs.
# Deliberately excludes short tokens that collide with common English
# words (e.g. "the", "hi", "a", "he", "so") to keep false positives low.
# Not exhaustive - this is a cheap heuristic with an obvious upgrade
# path to a real language-ID model later, same spirit as
# MemoryManager's keyword-overlap search.
_ROMAN_HINDI_WORDS = frozenset({
    "kya", "kyu", "kyun", "kyunki", "kaise", "kaisi", "kaisa", "kahan",
    "kab", "kaun", "kitna", "kitni",
    "kar", "karo", "karti", "karta", "karna", "kiya", "kiye", "kari",
    "raha", "rahi", "rahe", "rha", "rhi",
    "hai", "hain", "tha", "thi", "the", "thay", "hoga", "hogi", "honge",
    "hoon", "hun", "ho",
    "nahi", "nahin", "haan", "han",
    "matlab", "accha", "acha", "achha", "theek", "thik",
    "bhai", "yaar", "dost",
    "tum", "tumhe", "tumse", "tumhara", "tumhari",
    "tera", "teri", "tere",
    "mera", "meri", "mere",
    "hum", "humein", "humse", "apna", "apni",
    "uska", "uske", "iska", "iske",
    "waise", "waisay", "wala", "wali",
    "abhi", "jaldi", "bas", "sirf", "bilkul", "shayad",
    "lekin", "magar", "agar", "toh", "tho",
    "pareshan", "tension", "samajh", "sakti", "sakta", "sakte",
    "puchni", "puchna", "poochna",
    "zindagi", "dil", "pyaar", "pyar",
    "ghar", "khana", "paani", "paisa", "kaam", "naukri", "padhai",
    "chalo", "chal", "chale",
    "bahut", "thoda", "zyada", "bohot",
})

# Tokens that only really make sense as loose Hindi/Hinglish markers
# when combined with the ones above - kept separate so they alone
# don't tip a message into "roman_hindi" territory.
_WEAK_MARKERS = frozenset({"ho", "the", "hai"})

LANG_ENGLISH = "english"
LANG_HINDI = "hindi"            # Devanagari script
LANG_ROMAN_HINDI = "roman_hindi"  # Hindi, written in Latin script
LANG_HINGLISH = "hinglish"      # Hindi + English mixed, Latin script
LANG_MIXED = "mixed"            # Devanagari mixed with real English

# Ordered "distance" scale used to keep style transitions gradual -
# see _smooth_style() below.
_STYLE_SCALE = [LANG_ENGLISH, LANG_HINGLISH, LANG_ROMAN_HINDI]


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


class CommunicationManager:

    # -----------------------------------------------------------
    # Per-message language detection
    # -----------------------------------------------------------

    def detect_message_language(self, text: str) -> str:
        """
        Classifies a single message. Deliberately does not rely only
        on Unicode - Roman-script Hindi ("kya kar raha hai") is
        detected via a curated marker-word list, not script alone.
        """

        text = text or ""
        has_devanagari = bool(_DEVANAGARI_RE.search(text))

        words = _tokenize(text)
        if not words:
            return LANG_HINDI if has_devanagari else LANG_ENGLISH

        strong_hits = sum(1 for w in words if w in _ROMAN_HINDI_WORDS and w not in _WEAK_MARKERS)
        weak_hits = sum(1 for w in words if w in _WEAK_MARKERS)
        hindi_marker_ratio = (strong_hits + 0.4 * weak_hits) / len(words)

        if has_devanagari:
            # Devanagari present alongside a real amount of plain
            # English content -> code-mixed at the script level.
            english_only_words = len(words) - strong_hits - weak_hits
            if english_only_words >= 3:
                return LANG_MIXED
            return LANG_HINDI

        if strong_hits == 0:
            return LANG_ENGLISH

        if hindi_marker_ratio >= 0.6:
            return LANG_ROMAN_HINDI

        return LANG_HINGLISH

    # -----------------------------------------------------------
    # Conversation-level style (smoothed, not per-message)
    # -----------------------------------------------------------

    def detect_conversation_style(self, conversation_history: str, latest_message: str) -> str:
        """
        Decides the style to reply in *right now*, weighting recent
        turns more heavily so a single new word doesn't flip the whole
        conversation's language. E.g. an English conversation where the
        user suddenly writes one Hinglish-leaning sentence should nudge
        the reply toward Hinglish, not snap all the way to Roman Hindi.
        """

        current = self.detect_message_language(latest_message)

        past_user_lines = [
            line.split(":", 1)[1].strip()
            for line in (conversation_history or "").splitlines()
            if line.lower().startswith("user:")
        ]

        if not past_user_lines:
            # First message in the conversation - nothing to smooth
            # against yet, so just mirror the message as detected.
            return current

        # Recency-weighted vote over the last few user turns plus the
        # current message (current counts for more than any single
        # past turn, but not enough to override a strong pattern).
        recent = past_user_lines[-5:]
        history_style = self._weighted_history_style(recent)

        return self._smooth_style(history_style, current)

    def _weighted_history_style(self, past_messages: list[str]) -> str:
        scores = {LANG_ENGLISH: 0.0, LANG_HINGLISH: 0.0, LANG_ROMAN_HINDI: 0.0}

        weight = 1.0
        for msg in reversed(past_messages):  # most recent first
            style = self.detect_message_language(msg)
            bucket = self._collapse_to_scale(style)
            scores[bucket] += weight
            weight *= 0.7  # older turns count for progressively less

        return max(scores, key=scores.get)

    @staticmethod
    def _collapse_to_scale(style: str) -> str:
        """Maps hindi/mixed onto the same end of the scale as roman_hindi."""
        if style in (LANG_HINDI, LANG_MIXED, LANG_ROMAN_HINDI):
            return LANG_ROMAN_HINDI
        if style == LANG_HINGLISH:
            return LANG_HINGLISH
        return LANG_ENGLISH

    @staticmethod
    def _smooth_style(history_style: str, current_style: str) -> str:
        """
        Only allows the conversation to move one step at a time along
        [english -> hinglish -> roman_hindi]. A pure Hindi/Devanagari
        message from the user is always mirrored directly though -
        that's an explicit, unambiguous signal, not something to damp.
        """

        if current_style in (LANG_HINDI, LANG_MIXED):
            return current_style

        current_bucket = CommunicationManager._collapse_to_scale(current_style)

        if history_style not in _STYLE_SCALE or current_bucket not in _STYLE_SCALE:
            return current_style

        history_idx = _STYLE_SCALE.index(history_style)
        current_idx = _STYLE_SCALE.index(current_bucket)

        if current_idx - history_idx > 1:
            return _STYLE_SCALE[history_idx + 1]

        return current_bucket

    # -----------------------------------------------------------
    # Prompt instructions
    # -----------------------------------------------------------

    def build_communication_instructions(self, style: str) -> str:
        """The block PromptBuilder inserts verbatim into the prompt."""

        shared = (
            "Communication Style:\n"
            "- Mirror the user's language naturally - never translate "
            "unnecessarily and never sound like Google Translate.\n"
            "- Speak like a close, emotionally aware friend, not a "
            "textbook or customer support script.\n"
            "- Use contractions and casual phrasing naturally.\n"
            "- Use emojis only when they'd feel natural here - never "
            "force them, never overuse them.\n"
        )

        style_line = {
            LANG_ENGLISH: "- Reply in natural, conversational English.",
            LANG_HINDI: "- Reply in Hindi, written in Devanagari script, matching the user.",
            LANG_ROMAN_HINDI: "- Reply in Hindi, written in Roman/Latin script (like the user did) - do not switch to Devanagari or to English.",
            LANG_HINGLISH: "- Reply in natural Hinglish, blending Hindi and English in Roman script exactly like the user does.",
            LANG_MIXED: "- Mirror the user's mix of Hindi and English naturally, in whichever script fits the reply best.",
        }.get(style, "- Reply in natural, conversational English.")

        return shared + style_line

    # -----------------------------------------------------------
    # Gradual preferred-language memory
    # -----------------------------------------------------------
    # The committed preference is stored as an ordinary row in the
    # existing `memory` table (no schema change) - one fact,
    # key_name="preferred_language". The streak counter that decides
    # WHEN to commit a change is deliberately kept in process memory
    # rather than in that same table: MemoryManager formats every
    # stored row verbatim into the prompt context (and we're not
    # allowed to modify memory retrieval), so bookkeeping fields would
    # otherwise leak into Gemini's prompt as meaningless noise. Losing
    # an in-progress streak on server restart is an acceptable
    # trade-off for a soft heuristic like this - the committed
    # preference itself still persists fine.

    _MEMORY_CATEGORY = "communication"
    _PREF_KEY = "preferred_language"
    _STREAK_TO_UPDATE = 3  # consecutive agreeing turns before we commit to a change

    def __init__(self, db: DatabaseManager):
        self.db = db
        self._streaks: dict[int, dict] = {}  # user_id -> {"candidate": str, "count": int}

    def update_preferred_language_memory(self, user_id: int, detected_style: str):
        """
        Call this once per turn with the just-detected conversation
        style. Only overwrites the stored preference after several
        consecutive turns agree - a single message's language never
        overwrites a habit observed across a real conversation.
        """

        bucket = self._collapse_to_scale(detected_style)

        existing = {
            row["key_name"]: row["value"]
            for row in self.db.get_memory(user_id)
            if row.get("category") == self._MEMORY_CATEGORY
        }
        current_pref = existing.get(self._PREF_KEY)

        if current_pref == bucket:
            self._streaks.pop(user_id, None)
            return

        if current_pref is None:
            # No preference recorded yet - safe to set immediately,
            # there's nothing established to gradually change away from.
            self.db.save_memory_bulk(user_id, [
                {"category": self._MEMORY_CATEGORY, "key_name": self._PREF_KEY, "value": bucket}
            ])
            return

        streak = self._streaks.get(user_id)
        if streak and streak["candidate"] == bucket:
            streak["count"] += 1
        else:
            streak = {"candidate": bucket, "count": 1}
        self._streaks[user_id] = streak

        if streak["count"] >= self._STREAK_TO_UPDATE:
            self.db.save_memory_bulk(user_id, [
                {"category": self._MEMORY_CATEGORY, "key_name": self._PREF_KEY, "value": bucket}
            ])
            self._streaks.pop(user_id, None)
