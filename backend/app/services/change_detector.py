import hmac
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.core.config import settings
from app.models.entities import Repository, Job, Requirement, Assessment, Citation, AuditHistory, WebhookEvent
from app.services.github_scanner import GitHubScannerService
from app.services.assessment_engine import AssessmentEngineService

class ChangeDetectionService:
    """
    Webhook & Change Detection Service:
    - HMAC-SHA256 signature verification (X-Hub-Signature-256)
    - Delivery deduplication (X-GitHub-Delivery)
    - Changed files extraction from push commits
    - Incremental / Reassessment trigger for affected skills & jobs
    - Polling fallback to detect latest commits
    """

    @classmethod
    def verify_signature(cls, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """
        Verify GitHub HMAC-SHA256 signature against settings.GITHUB_WEBHOOK_SECRET.
        """
        if not signature_header:
            return False
        
        prefix = "sha256="
        if not signature_header.startswith(prefix):
            return False
        
        expected_sig = signature_header[len(prefix):]
        secret = settings.GITHUB_WEBHOOK_SECRET.encode("utf-8")
        computed_sig = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
        
        return hmac.compare_digest(computed_sig, expected_sig)

    @classmethod
    def extract_changed_files(cls, push_payload: Dict[str, Any]) -> List[str]:
        """
        Extract unique added, modified, or removed files across commits in a push payload.
        """
        changed = set()
        commits = push_payload.get("commits", [])
        for commit in commits:
            for f in commit.get("added", []):
                changed.add(f)
            for f in commit.get("modified", []):
                changed.add(f)
            for f in commit.get("removed", []):
                changed.add(f)
        return sorted(list(changed))

    @classmethod
    async def process_push_event(
        cls,
        session: Session,
        delivery_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a verified GitHub push event:
        1. Check repository registration in system.
        2. Update repo latest_commit_sha.
        3. Identify changed files.
        4. Trigger reassessments for any jobs evaluated against this repository.
        5. Record status changes in AuditHistory and complete the WebhookEvent.
        """
        repo_data = payload.get("repository", {})
        full_name = repo_data.get("full_name")
        after_sha = payload.get("after")

        # Find repository in DB
        repo = session.exec(select(Repository).where(Repository.full_name == full_name)).first()
        if not repo:
            # We don't track this repo, record as ignored
            return {
                "status": "ignored",
                "message": f"Repository '{full_name}' is not connected to AI Career Coach."
            }

        if after_sha and after_sha != "0000000000000000000000000000000000000000":
            repo.latest_commit_sha = after_sha
            session.add(repo)
            session.flush()

        changed_files = cls.extract_changed_files(payload)

        # Find jobs that have assessments against this repo
        assessments = session.exec(select(Assessment).where(Assessment.repo_id == repo.id)).all()
        job_ids = set()
        for a in assessments:
            if a.requirement and a.requirement.job_id:
                job_ids.add(a.requirement.job_id)

        # If no previous assessments, check all jobs with requirements
        if not job_ids:
            all_reqs = session.exec(select(Requirement)).all()
            job_ids = {r.job_id for r in all_reqs}

        # Inspect new tree
        tree = await GitHubScannerService.get_repo_tree(repo.full_name, repo.latest_commit_sha or "main")
        tree_paths = [item["path"] for item in tree]
        content_cache: Dict[str, Optional[str]] = {}

        reassessed_jobs_count = 0
        total_transitions = 0

        for j_id in job_ids:
            reqs = session.exec(select(Requirement).where(Requirement.job_id == j_id)).all()
            if not reqs:
                continue

            for req in reqs:
                eval_result = await AssessmentEngineService.evaluate_requirement(req, repo, tree_paths, content_cache)

                existing = session.exec(
                    select(Assessment).where(
                        Assessment.requirement_id == req.id,
                        Assessment.repo_id == repo.id
                    )
                ).first()

                prev_status = existing.status.value if existing else None

                if existing:
                    existing.status = eval_result.status
                    existing.confidence_score = eval_result.confidence_score
                    existing.reason = eval_result.reason
                    existing.evaluated_at = datetime.now(timezone.utc)
                    session.add(existing)
                    session.flush()
                    assessment_record = existing

                    # Refresh citations
                    old_cits = session.exec(select(Citation).where(Citation.assessment_id == assessment_record.id)).all()
                    for old_c in old_cits:
                        session.delete(old_c)
                else:
                    assessment_record = Assessment(
                        requirement_id=req.id,
                        repo_id=repo.id,
                        status=eval_result.status,
                        confidence_score=eval_result.confidence_score,
                        reason=eval_result.reason
                    )
                    session.add(assessment_record)
                    session.flush()

                for cit in eval_result.citations:
                    new_cit = Citation(
                        assessment_id=assessment_record.id,
                        file_path=cit.file_path,
                        start_line=cit.start_line,
                        end_line=cit.end_line,
                        commit_sha=cit.commit_sha,
                        snippet_text=cit.snippet_text,
                        github_url=cit.github_url
                    )
                    session.add(new_cit)

                # Record status audit history
                if prev_status != eval_result.status.value:
                    audit = AuditHistory(
                        requirement_id=req.id,
                        previous_status=prev_status,
                        new_status=eval_result.status.value,
                        trigger_event="github_webhook_push",
                        commit_sha=repo.latest_commit_sha
                    )
                    session.add(audit)
                    total_transitions += 1

            reassessed_jobs_count += 1

        session.commit()

        return {
            "status": "completed",
            "repository": full_name,
            "commit_sha": repo.latest_commit_sha,
            "changed_files_count": len(changed_files),
            "changed_files": changed_files,
            "reassessed_jobs_count": reassessed_jobs_count,
            "status_transitions_recorded": total_transitions
        }

    @classmethod
    async def poll_repository_for_changes(
        cls,
        session: Session,
        repo_id: int
    ) -> Dict[str, Any]:
        """
        Polling fallback: compares latest remote commit with DB commit.
        If different, triggers synthetic reassessment pipeline.
        """
        repo = session.exec(select(Repository).where(Repository.id == repo_id)).first()
        if not repo:
            return {"error": "Repository not found"}

        # Fetch latest commit from GitHub API
        latest_sha = await GitHubScannerService.get_latest_commit_sha(repo.full_name, repo.default_branch)
        if not latest_sha:
            return {"error": "Unable to resolve remote commit SHA"}

        old_sha = repo.latest_commit_sha

        if old_sha and old_sha == latest_sha:
            return {
                "changed": False,
                "repository": repo.full_name,
                "current_sha": latest_sha,
                "message": "Repository is already at latest commit."
            }

        # Update and trigger pipeline
        repo.latest_commit_sha = latest_sha
        session.add(repo)
        session.commit()

        # Synthetic push payload
        synth_payload = {
            "repository": {"full_name": repo.full_name},
            "after": latest_sha,
            "commits": [{"added": [], "modified": ["(polled_change)"], "removed": []}]
        }

        synthetic_delivery = f"poll-{repo.id}-{int(datetime.now(timezone.utc).timestamp())}"
        result = await cls.process_push_event(session, synthetic_delivery, synth_payload)
        result["polled_update"] = True
        result["previous_sha"] = old_sha
        result["new_sha"] = latest_sha
        return result
