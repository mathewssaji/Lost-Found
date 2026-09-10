import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from PIL import Image, ImageDraw, ImageFont

from backend.config import settings, SAMPLE_DIR
from backend.models import create_item_doc
from backend.ml_engine import ml_engine
from backend.vector_search import add_item_to_store

def create_sample_item_image(filename: str, category: str, title: str, bg_color: tuple, accent_color: tuple) -> str:
    """Generates a clean product representation image with PIL."""
    file_path = SAMPLE_DIR / filename
    if file_path.exists():
        return f"/sample_assets/{filename}"

    width, height = 600, 450
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Subtle gradient overlay
    for y in range(height):
        alpha = int(35 * (y / height))
        draw.line([(0, y), (width, y)], fill=(accent_color[0], accent_color[1], accent_color[2], alpha))

    # Inner decorative rounded card
    pad = 25
    draw.rounded_rectangle([pad, pad, width - pad, height - pad], radius=16, outline=accent_color, width=3)

    # Header category pill
    pill_w, pill_h = 160, 36
    draw.rounded_rectangle([45, 45, 45 + pill_w, 45 + pill_h], radius=18, fill=accent_color)
    draw.text((65, 55), category.upper(), fill=(255, 255, 255))

    # Central graphic / icon symbol
    cx, cy = width // 2, height // 2 - 10
    draw.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], fill=(255, 255, 255, 40), outline=accent_color, width=3)
    draw.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=accent_color)

    # Bottom Title & Campus watermark
    draw.text((45, height - 75), title[:40], fill=(255, 255, 255))
    draw.text((45, height - 50), "Campus Lost & Found Verified Item", fill=(200, 200, 220))

    img.save(file_path, "JPEG", quality=90)
    return f"/sample_assets/{filename}"

