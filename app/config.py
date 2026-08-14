"""Environment configuration loaded from the local .env file."""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Reads and validates the environment variables the app needs."""

    def __init__(self) -> None:
        self.supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
        self.supabase_key: str = os.getenv("SUPABASE_KEY", "").strip()
        self.port: int = int(os.getenv("PORT", "3000"))

        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_KEY", self.supabase_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing environment variable(s): {', '.join(missing)}. "
                "Copy .env.example to .env and fill in your Supabase credentials."
            )


settings = Settings()
