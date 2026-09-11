import os
import shutil
import logging
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from bson import ObjectId

from backend.config import settings, BASE_DIR, UPLOADS_DIR, SAMPLE_DIR
from backend.database import connect_to_mongo, close_mongo_connection, get_items_collection, db_manager
from backend.models import create_item_doc, item_doc_to_dict
from backend.schemas import ItemResponse, MatchCandidate, ItemCreateResult, VisualScanResult, StatsResponse
from backend.ml_engine import ml_engine
from backend.vector_search import find_matches, add_item_to_store, in_memory_items
from backend.seed_data import seed_campus_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("campus_lost_found.app")

FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing Campus Lost & Found Engine...")
    await connect_to_mongo()

    yield

    # Shutdown
    await close_mongo_connection()

from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# GZip compression for ultra-fast transfers
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS middleware for open campus client access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount media directories safely
try:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
except Exception:
    pass

try:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/sample_assets", StaticFiles(directory=str(SAMPLE_DIR)), name="sample_assets")
except Exception:
    pass

if (FRONTEND_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

import asyncio
import time

@app.middleware("http")
async def db_connection_middleware(request, call_next):
    # Non-blocking connection check: never stall user requests
    if not db_manager.is_connected and not db_manager.is_connecting:
        if time.time() - db_manager.last_attempt_time > 45.0:
            asyncio.create_task(connect_to_mongo())
    return await call_next(request)

# ----------------- API ENDPOINTS -----------------

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "mongo_connected": db_manager.is_connected,
        "clip_ready": ml_engine.is_loaded,
        "gemini_active": bool(settings.GEMINI_API_KEY),
        "using_fallback_encoder": ml_engine.use_fallback,
        "items_in_store": len(in_memory_items)
    }

@app.post("/api/ai/analyze-image")
async def ai_analyze_image(image: UploadFile = File(...)):
    """
    Analyzes an uploaded item image with Google Gemini Multimodal Vision AI
    to automatically extract Title, Description, Category, and Tags.
    """
    if not image or not image.filename:
        raise HTTPException(status_code=400, detail="No image file provided.")

    contents = await image.read()
    if len(contents) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image exceeds 8MB limit.")

    analysis = ml_engine.analyze_image_with_gemini(contents)
    if not analysis:
        filename_clean = Path(image.filename).stem.replace("_", " ").replace("-", " ")
        return {
            "success": False,
            "title": filename_clean.title(),
            "description": "Item photo uploaded.",
            "category": "Other",
            "tags": ["campus"],
            "model": "fallback"
        }

    return {
        "success": True,
        "title": analysis.get("title", ""),
        "description": analysis.get("description", ""),
        "category": analysis.get("category", "Other"),
        "tags": analysis.get("tags", []),
        "model": "gemini-3.6-flash"
    }

@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """Retrieve campus aggregate stats for live status pills and dashboard."""
    items_col = get_items_collection()
    active_lost = 0
    active_found = 0
    claimed_count = 0
    categories_count = {cat: 0 for cat in settings.ITEM_CATEGORIES}
    locations_count = {loc: 0 for loc in settings.CAMPUS_LOCATIONS}

    all_items = []
    if items_col is not None:
        try:
            async for doc in items_col.find({}):
                all_items.append(doc)
        except Exception as e:
            logger.warning(f"Error fetching stats from MongoDB: {e}")
            all_items = in_memory_items
    else:
        all_items = in_memory_items

    for item in all_items:
        status_val = item.get("status", "ACTIVE")
        item_type = item.get("item_type", "LOST")
        cat = item.get("category", "Other")
        loc = item.get("location", "Campus")

        if status_val == "ACTIVE":
            if item_type == "LOST":
                active_lost += 1
            else:
                active_found += 1
        elif status_val == "CLAIMED":
            claimed_count += 1

        if cat in categories_count:
            categories_count[cat] += 1
        else:
            categories_count[cat] = categories_count.get(cat, 0) + 1

        if loc in locations_count:
            locations_count[loc] += 1
        else:
            locations_count[loc] = locations_count.get(loc, 0) + 1

    total_active = active_lost + active_found

    return StatsResponse(
        total_active=total_active,
        total_lost=active_lost,
        total_found=active_found,
        total_claimed=claimed_count,
        categories=categories_count,
        locations=locations_count,
        is_mongo_connected=db_manager.is_connected
    )

@app.get("/api/config/options")
async def get_form_options():
    """Provides dropdown options for UI forms."""
    return {
        "categories": settings.ITEM_CATEGORIES,
        "locations": settings.CAMPUS_LOCATIONS
    }

