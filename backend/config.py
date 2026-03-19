import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://osint:changeme@localhost:5432/osint_viewer",
    )
    SYNC_DATABASE_URL: str = DATABASE_URL.replace("+asyncpg", "")

    OPENSKY_USERNAME: str = os.getenv("OPENSKY_USERNAME", "")
    OPENSKY_PASSWORD: str = os.getenv("OPENSKY_PASSWORD", "")

    NOMINATIM_USER_AGENT: str = os.getenv(
        "NOMINATIM_USER_AGENT", "osint-viewer/1.0"
    )

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    FLIGHT_REFRESH_INTERVAL: int = int(
        os.getenv("FLIGHT_REFRESH_INTERVAL", "60")
    )
    SCRAPING_REFRESH_INTERVAL: int = int(
        os.getenv("SCRAPING_REFRESH_INTERVAL", "900")
    )


settings = Settings()
