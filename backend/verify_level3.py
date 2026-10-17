import httpx

def verify_level3():
    print("Testing Repository Connection and Line Range Evidence Extraction...")
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
        # 1. Connect a repository
        repo_payload = {
            "full_name": "tiangolo/fastapi",
            "default_branch": "master"
        }
        resp = client.post("/api/v1/repos/connect", json=repo_payload)
        assert resp.status_code == 200, f"Connect repo failed: {resp.text}"
        repo_data = resp.json()
        repo_id = repo_data["id"]
        commit_sha = repo_data["latest_commit_sha"]
        print(f"Connected Repo: ID={repo_id}, FullName='{repo_data['full_name']}'")
        print(f"Resolved Commit SHA: {commit_sha}")
        assert commit_sha is not None and len(commit_sha) >= 10

        # 2. Inspect repository tree
        inspect_resp = client.get(f"/api/v1/repos/{repo_id}/inspect")
        assert inspect_resp.status_code == 200, f"Inspect repo failed: {inspect_resp.text}"
        inspect_data = inspect_resp.json()
        print(f"Repo Tree Files Count: {inspect_data['tree_file_count']}")
        print(f"Sample paths: {inspect_data['sample_files'][:4]}")

        # 3. Collect evidence with line range citations
        evidence_resp = client.get(f"/api/v1/repos/{repo_id}/evidence?keywords=FastAPI,SQLModel,Docker")
        assert evidence_resp.status_code == 200, f"Collect evidence failed: {evidence_resp.text}"
        evidence_data = evidence_resp.json()
        collected = evidence_data["collected_evidences"]
        print(f"\nCollected {len(collected)} Code Evidence Citations:")

        for ev in collected[:3]:
            print(f"  - [{ev['matched_keyword']}] {ev['file_path']} (Lines: {ev['start_line']} to {ev['end_line']})")
            print(f"    Commit SHA: {ev['commit_sha']}")
            print(f"    GitHub URL: {ev['github_url']}")
            assert f"#L{ev['start_line']}-L{ev['end_line']}" in ev['github_url']
            assert ev['commit_sha'] in ev['github_url']

    print("\nALL LEVEL 3 REPO INSPECTION & LINE-RANGE CITATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    verify_level3()
