import os
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# Database Configuration
# ==========================================

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# ==========================================
# Gemini Configuration
# ==========================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ==========================================
# Authentication
# ==========================================

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 60))

# ==========================================
# Supabase Authentication
# ==========================================
# Supabase is used ONLY for auth (signup/login/Google OAuth/JWT).
# All application data (users, conversations, messages, memory)
# still lives in MySQL.

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# ==========================================
# Whisper
# ==========================================

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

# ==========================================
# XTTS
# ==========================================

XTTS_MODEL = os.getenv(
    "XTTS_MODEL",
    "tts_models/multilingual/multi-dataset/xtts_v2"
)

VOICE_SAMPLE = os.getenv(
    "VOICE_SAMPLE",
    "samples/voice.wav"
)

# ==========================================
# Server
# ==========================================

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "True") == "True"

# ==========================================
# Validation
# ==========================================

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")

required_db = [
    DB_HOST,
    DB_NAME,
    DB_USER,
    DB_PASSWORD
]

if any(value is None for value in required_db):
    raise ValueError("Database configuration is missing in .env")

required_supabase = [
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
]

if any(value is None for value in required_supabase):
    raise ValueError("Supabase configuration is missing in .env")