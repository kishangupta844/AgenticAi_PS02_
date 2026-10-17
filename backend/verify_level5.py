import os
import sys
import json
import hmac
import hashlib
from datetime import datetime

# Ensure backend directory is in sys.path
backend_path = os.path.dirname(os.path.abspath(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

def compute_hmac_sha256(secret: str, payload_bytes: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

def verify_level5():
    print("Testing Level 5: GitHub Webhook Ingestion, HMAC Verification, Deduplication & Reassessment...")

    client = TestClient(app)

    # 1. Setup a connected repo & a test job
    repo_res = client.post("/api/v1/repos/connect", json={
        "full_name": "tiangolo/fastapi",
        "default_branch": "master"
    })
    assert repo_res.status_code == 200
    repo_data = repo_res.json()
    repo_id = repo_data["id"]
    print(f"Connected repository: ID={repo_id}, name='{repo_data['full_name']}'")

    job_res = client.post("/api/v1/jobs/import", json={
        "raw_text": """
Job Title: Lead Web Services Engineer
Required:
- Strong experience with FastAPI and Python microservices.
- Docker containerization.
""",
        "source_url": "https://example.com/lead-web-services"
    })
    assert job_res.status_code == 200
    job_id = job_res.json()["id"]
    print(f"Imported Job: ID={job_id}")

    # Initial assessment run
    init_assess = client.post("/api/v1/assessments/run", json={"job_id": job_id, "repo_id": repo_id})
    assert init_assess.status_code == 200
    initial_summary = init_assess.json()["summary"]
    print(f"Initial Assessment: {initial_summary['met']} MET, {initial_summary['partial']} PARTIAL, {initial_summary['unmet']} UNMET")

    # 2. Test HMAC Security Validation
    payload = {
        "ref": "refs/heads/master",
        "before": "c9f3e8b417a250d4f9b871c890a1b2c3d4e5f678",
        "after": "d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f678",
        "repository": {
            "id": 123456,
            "full_name": "tiangolo/fastapi"
        },
        "commits": [
            {
                "id": "d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f678",
                "message": "Add Dockerfile and production compose service",
                "added": ["Dockerfile", "docker-compose.yml"],
                "modified": ["backend/app/main.py"],
                "removed": []
            }
        ],
        "sender": {
            "login": "octocat"
        }
    }
    raw_payload_bytes = json.dumps(payload).encode("utf-8")

    print("\n--- Testing Webhook HMAC Signature Validation ---")
    # Submitting with invalid signature should return 401
    bad_res = client.post(
        "/api/v1/webhooks/github",
        content=raw_payload_bytes,
        headers={
            "X-Hub-Signature-256": "sha256=invalid_hash_signature",
            "X-GitHub-Delivery": "delivery-test-001",
            "X-GitHub-Event": "push",
            "Content-Type": "application/json"
        }
    )
    assert bad_res.status_code == 401, f"Expected 401 on bad signature, got {bad_res.status_code}"
    print("Invalid HMAC signature correctly rejected with 401 Unauthorized.")

    # 3. Test Valid Webhook Delivery
    valid_sig = compute_hmac_sha256(settings.GITHUB_WEBHOOK_SECRET, raw_payload_bytes)
    delivery_id = f"delivery-{int(datetime.now().timestamp())}"

    print(f"\n--- Submitting Valid Webhook Push Delivery ({delivery_id}) ---")
    good_res = client.post(
        "/api/v1/webhooks/github",
        content=raw_payload_bytes,
        headers={
            "X-Hub-Signature-256": valid_sig,
            "X-GitHub-Delivery": delivery_id,
            "X-GitHub-Event": "push",
            "Content-Type": "application/json"
        }
    )
    assert good_res.status_code == 200, f"Valid delivery failed: {good_res.text}"
    webhook_res_data = good_res.json()
    print(f"Webhook processed: Status='{webhook_res_data['status']}'")
    details = webhook_res_data["details"]
    print(f"Repository: {details['repository']}")
    print(f"Updated Commit SHA: {details['commit_sha']}")
    print(f"Detected Changed Files ({details['changed_files_count']}): {details['changed_files']}")
    print(f"Reassessed Jobs Count: {details['reassessed_jobs_count']}")

    # 4. Test Delivery Deduplication (Idempotency)
    print("\n--- Testing Delivery Deduplication (Idempotency) ---")
    dup_res = client.post(
        "/api/v1/webhooks/github",
        content=raw_payload_bytes,
        headers={
            "X-Hub-Signature-256": valid_sig,
            "X-GitHub-Delivery": delivery_id,
            "X-GitHub-Event": "push",
            "Content-Type": "application/json"
        }
    )
    assert dup_res.status_code == 409, f"Expected 409 Conflict on duplicate delivery, got {dup_res.status_code}"
    print(f"Duplicate delivery correctly rejected with 409 Conflict: {dup_res.json()['detail']}")

    # 5. Verify Webhook Events Log
    events_res = client.get("/api/v1/webhooks/events")
    assert events_res.status_code == 200
    events = events_res.json()
    matching_event = next((e for e in events if e["delivery_id"] == delivery_id), None)
    assert matching_event is not None
    assert matching_event["status"] == "completed"
    print(f"Verified event persisted in DB: delivery_id='{matching_event['delivery_id']}', status='{matching_event['status']}'")

    # 6. Test Polling Fallback Trigger
    print("\n--- Testing Polling Fallback Endpoint (POST /api/v1/webhooks/poll/{repo_id}) ---")
    poll_res = client.post(f"/api/v1/webhooks/poll/{repo_id}")
    assert poll_res.status_code == 200
    poll_data = poll_res.json()
    print(f"Poller result: {poll_data}")

    print("\n=================================================================")
    print("ALL LEVEL 5 WEBHOOK, DEDUPLICATION & CHANGE DETECTION TESTS PASSED!")
    print("=================================================================\n")

if __name__ == "__main__":
    verify_level5()
