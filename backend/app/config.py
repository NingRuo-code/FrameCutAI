import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT
DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'framecutai.db'}"
STORAGE_ROOT = PROJECT_ROOT / "storage"
EVAL_DATASET_PATH = REPO_ROOT / "evals" / "dataset.json"
EVAL_REPORT_ROOT = STORAGE_ROOT / "evals"
MAX_VIDEO_BYTES = int(os.getenv("FRAMECUTAI_MAX_VIDEO_BYTES", str(500 * 1024 * 1024)))
ACCEPTED_VIDEO_EXTENSIONS = {
    extension.strip().lower()
    for extension in os.getenv(
        "FRAMECUTAI_ACCEPTED_VIDEO_EXTENSIONS",
        ".mp4,.mov,.mkv,.webm,.avi",
    ).split(",")
    if extension.strip()
}
PROVIDER_MODE = os.getenv("FRAMECUTAI_PROVIDER_MODE", "mock")
ASR_PROVIDER = os.getenv("FRAMECUTAI_ASR_PROVIDER", "mock")
LLM_PROVIDER = os.getenv("FRAMECUTAI_LLM_PROVIDER", "mock")
VISION_PROVIDER = os.getenv("FRAMECUTAI_VISION_PROVIDER", "mock")
ASR_MODEL = os.getenv("FRAMECUTAI_ASR_MODEL", "mock-asr")
LLM_MODEL = os.getenv("FRAMECUTAI_LLM_MODEL", "mock-llm")
VISION_MODEL = os.getenv("FRAMECUTAI_VISION_MODEL", "mock-vision")
