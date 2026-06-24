"""Central configuration, loaded from environment variables / .env.

Nothing secret is hard-coded. See .env.example for the full list.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# --- The only number we are permitted to dial -------------------------------
# The brief says: "Calls only our test number". We hard-default to it and the
# caller refuses to dial anything else (see caller.py).
ALLOWED_TARGET = "+18054398008"


class Settings:
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
    TARGET_NUMBER = os.getenv("TARGET_NUMBER", ALLOWED_TARGET)

    # Public hostname where Twilio reaches this server (no scheme).
    # e.g. "abc123.ngrok.app"  ->  https/wss are derived from it.
    PUBLIC_HOST = os.getenv("PUBLIC_HOST", "")

    # OpenAI Realtime
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-4o-realtime-preview")
    REALTIME_VOICE = os.getenv("REALTIME_VOICE", "alloy")

    # Transcription / analysis (post-call verification path)
    TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL", "whisper-1")
    ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "gpt-4o")

    # Local server
    PORT = int(os.getenv("PORT", "5050"))

    # Safety: max call length so a stuck call can't run forever (seconds)
    MAX_CALL_SECONDS = int(os.getenv("MAX_CALL_SECONDS", "210"))  # 3.5 min

    @property
    def ws_url(self) -> str:
        return f"wss://{self.PUBLIC_HOST}/media"

    @property
    def https_url(self) -> str:
        return f"https://{self.PUBLIC_HOST}"


settings = Settings()
