from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from bson import ObjectId

def item_doc_to_dict(doc: Dict[str, Any], include_contact: bool = True, include_embedding: bool = False) -> Dict[str, Any]:
    """Convert MongoDB BSON document to JSON-friendly dictionary."""
    if not doc:
        return {}
    
    res = {
        "id": str(doc.get("_id")),
        "item_type": doc.get("item_type", "LOST"),
        "title": doc.get("title", ""),
        "description": doc.get("description", ""),
        "category": doc.get("category", "Other"),
        "location": doc.get("location", "Campus"),
        "image_path": doc.get("image_path", ""),
        "status": doc.get("status", "ACTIVE"),
        "created_at": doc.get("created_at", datetime.now(timezone.utc)),
        "tags": doc.get("tags", []),
    }
    
    if include_contact:
        res["contact_name"] = doc.get("contact_name", "Anonymous")
        res["contact_info"] = doc.get("contact_info", "Hidden until claimed")
    else:
        res["contact_name"] = "Hidden"
        res["contact_info"] = "Claim this item to reveal contact details"
        
    if include_embedding and "embedding" in doc:
        res["embedding"] = doc["embedding"]
        
    return res

def create_item_doc(
    item_type: str,
    title: str,
    description: str,
    category: str,
    location: str,
    contact_info: str,
    contact_name: Optional[str] = None,
    image_path: Optional[str] = None,
    embedding: Optional[List[float]] = None,
    tags: Optional[List[str]] = None,
    status: str = "ACTIVE"
) -> Dict[str, Any]:
    """Construct a clean MongoDB document for insertion."""
    now = datetime.now(timezone.utc)
    return {
        "item_type": item_type.upper(),
        "title": title.strip(),
        "description": description.strip(),
        "category": category,
        "location": location,
        "contact_info": contact_info.strip(),
        "contact_name": contact_name.strip() if contact_name else "Campus Member",
        "image_path": image_path or "",
        "status": status.upper(),
        "tags": tags or [],
        "embedding": embedding or [],
        "created_at": now,
        "updated_at": now
    }
