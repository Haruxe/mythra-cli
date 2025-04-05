import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
DEFAULT_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DEFAULT_GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
DEFAULT_ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# --- Constants ---
GEMINI_MODELS = ["gemini-", "models/gemini-"]
OPENAI_MODELS = ["gpt-"]
ANTHROPIC_MODELS = ["claude-"]

# --- Supported Models ---
SUPPORTED_MODELS = [
    "gemini-1.5-pro-latest",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]

LLM_TIMEOUT = 90  # Timeout for LLM calls in seconds
LLM_MAX_RETRIES = 2
LLM_RETRY_DELAY_BASE = 2  # Base delay for exponential backoff in seconds
