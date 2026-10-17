from fastapi import APIRouter, Depends, Body
from sqlmodel import Session, select
from app.core.db import get_session
from app.core.config import settings
from app.models.entities import Job, Repository

router = APIRouter()

@router.get("/health")
def health_check():
    configured = bool(settings.GROQ_API_KEY or settings.GEMINI_API_KEY)
    return {
        "status": "healthy",
        "service": "AI Career Coach Backend",
        "version": "1.0.0",
        "gemini_configured": configured,
        "llm_configured": configured,
    }

@router.get("/stats")
def get_stats(session: Session = Depends(get_session)):
    job_count = len(session.exec(select(Job)).all())
    repo_count = len(session.exec(select(Repository)).all())
    configured = bool(settings.GROQ_API_KEY or settings.GEMINI_API_KEY)
    return {
        "jobs_count": job_count,
        "repositories_count": repo_count,
        "gemini_configured": configured,
        "llm_configured": configured,
    }

@router.get("/config")
def get_config():
    """Return runtime configuration status."""
    key = settings.GROQ_API_KEY or settings.GEMINI_API_KEY
    provider_name = "Groq" if settings.GROQ_API_KEY else ("Gemini" if settings.GEMINI_API_KEY else "None")
    masked = f"{key[:4]}...{key[-4:]} ({provider_name})" if len(key) >= 10 else ("Configured" if key else "Not Configured")
    from app.services.llm_provider import get_provider
    return {
        "gemini_configured": bool(key),
        "llm_configured": bool(key),
        "masked_key": masked if key else None,
        "provider": provider_name,
        "llm": get_provider().get_model_info()
    }

@router.post("/config/test-llm")
def test_llm():
    """Live call to provider to prove real LLM responses work."""
    from app.services.llm_provider import get_provider
    r = get_provider().generate_json('Return JSON with format: {"ok": true, "message": "hello from LLM"}')
    return {"success": r.data is not None, "model": r.model, "response": r.data, "error": r.error}

@router.post("/config/gemini-key")
def update_gemini_key(payload: dict = Body(...)):
    """Update API key (Gemini or Groq) in memory and persist in .env file."""
    new_key = payload.get("gemini_api_key", "").strip() or payload.get("groq_api_key", "").strip()
    is_groq = new_key.startswith("gsk_")
    if is_groq:
        settings.GROQ_API_KEY = new_key
        env_var = "GROQ_API_KEY"
    else:
        settings.GEMINI_API_KEY = new_key
        env_var = "GEMINI_API_KEY"
    
    # Also update root and backend .env file
    try:
        import os
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        root_dir = os.path.dirname(backend_dir)
        for env_path in [os.path.join(backend_dir, ".env"), os.path.join(root_dir, ".env")]:
            lines = []
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = [line for line in f.readlines() if not line.startswith(f"{env_var}=")]
            lines.append(f"{env_var}={new_key}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
    except Exception as e:
        print(f"Warning: could not update .env: {e}")

    return {
        "success": True,
        "gemini_configured": bool(new_key),
        "llm_configured": bool(new_key),
        "provider": "groq" if is_groq else "gemini",
        "message": f"{'Groq' if is_groq else 'Gemini'} API key updated successfully."
    }
