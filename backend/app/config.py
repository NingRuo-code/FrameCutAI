from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT
DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'framecutai.db'}"
STORAGE_ROOT = PROJECT_ROOT / "storage"
EVAL_DATASET_PATH = REPO_ROOT / "evals" / "dataset.json"
EVAL_REPORT_ROOT = STORAGE_ROOT / "evals"
MAX_VIDEO_BYTES = 500 * 1024 * 1024
ACCEPTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
