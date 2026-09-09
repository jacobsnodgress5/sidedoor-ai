import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

# Load environment variables from the project root .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Database configuration
_default_db = PROJECT_ROOT / "sidedoor_cache.db"
if not _default_db.exists() and (PROJECT_ROOT / "netweave_cache.db").exists():
    _default_db = PROJECT_ROOT / "netweave_cache.db"

DB_PATH = os.environ.get("DB_PATH", str(_default_db))
SCHEMA_PATH = os.environ.get("SCHEMA_PATH", str(PROJECT_ROOT / "schema.sql"))

# Daily Caps
DAILY_MESSAGE_CAP = int(os.environ.get("DAILY_MESSAGE_CAP", "20"))
MAX_HUNTER_CREDITS_PER_DAY = int(os.environ.get("MAX_HUNTER_CREDITS_PER_DAY", "2"))

# API Keys
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY")
HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY")

# Instantiate and expose the Gemini Client
def get_gemini_client():
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set. Please set it in your .env file.")
    return genai.Client(api_key=GEMINI_API_KEY)

# Default model to use
DEFAULT_MODEL = "gemini-3.5-flash-lite"
