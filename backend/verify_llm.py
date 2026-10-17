"""End-to-end check that REAL Gemini responses are used. Run: python verify_llm.py"""
from fastapi.testclient import TestClient
from app.main import app

JOB = """Backend Engineer Intern
Company: Apex
- Build REST APIs using FastAPI and Python.
- Experience with SQL databases (PostgreSQL preferred).
- Write automated tests and CI pipelines.
- Package services with Docker."""

with TestClient(app) as c:
    r = c.post("/api/v1/config/test-llm").json()
    print("LLM live:", r)
    assert r["success"], r
    job = c.post("/api/v1/jobs/import", json={"raw_text": JOB}).json()
    print("Job:", job["title"], [x["title"] for x in job["requirements"]])
    repo = c.post("/api/v1/repos/connect", json={"full_name": "tiangolo/fastapi"}).json()
    a = c.post("/api/v1/assessments/run", json={"job_id": job["id"], "repo_id": repo["id"]}).json()
    print("Summary:", a["summary"])
    for s in a["skill_assessments"]:
        print(f"- {s['requirement_title']}: {s['status']} llm={s['llm_used']} model={s['llm_model']} cites={len(s['citations'])}")
        print("   ", s["reason"][:140])
