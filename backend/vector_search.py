import logging
from typing import List, Dict, Any, Optional
import numpy as np
from bson import ObjectId

from backend.config import settings
from backend.database import get_items_collection, db_manager
from backend.models import item_doc_to_dict
from backend.ml_engine import ml_engine

logger = logging.getLogger("campus_lost_found.vector_search")

# In-memory document cache for offline/local fallback or fast retrieval
in_memory_items: List[Dict[str, Any]] = []

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two normalized vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    a = np.array(v1, dtype=np.float32)
    b = np.array(v2, dtype=np.float32)
    dot = float(np.dot(a, b))
    return max(0.0, min(1.0, dot))

async def find_matches(
    query_vector: List[float],
    query_item_type: str,
    query_category: str,
    query_location: str,
    target_type: Optional[str] = None,
    limit: int = 5,
    min_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Finds candidate matches using MongoDB Atlas $vectorSearch or in-memory cosine fallback.
    - If query_item_type is 'LOST', target is 'FOUND'
    - If query_item_type is 'FOUND', target is 'LOST'
    - If target_type is explicitly specified (e.g. 'ALL'), respect that.
    """
    if min_threshold is None:
        min_threshold = settings.DEFAULT_MATCH_THRESHOLD

    # Determine opposite partition
    if not target_type:
        target_type = "FOUND" if query_item_type.upper() == "LOST" else "LOST"

    items_col = get_items_collection()
    candidates = []

    # 1. Attempt MongoDB Atlas $vectorSearch
    if items_col is not None:
        try:
            filter_spec = {"status": "ACTIVE"}
            if target_type.upper() != "ALL":
                filter_spec["item_type"] = target_type.upper()

            pipeline = [
                {
                    "$vectorSearch": {
                        "index": settings.ATLAS_VECTOR_INDEX_NAME,
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": max(limit * 10, 50),
                        "limit": max(limit * 3, 20),
                        "filter": filter_spec
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "item_type": 1,
                        "title": 1,
                        "description": 1,
                        "category": 1,
                        "location": 1,
                        "contact_name": 1,
                        "contact_info": 1,
                        "image_path": 1,
                        "status": 1,
                        "created_at": 1,
                        "tags": 1,
                        "embedding": 1,
                        "atlas_score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]
            cursor = items_col.aggregate(pipeline)
            async for doc in cursor:
                candidates.append(doc)
            logger.info(f"Atlas $vectorSearch returned {len(candidates)} raw candidates.")
        except Exception as e:
            logger.debug(f"Atlas $vectorSearch not applicable or failed ({e}). Using standard query fallback.")
            candidates = []

    # 2. Fallback: Query MongoDB standard collection if Atlas vector search was not available
    if not candidates and items_col is not None:
        try:
            query = {"status": "ACTIVE"}
            if target_type.upper() != "ALL":
                query["item_type"] = target_type.upper()
            cursor = items_col.find(query)
            async for doc in cursor:
                candidates.append(doc)
        except Exception as e:
            logger.warning(f"Error querying MongoDB ({e}), falling back to in-memory store.")
            candidates = []

    # 3. Fallback: Query in-memory cache if MongoDB is offline
    if not candidates and in_memory_items:
        for doc in in_memory_items:
            if doc.get("status") == "ACTIVE":
                if target_type.upper() == "ALL" or doc.get("item_type") == target_type.upper():
                    candidates.append(doc)

    # 4. Vectorized High-Speed Composite Score Calculation
    scored_matches = []
    if candidates:
        embeddings = [c.get("embedding", []) for c in candidates]
        has_valid_matrix = all(len(emb) == len(query_vector) and len(emb) > 0 for emb in embeddings)

        if has_valid_matrix and len(candidates) > 0:
            matrix = np.array(embeddings, dtype=np.float32)
            q_vec = np.array(query_vector, dtype=np.float32)
            sim_array = np.clip(np.dot(matrix, q_vec), 0.0, 1.0)

            for i, cand in enumerate(candidates):
                vec_sim = float(cand.get("atlas_score", sim_array[i]))
                cand_cat = cand.get("category", "")
                cand_loc = cand.get("location", "")

                final_score, s_vec, s_cat, s_loc, is_high_conf = ml_engine.calculate_composite_score(
                    vec_sim=vec_sim,
                    query_cat=query_category,
                    cand_cat=cand_cat,
                    query_loc=query_location,
                    cand_loc=cand_loc
                )

                item_data = item_doc_to_dict(cand, include_contact=False)
                scored_matches.append({
                    "item": item_data,
                    "score": final_score,
                    "vec_score": s_vec,
                    "cat_score": s_cat,
                    "loc_score": s_loc,
                    "is_high_confidence": is_high_conf,
                    "created_at": cand.get("created_at")
                })
        else:
            # Fallback per-item
            for cand in candidates:
                cand_emb = cand.get("embedding", [])
                vec_sim = float(cand.get("atlas_score", cosine_similarity(query_vector, cand_emb)))
                final_score, s_vec, s_cat, s_loc, is_high_conf = ml_engine.calculate_composite_score(
                    vec_sim=vec_sim,
                    query_cat=query_category,
                    cand_cat=cand.get("category", ""),
                    query_loc=query_location,
                    cand_loc=cand.get("location", "")
                )
                item_data = item_doc_to_dict(cand, include_contact=False)
                scored_matches.append({
                    "item": item_data,
                    "score": final_score,
                    "vec_score": s_vec,
                    "cat_score": s_cat,
                    "loc_score": s_loc,
                    "is_high_confidence": is_high_conf,
                    "created_at": cand.get("created_at")
                })

    # Sort descending by composite confidence score
    scored_matches.sort(key=lambda m: m["score"], reverse=True)

    # Filter by threshold unless user has fewer matches
    filtered = [m for m in scored_matches if m["score"] >= min_threshold]
    if not filtered and scored_matches:
        # Provide top matches even if slightly below threshold so user sees closest items
        filtered = scored_matches[:limit]
    else:
        filtered = filtered[:limit]

    return filtered

async def add_item_to_store(doc: Dict[str, Any]) -> str:
    """Inserts item into MongoDB and updates in-memory cache."""
    items_col = get_items_collection()
    inserted_id = None

    if items_col is not None:
        try:
            res = await items_col.insert_one(doc)
            inserted_id = str(res.inserted_id)
            doc["_id"] = res.inserted_id
        except Exception as e:
            logger.warning(f"Could not insert to MongoDB: {e}")

    if not inserted_id:
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        inserted_id = str(doc["_id"])

    # Update in-memory cache
    in_memory_items.append(doc)
    return inserted_id
