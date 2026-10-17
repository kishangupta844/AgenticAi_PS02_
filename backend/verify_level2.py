import asyncio
import httpx

sample_job_text = """
Job Title: Senior Backend AI Engineer
Company: CloudScale AI
Location: Remote (US / Global)

About the Role:
We are looking for a Senior Backend AI Engineer to build high-performance data processing pipelines and API microservices.

Responsibilities:
- Build and maintain REST APIs using Python and FastAPI.
- Design normalized relational databases using PostgreSQL and SQLAlchemy.
- Containerize services with Docker and manage deployments on Kubernetes.
- Write unit and integration tests for all backend services.
- Experience with Git version control and GitHub actions CI/CD workflows.
- Knowledge of Redis caching and distributed task queues is preferred.
"""

def verify_level2():
    print("Testing Job Import with raw text payload...")
    with httpx.Client(base_url="http://127.0.0.1:8000") as client:
        # 1. Import job
        resp = client.post(
            "/api/v1/jobs/import",
            json={
                "raw_text": sample_job_text,
                "source_url": "https://example.com/careers/backend-ai-engineer"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        job_id = data["id"]
        print(f"Imported Job successfully: ID={job_id}, Title='{data['title']}', Company='{data['company']}'")
        print(f"Extracted {len(data['requirements'])} structured requirements:")
        for r in data["requirements"]:
            print(f"  - [{r['category']}] {r['title']} ({r['requirement_type']}, weight={r['weight']})")
            print(f"    Snippet: \"{r['source_snippet']}\"")
            assert len(r["source_snippet"]) > 0, "Source snippet must not be empty (traceability invariant)!"

        # 2. Query job by ID
        get_resp = client.get(f"/api/v1/jobs/{job_id}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        assert fetched["id"] == job_id
        assert len(fetched["requirements"]) == len(data["requirements"])
        print(f"Successfully fetched Job {job_id} from GET /api/v1/jobs/{job_id}")

        # 3. List jobs
        list_resp = client.get("/api/v1/jobs/")
        assert list_resp.status_code == 200
        jobs_list = list_resp.json()
        print(f"Total jobs currently in DB: {len(jobs_list)}")

    print("\nALL LEVEL 2 JOB EXTRACTION & TRACEABILITY CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    verify_level2()
