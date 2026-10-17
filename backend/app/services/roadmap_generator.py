from typing import List, Dict, Any, Optional
from app.models.entities import AssessmentStatus
from app.schemas.assessment import (
    SkillAssessmentResult,
    RoadmapPlan,
    RoadmapPhase,
    RoadmapTask,
    LearningResource
)

class RoadmapGenerator:
    """
    Synthesizes a personalized, realistic 15-Day Implementation Roadmap
    tailored to the person's specific skill gap assessment and target GitHub repository.

    Structure:
    - Phase 1 (Days 1-5): Foundation & Core Architecture Gaps (highest priority unmet/partial skills)
    - Phase 2 (Days 6-10): Advanced Integration, Testing & Data Layer (infrastructure, async, ORMs)
    - Phase 3 (Days 11-15): Production Polish, CI/CD, Documentation & Benchmark Verification

    Each day includes:
    - Concrete coding task referencing the target repo structure
    - Target skill
    - Actionable verification step (e.g. pytest, curl, docker-compose up)
    - Curated learning resources (videos + official docs)
    """

    @classmethod
    def generate_15_day_roadmap(
        cls,
        target_role: str,
        target_repo: str,
        skills: List[SkillAssessmentResult],
        llm_roadmap_data: Optional[Dict[str, Any]] = None
    ) -> RoadmapPlan:
        # Separate gaps by severity
        unmet_skills = [s for s in skills if s.status == AssessmentStatus.UNMET]
        partial_skills = [s for s in skills if s.status == AssessmentStatus.PARTIAL]
        met_skills = [s for s in skills if s.status == AssessmentStatus.MET]

        # Prioritize gaps (unmet first, then partial, sorted by weight descending)
        gaps = sorted(unmet_skills + partial_skills, key=lambda s: (s.status == AssessmentStatus.UNMET, s.weight), reverse=True)
        if not gaps:
            # If candidate met all requirements, roadmap focuses on architecture scale & advanced hardening
            gaps = sorted(skills, key=lambda s: s.weight, reverse=True)

        # Build day schedule (15 days across 3 phases)
        # Phase 1: Days 1-5 (Core Foundations)
        # Phase 2: Days 6-10 (Deep Implementation & Testing)
        # Phase 3: Days 11-15 (Production Readiness, CI & Capstone)

        phase1_tasks: List[RoadmapTask] = []
        phase2_tasks: List[RoadmapTask] = []
        phase3_tasks: List[RoadmapTask] = []

        total_gaps = len(gaps)

        for day in range(1, 16):
            # Select target skill cyclically or by priority
            gap_idx = (day - 1) % max(1, total_gaps)
            active_skill = gaps[gap_idx] if gaps else None
            skill_name = active_skill.requirement_title if active_skill else "Software Engineering Patterns"
            skill_resources = active_skill.resources if active_skill else []

            if day <= 5:
                # Phase 1: Architecture & Core Implementation
                if day == 1:
                    day_title = f"Day 1: Audit & {skill_name} Interface Scaffolding"
                    action_goal = f"Deconstruct role requirements for '{skill_name}' and lay out interface models in {target_repo}."
                    code_task = active_skill.practice_task if active_skill and active_skill.practice_task else f"Create schemas, type definitions, and core contracts for {skill_name}."
                    verif = f"Run linter and verify schemas import without errors in {target_repo}."
                elif day == 2:
                    day_title = f"Day 2: Implement Functional Core for {skill_name}"
                    action_goal = f"Implement primary service layer logic demonstrating {skill_name}."
                    code_task = f"Write the core business logic class/service for {skill_name} with input validation and clean error handling."
                    verif = f"Execute service with a test harness script or interactive CLI."
                elif day == 3:
                    day_title = f"Day 3: Exception Handling & Resilience in {skill_name}"
                    action_goal = f"Harden {skill_name} with structured exceptions and fallback logic."
                    code_task = f"Refactor service to catch domain errors, log contextual traces, and return standardized error objects."
                    verif = f"Trigger failure scenarios (e.g., bad inputs, connection failures) and verify graceful recovery."
                elif day == 4:
                    day_title = f"Day 4: Unit Testing Suite for {skill_name}"
                    action_goal = f"Establish 80%+ test coverage for newly added {skill_name} components."
                    code_task = f"Author comprehensive unit tests mocking external boundaries using pytest or Jest."
                    verif = f"Run test command (e.g. 'pytest -v' or 'npm test') and assert all tests pass."
                else: # day 5
                    day_title = f"Day 5: Milestone Checkpoint & Code Review"
                    action_goal = f"Verify Phase 1 foundation code against {target_role} expectations."
                    code_task = f"Clean up commit history, refactor variable naming, and document API contracts for {skill_name}."
                    verif = f"Create git commit with conventional commit message and inspect git diff."

                phase1_tasks.append(RoadmapTask(
                    day=day,
                    day_title=day_title,
                    target_skill=skill_name,
                    action_goal=action_goal,
                    code_task=code_task,
                    verification_step=verif,
                    recommended_resources=skill_resources[:2]
                ))

            elif day <= 10:
                # Phase 2: Integration & Advanced Work
                if day == 6:
                    day_title = f"Day 6: Deep Integration for {skill_name}"
                    action_goal = f"Connect {skill_name} to database or background pipeline."
                    code_task = f"Integrate data persistence or async messaging layer with {skill_name}."
                    verif = f"Validate persistent read/write operations against SQLite/PostgreSQL/Redis."
                elif day == 7:
                    day_title = f"Day 7: Performance & Async Optimization"
                    action_goal = f"Optimize concurrency and eliminate blocking calls in {skill_name}."
                    code_task = f"Introduce async/await, connection pooling, or batching to reduce latency."
                    verif = f"Benchmark response times under concurrent request loads."
                elif day == 8:
                    day_title = f"Day 8: Integration Testing & Contract Validation"
                    action_goal = f"Verify end-to-end communication across repository services."
                    code_task = f"Write integration tests validating the full workflow from entrypoint to database."
                    verif = f"Execute full integration test runner and verify zero race conditions."
                elif day == 9:
                    day_title = f"Day 9: Security & Input Sanitization"
                    action_goal = f"Protect {skill_name} components against injection and unauthorized access."
                    code_task = f"Add input sanitization, token validation, and rate-limiting middleware."
                    verif = f"Run security checks and probe with boundary edge-cases."
                else: # day 10
                    day_title = f"Day 10: Phase 2 Capstone Integration"
                    action_goal = f"Consolidate advanced features and conduct end-to-end sanity check."
                    code_task = f"Wire all newly developed capabilities into the main application startup pipeline."
                    verif = f"Spin up application server and verify healthy status endpoint."

                phase2_tasks.append(RoadmapTask(
                    day=day,
                    day_title=day_title,
                    target_skill=skill_name,
                    action_goal=action_goal,
                    code_task=code_task,
                    verification_step=verif,
                    recommended_resources=skill_resources[:2]
                ))

            else:
                # Phase 3: Production Readiness & Deployment (Days 11-15)
                if day == 11:
                    day_title = f"Day 11: Containerization & Docker Setup"
                    action_goal = f"Containerize repository for reproducible deployment."
                    code_task = f"Write multi-stage Dockerfile and docker-compose.yml including health checks."
                    verif = f"Run 'docker-compose up --build' and verify container boots cleanly."
                elif day == 12:
                    day_title = f"Day 12: CI/CD Automation Pipeline"
                    action_goal = f"Automate linting, testing, and security scanning on every push."
                    code_task = f"Create GitHub Actions workflow (.github/workflows/ci.yml) running test suite on PRs."
                    verif = f"Simulate CI runner or push branch to verify all workflow jobs succeed."
                elif day == 13:
                    day_title = f"Day 13: Observability, Metrics & Structured Logging"
                    action_goal = f"Equip the project with enterprise observability."
                    code_task = f"Implement structured JSON logging with request correlation IDs and latency timers."
                    verif = f"Inspect log outputs during request processing to confirm structured fields."
                elif day == 14:
                    day_title = f"Day 14: Documentation, Architecture Diagram & README"
                    action_goal = f"Showcase {target_role} competencies clearly in repository documentation."
                    code_task = f"Write comprehensive README.md with architecture overview, setup guide, and design trade-offs."
                    verif = f"Preview README markdown rendering and verify all links and code blocks."
                else: # day 15
                    day_title = f"Day 15: Final Audit & Assessment Rescan"
                    action_goal = f"Rerun AI Career Coach assessment to verify closed skill gaps."
                    code_task = f"Review commit history on GitHub, trigger Poll Repo, and run Full Assessment."
                    verif = f"Confirm target skills transition from Unmet/Partial to Met with high confidence citations."

                phase3_tasks.append(RoadmapTask(
                    day=day,
                    day_title=day_title,
                    target_skill=skill_name,
                    action_goal=action_goal,
                    code_task=code_task,
                    verification_step=verif,
                    recommended_resources=skill_resources[:2]
                ))

        phase1 = RoadmapPhase(
            phase_number=1,
            title="Phase 1: Architecture & Core Implementation (Days 1-5)",
            day_range="Days 1-5",
            focus_skills=[t.target_skill for t in phase1_tasks[:3]],
            tasks=phase1_tasks,
            milestone="Working core services and unit tests demonstrating baseline competency in top gap requirements."
        )

        phase2 = RoadmapPhase(
            phase_number=2,
            title="Phase 2: Deep Integration, Concurrency & Data Flow (Days 6-10)",
            day_range="Days 6-10",
            focus_skills=[t.target_skill for t in phase2_tasks[:3]],
            tasks=phase2_tasks,
            milestone="Production-grade asynchronous workflows, database integration, and end-to-end integration tests."
        )

        phase3 = RoadmapPhase(
            phase_number=3,
            title="Phase 3: Production Hardening, CI/CD & Final Verification (Days 11-15)",
            day_range="Days 11-15",
            focus_skills=[t.target_skill for t in phase3_tasks[:3]],
            tasks=phase3_tasks,
            milestone="Dockerized deployment, automated CI pipeline, enterprise documentation, and verified 'Met' readiness."
        )

        unmet_count = len(unmet_skills)
        partial_count = len(partial_skills)
        summary = (
            f"Tailored 15-day implementation roadmap targeting {unmet_count} unmet skill gaps and {partial_count} partial areas in '{target_repo}' "
            f"to meet hiring standards for {target_role}."
        )

        return RoadmapPlan(
            title=f"15-Day Implementation Roadmap for {target_role}",
            target_role=target_role,
            target_repo=target_repo,
            duration_days=15,
            summary=summary,
            phases=[phase1, phase2, phase3],
            expected_outcome=f"Elevate candidate readiness to 'Competitive' or 'Strong' by transforming identified gaps into verified GitHub code citations."
        )
