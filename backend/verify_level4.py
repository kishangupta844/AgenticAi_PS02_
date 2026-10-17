import os
import sys
import httpx

# Ensure backend directory is in sys.path
backend_path = os.path.dirname(os.path.abspath(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

def verify_level4():
    print("Testing Level 4: End-to-End Skill Assessment, Citation Binding & Gap Analysis...")

    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Health check
    res = client.get("/api/v1/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print("Health check OK!")

    # 2. Import a test job with FastAPI and Docker requirements
    job_payload = {
        "raw_text": """
Job Title: Principal Backend Architect
Company: NextGen Cloud Solutions
Requirements:
- Strong hands-on experience building web APIs with FastAPI and Python.
- Proven experience deploying scalable applications with Docker.
- Expertise in Kubernetes cluster orchestration.
- Familiarity with Rust systems programming.
""",
        "source_url": "https://example.com/careers/principal-architect"
    }

    job_res = client.post("/api/v1/jobs/import", json=job_payload)
    assert job_res.status_code == 200, f"Job import failed: {job_res.text}"
    job_data = job_res.json()
    job_id = job_data["id"]
    print(f"Created Job {job_id}: '{job_data['title']}' with {len(job_data['requirements'])} requirements.")

    # 3. Connect a repository (tiangolo/fastapi)
    repo_res = client.post("/api/v1/repos/connect", json={
        "full_name": "tiangolo/fastapi",
        "default_branch": "master"
    })
    assert repo_res.status_code == 200, f"Repo connect failed: {repo_res.text}"
    repo_data = repo_res.json()
    repo_id = repo_data["id"]
    print(f"Connected Repository {repo_id}: '{repo_data['full_name']}'")

    # 4. Trigger Assessment & Gap Analysis Run
    print("\nRunning Assessment & Gap Analysis via POST /api/v1/assessments/run ...")
    assess_res = client.post("/api/v1/assessments/run", json={
        "job_id": job_id,
        "repo_id": repo_id
    })
    assert assess_res.status_code == 200, f"Assessment run failed: {assess_res.text}"
    report = assess_res.json()

    print(f"\n--- Assessment Report Summary ---")
    summary = report["summary"]
    print(f"Total Skills Assessed: {summary['total_skills']}")
    print(f"MET: {summary['met']} | PARTIAL: {summary['partial']} | UNMET: {summary['unmet']}")
    print(f"Overall Match Percentage: {summary['overall_match_percentage']}%")
    print(f"Weighted Score: {summary['weighted_score']}")

    assert summary["total_skills"] >= 3
    assert summary["met"] + summary["partial"] + summary["unmet"] == summary["total_skills"]

    # 5. Verify Individual Skill Assessments & Citations
    print(f"\n--- Skill Evaluations & Citations ---")
    for skill in report["skill_assessments"]:
        print(f"\nRequirement: [{skill['category']}] {skill['requirement_title']}")
        print(f"  Status: {skill['status'].upper()} (Confidence: {skill['confidence_score']})")
        print(f"  Reason: {skill['reason']}")
        if skill["citations"]:
            print(f"  Citations ({len(skill['citations'])}):")
            for cit in skill["citations"]:
                print(f"    - {cit['file_path']}#L{cit['start_line']}-L{cit['end_line']}")
                print(f"      URL: {cit['github_url']}")
                assert "#L" in cit["github_url"]
                assert cit["start_line"] >= 1
                assert cit["end_line"] >= cit["start_line"]
        if skill["next_step"]:
            print(f"  Actionable Next Step: {skill['next_step']}")

    # 6. Verify audit history was tracked
    first_req_id = report["skill_assessments"][0]["requirement_id"]
    audit_res = client.get(f"/api/v1/assessments/audit/{first_req_id}")
    assert audit_res.status_code == 200
    audits = audit_res.json()
    assert len(audits) >= 1
    print(f"\nAudit History for Requirement {first_req_id}: logged {len(audits)} event(s) successfully.")

    # 7. Verify GET /api/v1/assessments/job/{job_id}
    job_assess_res = client.get(f"/api/v1/assessments/job/{job_id}")
    assert job_assess_res.status_code == 200
    job_assessments = job_assess_res.json()
    assert len(job_assessments) >= 1
    print(f"Retrieved saved assessments for Job {job_id} successfully.")

    print("\n=================================================================")
    print("ALL LEVEL 4 END-TO-END ASSESSMENT & GAP ANALYSIS CHECKS PASSED!")
    print("=================================================================\n")

if __name__ == "__main__":
    verify_level4()
