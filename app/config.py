"""Environment settings, read after .env is loaded by main.py."""
import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    public_base_url: str
    auth_token: str
    account_sid: str
    api_key: str
    live_model: str
    voice_mode: str
    validate_signatures: bool

    @classmethod
    def from_env(cls):
        return cls(os.getenv("PUBLIC_BASE_URL", "").rstrip('/'),
                   os.getenv("TWILIO_AUTH_TOKEN", ""), os.getenv("TWILIO_ACCOUNT_SID", ""),
                   os.getenv("GEMINI_API_KEY", ""),
                   os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-preview-12-2025"),
                   os.getenv("VOICE_MODE", "gemini"),
                   os.getenv("TWILIO_VALIDATE_SIGNATURES", "true").lower() == "true")

    def check(self):
        url = urlsplit(self.public_base_url)
        if url.scheme != "https" or not url.netloc or url.path or url.query or url.fragment or url.username:
            raise ValueError("Set PUBLIC_BASE_URL to your ngrok HTTPS origin, with no path.")
        if self.validate_signatures and not self.auth_token:
            raise ValueError("Set TWILIO_AUTH_TOKEN to validate incoming calls.")
        if self.voice_mode not in {"gemini", "echo"}:
            raise ValueError("VOICE_MODE must be gemini or echo.")
        if self.voice_mode == "gemini" and not self.api_key:
            raise ValueError("Set GEMINI_API_KEY, or use VOICE_MODE=echo to test the phone line.")