@app.post("/api/items", response_model=ItemCreateResult)
async def report_item(
    item_type: str = Form(..., description="'LOST' or 'FOUND'"),
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    location: str = Form(...),
    contact_info: str = Form(...),
    contact_name: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """
    Submits a Lost or Found item:
    1. Validates & stores image.
    2. Generates 512-dim multimodal CLIP embedding (0.75 * E_img + 0.25 * E_txt).
    3. Persists document to MongoDB Atlas.
    4. Automatically queries candidate matches from the opposite partition.
    """
    item_type = item_type.upper()
    if item_type not in ["LOST", "FOUND"]:
        raise HTTPException(status_code=400, detail="item_type must be either 'LOST' or 'FOUND'")

    # Handle image upload & size validation (< 8MB)
    image_rel_url = None
    saved_file_path = None

    if image and image.filename:
        # Check file extension
        ext = Path(image.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(status_code=400, detail="Unsupported image format. Use JPG, PNG, or WEBP.")

        # Read file contents & validate size (< 8MB = 8 * 1024 * 1024 bytes)
        contents = await image.read()
        if len(contents) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size exceeds 8MB limit.")

        unique_filename = f"{item_type.lower()}_{int(ObjectId().generation_time.timestamp())}_{os.urandom(4).hex()}{ext}"
        saved_file_path = UPLOADS_DIR / unique_filename
        try:
            with open(saved_file_path, "wb") as f:
                f.write(contents)
            image_rel_url = f"/uploads/{unique_filename}"
        except Exception:
            # On serverless platforms (Vercel) where local disk is read-only
            saved_file_path = None

        # For cloud/serverless persistence in MongoDB, store compressed base64 data URI
        import base64
        import io
        try:
            from PIL import Image
            pil_img = Image.open(io.BytesIO(contents)).convert("RGB")
            pil_img.thumbnail((600, 600))
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG", quality=80)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            image_rel_url = f"data:image/jpeg;base64,{b64_str}"
        except Exception:
            if not image_rel_url:
                image_rel_url = f"data:image/jpeg;base64,{base64.b64encode(contents).decode('utf-8')}"

    # Extract parsed tags
    parsed_tags = [t.strip().lower() for t in tags.split(",") if t.strip()] if tags else []

    # Compute Fused Multimodal Embedding
    text_content = f"{title} {description} {' '.join(parsed_tags)}"
    embedding_vector = ml_engine.get_fused_embedding(str(saved_file_path) if saved_file_path else None, text_content)

    # Construct and insert MongoDB document
    doc = create_item_doc(
        item_type=item_type,
        title=title,
        description=description,
        category=category,
        location=location,
        contact_info=contact_info,
        contact_name=contact_name,
        image_path=image_rel_url,
        embedding=embedding_vector,
        tags=parsed_tags,
        status="ACTIVE"
    )

    item_id = await add_item_to_store(doc)
    doc["id"] = item_id

    # Retrieve candidate matches from the OPPOSITE partition
    # (e.g., if user reported LOST, search active FOUND items)
    matches_raw = await find_matches(
        query_vector=embedding_vector,
        query_item_type=item_type,
        query_category=category,
        query_location=location,
        limit=3,
        min_threshold=settings.DEFAULT_MATCH_THRESHOLD
    )

    # Enhance top match with Google Gemini AI explanation if available
    if matches_raw and settings.GEMINI_API_KEY:
        try:
            top_cand = matches_raw[0]
            explanation = ml_engine.explain_match_with_gemini(
                lost_title=title if item_type == "LOST" else top_cand["item"]["title"],
                lost_desc=description if item_type == "LOST" else top_cand["item"]["description"],
                found_title=top_cand["item"]["title"] if item_type == "LOST" else title,
                found_desc=top_cand["item"]["description"] if item_type == "LOST" else description
            )
            if explanation:
                top_cand["ai_explanation"] = explanation
        except Exception:
            pass

    created_item = item_doc_to_dict(doc, include_contact=True)
    matches = [MatchCandidate(**m) for m in matches_raw]

    return ItemCreateResult(
        item=ItemResponse(**created_item),
        matches=matches,
        message=f"{item_type} report registered successfully. Found {len(matches)} matching candidates."
    )

@app.post("/api/ai/explain-match")
async def explain_match_endpoint(
    lost_title: str = Form(...),
    lost_desc: str = Form(...),
    found_title: str = Form(...),
    found_desc: str = Form(...)
):
    """Generates a real-time Gemini AI explanation for why two items match."""
    explanation = ml_engine.explain_match_with_gemini(lost_title, lost_desc, found_title, found_desc)
    return {
        "explanation": explanation or "Both items share high visual and semantic similarity.",
        "model": "gemini-3.6-flash"
    }

@app.get("/api/items")
async def list_items(
    item_type: Optional[str] = Query("ALL", description="LOST, FOUND, or ALL"),
    category: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    status: Optional[str] = Query("ACTIVE", description="ACTIVE, CLAIMED, or ALL"),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """Lists campus items with multi-facet filters."""
    items_col = get_items_collection()
    results = []

    if items_col is not None:
        try:
            query = {}
            if item_type and item_type.upper() != "ALL":
                query["item_type"] = item_type.upper()
            if status and status.upper() != "ALL":
                query["status"] = status.upper()
            if category:
                query["category"] = category
            if location:
                query["location"] = location
            if search and search.strip():
                # Text regex search on title, description, and tags
                regex = {"$regex": search.strip(), "$options": "i"}
                query["$or"] = [{"title": regex}, {"description": regex}, {"tags": regex}]

            cursor = items_col.find(query).sort("created_at", -1).skip(skip).limit(limit)
            async for doc in cursor:
                results.append(item_doc_to_dict(doc, include_contact=False))
            return {"items": results, "total": len(results)}
        except Exception as e:
            logger.warning(f"Error reading from MongoDB: {e}")

    # Fallback to in-memory store
    filtered = []
    for doc in in_memory_items:
        if item_type and item_type.upper() != "ALL" and doc.get("item_type") != item_type.upper():
            continue
        if status and status.upper() != "ALL" and doc.get("status") != status.upper():
            continue
        if category and doc.get("category") != category:
            continue
        if location and doc.get("location") != location:
            continue
        if search and search.strip():
            q = search.lower().strip()
            title_match = q in doc.get("title", "").lower()
            desc_match = q in doc.get("description", "").lower()
            tags_match = any(q in t.lower() for t in doc.get("tags", []))
            if not (title_match or desc_match or tags_match):
                continue
        filtered.append(item_doc_to_dict(doc, include_contact=False))

    filtered.sort(key=lambda x: x.get("created_at"), reverse=True)
    return {"items": filtered[skip:skip + limit], "total": len(filtered)}

@app.get("/api/items/{item_id}")
async def get_item_by_id(item_id: str):
    """Retrieves item details."""
    items_col = get_items_collection()
    if items_col is not None:
        try:
            doc = await items_col.find_one({"_id": ObjectId(item_id)})
            if doc:
                return item_doc_to_dict(doc, include_contact=False)
        except Exception:
            pass

    for doc in in_memory_items:
        if str(doc.get("_id")) == item_id or str(doc.get("id")) == item_id:
            return item_doc_to_dict(doc, include_contact=False)

    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/api/items/{item_id}/claim")
async def claim_item(item_id: str):
    """
    Marks an item as claimed and reveals the contact details of the reporter.
    """
    items_col = get_items_collection()
    updated_doc = None

    if items_col is not None:
        try:
            doc = await items_col.find_one_and_update(
                {"_id": ObjectId(item_id)},
                {"$set": {"status": "CLAIMED"}},
                return_document=True
            )
            if doc:
                updated_doc = doc
        except Exception as e:
            logger.warning(f"Error claiming item in MongoDB: {e}")

    if not updated_doc:
        for doc in in_memory_items:
            if str(doc.get("_id")) == item_id or str(doc.get("id")) == item_id:
                doc["status"] = "CLAIMED"
                updated_doc = doc
                break

    if not updated_doc:
        raise HTTPException(status_code=404, detail="Item not found")

    return {
        "message": "Item claimed successfully! Contact details revealed below.",
        "item": item_doc_to_dict(updated_doc, include_contact=True)
    }

@app.post("/api/match/scan", response_model=VisualScanResult)
async def visual_matcher_scan(
    image: Optional[UploadFile] = File(None),
    query_text: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    target_type: Optional[str] = Form("ALL")
):
    """
    Standalone 'Visual Matcher' reverse-image scan:
    Allows student to upload an image and/or text to instantly query both Lost and Found items
    without saving a new record into the database.
    """
    if not image and (not query_text or not query_text.strip()):
        raise HTTPException(status_code=400, detail="Please upload a photo or enter a description to search.")

    image_rel_url = None
    saved_file_path = None

    if image and image.filename:
        ext = Path(image.filename).suffix.lower()
        contents = await image.read()
        unique_filename = f"scan_{int(ObjectId().generation_time.timestamp())}_{os.urandom(4).hex()}{ext}"
        saved_file_path = UPLOADS_DIR / unique_filename
        with open(saved_file_path, "wb") as f:
            f.write(contents)
        image_rel_url = f"/uploads/{unique_filename}"

    # Compute query vector
    query_vector = ml_engine.get_fused_embedding(str(saved_file_path) if saved_file_path else None, query_text or "")

    # Execute search
    matches_raw = await find_matches(
        query_vector=query_vector,
        query_item_type="QUERY",
        query_category=category or "Other",
        query_location=location or "Campus",
        target_type=target_type or "ALL",
        limit=9,
        min_threshold=50.0  # Show lookalikes for visual scanner
    )

    matches = [MatchCandidate(**m) for m in matches_raw]

    return VisualScanResult(
        query_image_path=image_rel_url,
        query_text=query_text,
        target_type=target_type or "ALL",
        matches=matches,
        total_found=len(matches)
    )

@app.post("/api/seed")
async def trigger_seed():
    """Manual trigger to re-seed campus sample data."""
    count = await seed_campus_database()
    return {"message": f"Successfully seeded {count} campus items."}

# ----------------- HTML PAGE ROUTES -----------------

@app.get("/")
async def serve_home():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/browse")
async def serve_browse():
    return FileResponse(FRONTEND_DIR / "browse.html")

@app.get("/matcher")
async def serve_matcher():
    return FileResponse(FRONTEND_DIR / "matcher.html")
