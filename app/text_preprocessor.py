import re


class TextPreprocessor:
    """
    ==========================================================
                    MANASVI TEXT PREPROCESSOR V1
    ==========================================================

    Pipeline

    Raw Gemini Text
            |
            v
    Markdown Cleanup
            |
            v
    Emoji Removal
            |
            v
    Symbol Expansion
            |
            v
    URL Cleanup
            |
            v
    Email Cleanup
            |
            v
    Number Normalization
            |
            v
    Acronym Expansion
            |
            v
    Pronunciation Fixes
            |
            v
    Natural Pause Generation
            |
            v
    Final Cleanup

    """

    def __init__(self):

        # ---------------------------------------------------
        # Pronunciation Dictionary
        # ---------------------------------------------------

        self.pronunciation_dict = {

            "Manav": "Maanav",
            "Manasvi": "Manasvi",

            "Ghaziabad": "Ghaa zee aa baad",

            "AI": "A I",
            "ML": "M L",
            "NLP": "N L P",
            "API": "A P I",
            "CPU": "C P U",
            "GPU": "G P U",
            "SQL": "S Q L",
            "GPT": "G P T",

            "WiFi": "Wi Fi",
            "USB": "U S B",
            "HTTP": "H T T P",
            "HTTPS": "H T T P S"
        }

        # ---------------------------------------------------
        # Hindi Pronunciation Dictionary
        # ---------------------------------------------------
        # XTTS often mispronounces common Roman-script Hindi words
        # (it's trained mostly on English/Devanagari, not transliterated
        # Hindi). Converting just these pronunciation-critical words to
        # Devanagari before synthesis fixes that - purely a speech-
        # quality fix. The user never sees this: it only ever touches
        # the text handed to XTTS, never the reply shown in the UI.
        # Kept as its own small, easily-extended dictionary (modular,
        # separate from the English acronym dictionary above).

        self.hindi_pronunciation_dict = {

            "yaar": "यार",
            "namaste": "नमस्ते",
            "bhai": "भाई",
            "accha": "अच्छा",
            "acha": "अच्छा",
            "haan": "हाँ",
            "nahi": "नहीं",
            "nahin": "नहीं",
            "shukriya": "शुक्रिया",
            "dhanyavaad": "धन्यवाद",
            "arre": "अरे",
            "theek hai": "ठीक है",
        }

        # ---------------------------------------------------
        # Symbol Dictionary
        # ---------------------------------------------------

        self.symbol_dict = {

            "&": " and ",
            "@": " at ",
            "%": " percent ",
            "#": " number ",
            "+": " plus ",
            "=": " equals ",
            "*": " times ",
            "/": " slash ",
            "\\": " slash ",
            "|": " ",
            "~": " ",
            "^": " ",
            "_": " ",
            "<": " less than ",
            ">": " greater than "
        }

    # =====================================================
    # MAIN PIPELINE
    # =====================================================

    def preprocess(self, text):

        text = self.remove_markdown(text)

        text = self.remove_emojis(text)

        text = self.convert_hindi_pronunciation(text)

        text = self.expand_symbols(text)

        text = self.clean_urls(text)

        text = self.clean_emails(text)

        text = self.normalize_numbers(text)

        text = self.expand_abbreviations(text)

        text = self.fix_pronunciation(text)

        text = self.add_pauses(text)

        text = self.remove_extra_spaces(text)

        return text

    # =====================================================
    # MARKDOWN CLEANUP
    # =====================================================

    def remove_markdown(self, text):

        # Bold
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)

        # Italic
        text = re.sub(r"\*(.*?)\*", r"\1", text)

        # Inline Code
        text = re.sub(r"`(.*?)`", r"\1", text)

        # Headers
        text = re.sub(r"#+\s*", "", text)

        # Block Quotes
        text = re.sub(r">\s*", "", text)

        # Bullet Lists
        text = text.replace("\u2022", "")
        text = text.replace("-", " ")

        return text

    # =====================================================
    # EMOJI REMOVAL
    # =====================================================

    def remove_emojis(self, text):

        emoji_pattern = re.compile(

            "["

            "\U0001F600-\U0001F64F"

            "\U0001F300-\U0001F5FF"

            "\U0001F680-\U0001F6FF"

            "\U0001F1E0-\U0001F1FF"

            "\U00002700-\U000027BF"

            "\U000024C2-\U0001F251"

            "]+",

            flags=re.UNICODE

        )

        return emoji_pattern.sub("", text)

    # =====================================================
    # HINDI PRONUNCIATION CONVERSION
    # =====================================================

    def convert_hindi_pronunciation(self, text):

        for word, devanagari in self.hindi_pronunciation_dict.items():

            text = re.sub(
                rf"\b{re.escape(word)}\b",
                devanagari,
                text,
                flags=re.IGNORECASE,
            )

        return text

    # =====================================================
    # SYMBOL EXPANSION
    # =====================================================

    def expand_symbols(self, text):

        for symbol, replacement in self.symbol_dict.items():

            text = text.replace(symbol, replacement)

        return text

    # =====================================================
    # URL CLEANUP
    # =====================================================

    def clean_urls(self, text):

        pattern = r'https?://\S+|www\.\S+'

        def replace_url(match):

            url = match.group(0)

            url = url.replace("https://", "")
            url = url.replace("http://", "")
            url = url.replace("www.", "")

            url = url.replace("/", " slash ")
            url = url.replace(".", " dot ")

            return url

        return re.sub(pattern, replace_url, text)

    # =====================================================
    # EMAIL CLEANUP
    # =====================================================

    def clean_emails(self, text):

        pattern = r'[\w\.-]+@[\w\.-]+\.\w+'

        def replace_email(match):

            email = match.group(0)

            email = email.replace("@", " at ")
            email = email.replace(".", " dot ")

            return email

        return re.sub(pattern, replace_email, text)

    # =====================================================
    # NUMBER NORMALIZATION
    # =====================================================

    def normalize_numbers(self, text):

        # Decimal numbers

        def decimal_replace(match):

            number = match.group(0)

            return number.replace(".", " point ")

        text = re.sub(r"\d+\.\d+", decimal_replace, text)

        # Simple integers

        text = re.sub(r"\b2026\b", "two thousand twenty six", text)
        text = re.sub(r"\b2025\b", "two thousand twenty five", text)
        text = re.sub(r"\b2024\b", "two thousand twenty four", text)

        return text

    # =====================================================
    # ACRONYM EXPANSION
    # =====================================================

    def expand_abbreviations(self, text):

        for word, replacement in self.pronunciation_dict.items():

            text = re.sub(
                rf"\b{re.escape(word)}\b",
                replacement,
                text
            )

        return text

    # =====================================================
    # PRONUNCIATION FIXES
    # =====================================================

    def fix_pronunciation(self, text):

        custom = {

            "ChatGPT": "Chat G P T",

            "GitHub": "Git Hub",

            "YouTube": "You Tube",

            "OpenAI": "Open A I",

            "WhatsApp": "Whats App",

            "Wi-Fi": "Wi Fi",

            "USB": "U S B",

            "RTX": "R T X",

            "CUDA": "Cue Duh",

            "PyTorch": "Pie Torch",

            "NumPy": "Num Pie",

            "TensorFlow": "Tensor Flow"

        }

        for word, replacement in custom.items():

            text = re.sub(
                rf"\b{re.escape(word)}\b",
                replacement,
                text
            )

        return text

    # =====================================================
    # NATURAL PAUSES
    # =====================================================

    def add_pauses(self, text):

        text = text.replace(",", "...")

        text = text.replace(";", "...")

        text = text.replace(":", "...")

        text = text.replace(" - ", "...")
        text = text.replace("!", "...")
        text = text.replace("(", ", ")
        text = text.replace(")", "")

        text = text.replace("...", "... ")

        text = re.sub(r"\.\s+", ". ", text)

        return text

    # =====================================================
    # REMOVE EXTRA SPACES
    # =====================================================

    def remove_extra_spaces(self, text):

        return re.sub(r"\s+", " ", text).strip()