SAMPLE_ITEMS_DATA = [
    {
        "item_type": "LOST",
        "category": "Electronics",
        "title": "Silver Apple MacBook Air M2 13-inch",
        "description": "Left on table 4 at the Central Library 2nd floor quiet zone. Silver color with a small GitHub Octocat sticker on the bottom left corner of the lid.",
        "location": "Central Library",
        "contact_name": "Alex Rivera",
        "contact_info": "alex.rivera@campus.edu | +1 (555) 234-5678",
        "tags": ["laptop", "macbook", "apple", "silver", "stickers"],
        "filename": "laptop_lost.jpg",
        "bg_color": (30, 41, 59),
        "accent_color": (99, 102, 241)
    },
    {
        "item_type": "FOUND",
        "category": "Electronics",
        "title": "Space Gray / Silver MacBook Air Laptop",
        "description": "Found on a study desk at Central Library 2nd floor near the reading cubes. In clean condition with a sticker on the top shell. Handed to the library help desk.",
        "location": "Central Library",
        "contact_name": "Library Circulation Desk",
        "contact_info": "library-lostfound@campus.edu | (555) 019-2834",
        "tags": ["laptop", "macbook", "computer", "desk"],
        "filename": "laptop_found.jpg",
        "bg_color": (30, 41, 59),
        "accent_color": (79, 70, 229)
    },
    {
        "item_type": "LOST",
        "category": "Bottles",
        "title": "Cobalt Blue Hydro Flask 32oz Water Bottle",
        "description": "Metallic cobalt blue 32oz wide mouth insulated bottle with a black flex cap. Has a subtle dent on the bottom rim and an outdoor hiking sticker.",
        "location": "Sports Complex",
        "contact_name": "Jordan Chen",
        "contact_info": "jordan.c@campus.edu | +1 (555) 876-5432",
        "tags": ["hydroflask", "water bottle", "blue", "gym"],
        "filename": "flask_lost.jpg",
        "bg_color": (12, 74, 96),
        "accent_color": (14, 165, 233)
    },
    {
        "item_type": "FOUND",
        "category": "Bottles",
        "title": "Blue Insulated Metal Hydro Flask with Flex Cap",
        "description": "Found near the basketball bleachers at the Sports Complex. 32oz deep blue bottle with black strap handle.",
        "location": "Sports Complex",
        "contact_name": "Coach Marcus (Gym Office)",
        "contact_info": "athletics-desk@campus.edu | (555) 012-9988",
        "tags": ["water bottle", "blue", "sports", "gym"],
        "filename": "flask_found.jpg",
        "bg_color": (12, 74, 96),
        "accent_color": (2, 132, 199)
    },
    {
        "item_type": "LOST",
        "category": "ID & Cards",
        "title": "Campus Student ID Card - Sarah Jenkins",
        "description": "Computer Science student badge #98231 in a transparent plastic holder with a purple campus lanyard. Lost around lunch hour.",
        "location": "Main Cafeteria",
        "contact_name": "Sarah Jenkins",
        "contact_info": "s.jenkins@campus.edu",
        "tags": ["id card", "student id", "badge", "lanyard"],
        "filename": "id_lost.jpg",
        "bg_color": (76, 29, 149),
        "accent_color": (168, 85, 247)
    },
    {
        "item_type": "FOUND",
        "category": "ID & Cards",
        "title": "Student ID Card with Purple Lanyard",
        "description": "Found on a dining tray at the Main Cafeteria food court. Belongs to a CS student. Deposited with cafeteria security.",
        "location": "Main Cafeteria",
        "contact_name": "Cafeteria Supervisor",
        "contact_info": "dining-security@campus.edu | (555) 011-4455",
        "tags": ["id card", "student card", "cafeteria"],
        "filename": "id_found.jpg",
        "bg_color": (76, 29, 149),
        "accent_color": (147, 51, 234)
    },
    {
        "item_type": "LOST",
        "category": "Electronics",
        "title": "Sony WH-1000XM4 Wireless Headphones (Matte Black)",
        "description": "Black over-ear active noise cancelling headphones in their original zippered fabric case. Forgotten after CS301 lecture in Lab 304.",
        "location": "CS Block",
        "contact_name": "David Miller",
        "contact_info": "dmiller@campus.edu | +1 (555) 345-9876",
        "tags": ["sony", "headphones", "audio", "black"],
        "filename": "headphones_lost.jpg",
        "bg_color": (24, 24, 27),
        "accent_color": (245, 158, 11)
    },
    {
        "item_type": "FOUND",
        "category": "Electronics",
        "title": "Black Noise-Cancelling Over-Ear Headphones",
        "description": "Discovered on the chair row in CS Block Room 304. High-end black headset inside protective zipper pouch.",
        "location": "CS Block",
        "contact_name": "CS Department Front Office",
        "contact_info": "cs-reception@campus.edu | (555) 014-3322",
        "tags": ["headphones", "cs block", "sony", "case"],
        "filename": "headphones_found.jpg",
        "bg_color": (24, 24, 27),
        "accent_color": (217, 119, 6)
    },
    {
        "item_type": "LOST",
        "category": "Keys",
        "title": "Dorm Key Set with Red Honda Car Key & Lanyard",
        "description": "Ring containing two brass dorm room keys, a mailbox key, and a black Honda key fob with a red woven tag.",
        "location": "Hostel Block A",
        "contact_name": "Emily Watson",
        "contact_info": "emily.w@campus.edu | +1 (555) 432-1100",
        "tags": ["keys", "car key", "honda", "dorm"],
        "filename": "keys_lost.jpg",
        "bg_color": (153, 27, 27),
        "accent_color": (239, 68, 68)
    },
    {
        "item_type": "FOUND",
        "category": "Keys",
        "title": "Keyring with Car Fob and Dorm Keys",
        "description": "Found near the entrance lobby benches at Hostel Block A. Contains multiple keys and a red keychain tag.",
        "location": "Hostel Block A",
        "contact_name": "Hostel Warden Office",
        "contact_info": "hostel-a@campus.edu | (555) 019-7711",
        "tags": ["keys", "keychain", "hostel"],
        "filename": "keys_found.jpg",
        "bg_color": (153, 27, 27),
        "accent_color": (220, 38, 38)
    },
    {
        "item_type": "LOST",
        "category": "Bags & Backpacks",
        "title": "Black North Face Surge 31L Backpack",
        "description": "Black nylon backpack with reflective tabs and turquoise zipper pulls. Contains notebooks and stationery.",
        "location": "Student Center",
        "contact_name": "Carlos Gomez",
        "contact_info": "carlos.g@campus.edu | +1 (555) 654-3210",
        "tags": ["backpack", "bag", "north face", "black"],
        "filename": "backpack_lost.jpg",
        "bg_color": (15, 23, 42),
        "accent_color": (16, 185, 129)
    },
    {
        "item_type": "FOUND",
        "category": "Electronics",
        "title": "Texas Instruments TI-84 Plus CE Graphing Calculator",
        "description": "Color screen scientific calculator in mint condition with black slide case. Found in Engineering Annex Room 102.",
        "location": "Engineering Annex",
        "contact_name": "Lab Tech Kevin",
        "contact_info": "engg-lab@campus.edu | (555) 018-4499",
        "tags": ["calculator", "ti-84", "engineering", "math"],
        "filename": "calculator_found.jpg",
        "bg_color": (19, 78, 74),
        "accent_color": (20, 184, 166)
    }
]

async def seed_campus_database():
    """Populates MongoDB and in-memory store with sample items."""
    seeded_count = 0
    now = datetime.now(timezone.utc)

    for i, data in enumerate(SAMPLE_ITEMS_DATA):
        img_rel_url = create_sample_item_image(
            filename=data["filename"],
            category=data["category"],
            title=data["title"],
            bg_color=data["bg_color"],
            accent_color=data["accent_color"]
        )

        full_img_path = SAMPLE_DIR / data["filename"]

        # Compute fused multimodal embedding
        text_content = f"{data['title']} {data['description']}"
        embedding = ml_engine.get_fused_embedding(str(full_img_path), text_content)

        # Distribute created_at times across past few days
        time_offset = timedelta(hours=i * 5 + 2)
        item_time = now - time_offset

        doc = create_item_doc(
            item_type=data["item_type"],
            title=data["title"],
            description=data["description"],
            category=data["category"],
            location=data["location"],
            contact_info=data["contact_info"],
            contact_name=data["contact_name"],
            image_path=img_rel_url,
            embedding=embedding,
            tags=data["tags"],
            status="ACTIVE"
        )
        doc["created_at"] = item_time
        doc["updated_at"] = item_time

        await add_item_to_store(doc)
        seeded_count += 1

    return seeded_count
