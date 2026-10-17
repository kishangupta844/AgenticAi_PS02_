import json
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Header, HTTPException, Depends, BackgroundTasks
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.entities import WebhookEvent
from app.services.change_detector import ChangeDetectionService

router = APIRouter()

@router.post("/github")
async def receive_github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    x_github_event: Optional[str] = Header("push", alias="X-GitHub-Event"),
    session: Session = Depends(get_session)
):
    """
    GitHub Webhook Ingestion Endpoint (Module E / Phase 5):
    1. Validates HMAC-SHA256 signature against configured webhook secret.
    2. Enforces delivery deduplication via X-GitHub-Delivery header (returns 409 Conflict on duplicate).
    3. Persists delivery event tracking in database.
    4. Extracts changed commit files and triggers automated reassessment & audit history updates.
    """
    raw_body = await request.body()

    # Step 1: Validate HMAC Signature
    if not ChangeDetectionService.verify_signature(raw_body, x_hub_signature_256):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing webhook signature (X-Hub-Signature-256 mismatch)."
        )

    # Step 2: Delivery ID check & Deduplication
    delivery_id = x_github_delivery or f"synthetic-{hash(raw_body)}"
    existing_event = session.exec(select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id)).first()
    if existing_event:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate delivery ignored. Event '{delivery_id}' was already received with status '{existing_event.status}'."
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Malformed JSON payload: {str(e)}")

    repo_full_name = payload.get("repository", {}).get("full_name", "unknown")
    sender_login = payload.get("sender", {}).get("login")
    after_sha = payload.get("after")

    # Step 3: Record received WebhookEvent
    event = WebhookEvent(
        delivery_id=delivery_id,
        event_type=x_github_event or "push",
        repository_full_name=repo_full_name,
        sender_login=sender_login,
        commit_sha=after_sha,
        status="processing"
    )
    session.add(event)
    session.commit()
    session.refresh(event)

    # Step 4: Handle Event (if push, process changed files & reassess)
    if x_github_event == "push":
        result = await ChangeDetectionService.process_push_event(session, delivery_id, payload)
        event.status = result.get("status", "completed")
        event.completed_at = datetime.now(timezone.utc)
        session.add(event)
        session.commit()

        return {
            "delivery_id": delivery_id,
            "event": x_github_event,
            "status": event.status,
            "details": result
        }

    # Non-push events (ping, etc.)
    event.status = "completed"
    event.completed_at = datetime.now(timezone.utc)
    session.add(event)
    session.commit()

    return {
        "delivery_id": delivery_id,
        "event": x_github_event,
        "status": "completed",
        "message": f"Event '{x_github_event}' acknowledged."
    }

@router.get("/events")
def list_webhook_events(session: Session = Depends(get_session)):
    """List recent webhook deliveries and processing statuses."""
    events = session.exec(select(WebhookEvent).order_by(WebhookEvent.created_at.desc())).all()
    return events

@router.post("/poll/{repo_id}")
async def poll_repository(repo_id: int, session: Session = Depends(get_session)):
    """
    Polling fallback endpoint:
    Checks upstream repository commit SHA and triggers change detection & reassessment if updated.
    """
    result = await ChangeDetectionService.poll_repository_for_changes(session, repo_id)
    return result
