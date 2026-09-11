import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent

is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
if is_serverless:
    UPLOADS_DIR = Path("/tmp/uploads")
    SAMPLE_DIR = BASE_DIR / "sample_assets"
else:
    UPLOADS_DIR = BASE_DIR / "uploads"
    SAMPLE_DIR = BASE_DIR / "sample_assets"

try:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

try:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

class Settings:
    # App Settings
    APP_NAME: str = "Campus Lost & Found Matcher"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # MongoDB Atlas Settings
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "campus_lost_found")
    ITEMS_COLLECTION: str = "items"
    ATLAS_VECTOR_INDEX_NAME: str = os.getenv("ATLAS_VECTOR_INDEX_NAME", "vector_index")

    # Google Gemini AI Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_VISION_MODEL: str = "models/gemini-3.6-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-2"

    # Multimodal Embedding Model
    CLIP_MODEL_NAME: str = os.getenv("CLIP_MODEL_NAME", "openai/clip-vit-base-patch32")
    EMBEDDING_DIM: int = 512

    # Multimodal Weighting
    FUSED_IMG_WEIGHT: float = 0.75
    FUSED_TXT_WEIGHT: float = 0.25

    # Composite Match Score Weights
    WEIGHT_VECTOR: float = 0.70
    WEIGHT_CATEGORY: float = 0.20
    WEIGHT_LOCATION: float = 0.10

    # Match Thresholds
    DEFAULT_MATCH_THRESHOLD: float = 68.0   # >= 68% is considered a match
    HIGH_CONFIDENCE_THRESHOLD: float = 82.0  # >= 82% triggers emerald high-confidence badge

    # Campus Context Lists
    CAMPUS_LOCATIONS: list[str] = [
        "Central Library",
        "CS Block",
        "Main Cafeteria",
        "Sports Complex",
        "Engineering Annex",
        "Hostel Block A",
        "Hostel Block B",
        "Student Center",
        "Admin Building",
    ]

    ITEM_CATEGORIES: list[str] = [
        "Electronics",
        "ID & Cards",
        "Keys",
        "Bottles",
        "Bags & Backpacks",
        "Notebooks & Books",
        "Accessories & Wearables",
        "Other",
    ]

settings = Settings()
