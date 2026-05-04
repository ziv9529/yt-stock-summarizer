from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

ROOT_DIR: Path = Path(__file__).parent.parent
DATA_DIR: Path = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH: Path = Path(os.getenv("DB_PATH", str(DATA_DIR / "summaries.db")))

# Claude model versions — never use unversioned aliases
MODEL_HAIKU: str = "claude-haiku-4-5-20251001"
MODEL_SONNET: str = "claude-sonnet-4-6"
MODEL_OPUS: str = "claude-opus-4-7"

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
