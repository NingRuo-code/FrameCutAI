from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'framecutai.db'}"
STORAGE_ROOT = PROJECT_ROOT / "storage"
MAX_VIDEO_BYTES = 500 * 1024 * 1024
ACCEPTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
