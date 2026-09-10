import asyncio
from starlette.testclient import TestClient
from backend.app import app
from backend.config import SAMPLE_DIR

client = TestClient(app)

def test_api_suite():
    print("Testing API Suite...")

    # 1. Health
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print("✓ Health Check: OK", res.json())

    # 2. Stats
    res = client.get("/api/stats")
    assert res.status_code == 200, f"Stats failed: {res.text}"
    stats = res.json()
    assert stats["total_active"] > 0, "Stats should show active items"
    print(f"✓ Stats: Total Active={stats['total_active']}, Lost={stats['total_lost']}, Found={stats['total_found']}")

    # 3. List Items
    res = client.get("/api/items?item_type=LOST")
    assert res.status_code == 200
    lost_items = res.json()["items"]
    assert len(lost_items) > 0, "Should have lost items"
    print(f"✓ List Items (LOST): Returned {len(lost_items)} items")

    # 4. Report Item with Image & Cross-Match
    img_path = SAMPLE_DIR / "flask_lost.jpg"
    with open(img_path, "rb") as f:
        res = client.post(
            "/api/items",
            data={
                "item_type": "LOST",
                "title": "Cobalt Blue Hydro Flask 32oz",
                "description": "Lost near bleachers in Sports Complex, dark blue metal bottle with cap",
                "category": "Bottles",
                "location": "Sports Complex",
                "contact_info": "tester@campus.edu",
                "contact_name": "Test Student",
                "tags": "bottle, blue, sports"
            },
            files={"image": ("flask_lost.jpg", f, "image/jpeg")}
        )
    assert res.status_code == 200, f"Report failed: {res.text}"
    create_res = res.json()
    new_item = create_res["item"]
    matches = create_res["matches"]
    print(f"✓ Report Item: Created '{new_item['title']}' (ID: {new_item['id']})")
    print(f"✓ Cross-Match Candidates: {len(matches)} returned")
    for m in matches:
        print(f"   -> Match: {m['item']['title']} | Score: {m['score']}% | HighConf: {m['is_high_confidence']}")

    # 5. Claim Item & Reveal Contact
    item_to_claim = matches[0]["item"]["id"] if matches else new_item["id"]
    res = client.post(f"/api/items/{item_to_claim}/claim")
    assert res.status_code == 200
    claim_res = res.json()
    assert claim_res["item"]["status"] == "CLAIMED"
    assert claim_res["item"]["contact_info"] != "Claim this item to reveal contact details"
    print(f"✓ Claim Item: Successfully revealed contact: {claim_res['item']['contact_name']} ({claim_res['item']['contact_info']})")

    # 6. Visual Matcher Reverse Scan
    with open(img_path, "rb") as f:
        res = client.post(
            "/api/match/scan",
            data={"target_type": "ALL", "query_text": "blue hydroflask bottle"},
            files={"image": ("scan.jpg", f, "image/jpeg")}
        )
    assert res.status_code == 200
    scan_res = res.json()
    print(f"✓ Visual Matcher Scan: Found {len(scan_res['matches'])} visual lookalikes")

    # 7. HTML Page Serving
    for route in ["/", "/browse", "/matcher"]:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} failed"
        assert "<html" in res.text.lower(), f"Route {route} did not return HTML"
        print(f"✓ Route {route}: HTML Served Successfully")

    print("\n>>> ALL API TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_api_suite()
