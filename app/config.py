"""
app/config.py — Centralized configuration loaded from environment variables.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present (local development)
load_dotenv()


class Settings:
    # --- Groq API ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # --- Agent ---
    MAX_STEPS: int = int(os.getenv("MAX_STEPS", "20"))
    STEP_TIMEOUT_SECONDS: int = int(os.getenv("STEP_TIMEOUT_SECONDS", "30"))

    # --- Browser ---
    HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/agent.log")

    def validate(self):
        """Raises ValueError if required settings are missing."""
        if not self.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com"
            )
        return self


settings = Settings()


def setup_logging():
    """Configure structured logging to stdout and optionally to file."""
    log_dir = Path(settings.LOG_FILE).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers = [logging.StreamHandler()]

    try:
        handlers.append(logging.FileHandler(settings.LOG_FILE))
    except (OSError, PermissionError):
        # If we can't write to the log file (e.g. in Docker read-only fs), skip it
        pass

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        handlers=handlers,
    )
