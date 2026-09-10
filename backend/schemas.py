from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ItemBase(BaseModel):
    item_type: str = Field(..., description="'LOST' or 'FOUND'")
    title: str = Field(..., min_length=2, max_length=150)
    description: str = Field(..., min_length=2, max_length=1000)
    category: str = Field(..., description="Item Category")
    location: str = Field(..., description="Campus zone / building")
    contact_info: str = Field(..., description="Email, phone or student ID")
    contact_name: Optional[str] = Field(None, description="Submitter's name")
    tags: Optional[List[str]] = Field(default_factory=list)

class ItemCreate(ItemBase):
    pass

class ItemResponse(BaseModel):
    id: str
    item_type: str
    title: str
    description: str
    category: str
    location: str
    contact_name: Optional[str] = None
    contact_info: Optional[str] = None
    image_path: Optional[str] = None
    status: str = "ACTIVE"
    created_at: datetime
    tags: List[str] = Field(default_factory=list)

class MatchCandidate(BaseModel):
    item: ItemResponse
    score: float = Field(..., description="Final blended confidence score [0, 100%]")
    vec_score: float = Field(..., description="Cosine similarity [0, 1]")
    cat_score: float = Field(..., description="Category score (1.0 or 0.2)")
    loc_score: float = Field(..., description="Location score (1.0 or 0.6)")
    is_high_confidence: bool = Field(..., description="True if score >= 82%")

class ItemCreateResult(BaseModel):
    item: ItemResponse
    matches: List[MatchCandidate]
    message: str

class VisualScanResult(BaseModel):
    query_image_path: Optional[str] = None
    query_text: Optional[str] = None
    target_type: str = "ALL"
    matches: List[MatchCandidate]
    total_found: int

class StatsResponse(BaseModel):
    total_active: int
    total_lost: int
    total_found: int
    total_claimed: int
    categories: Dict[str, int]
    locations: Dict[str, int]
    is_mongo_connected: bool
