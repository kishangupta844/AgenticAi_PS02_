import os
import re
import json
from typing import List, Dict, Any, Optional
from sqlmodel import Session

from app.models.entities import Requirement, Repository, AssessmentStatus, Job
from app.schemas.assessment import CitationItem, SkillAssessmentResult, AssessmentSummary, LearningResource
from app.services.github_scanner import GitHubScannerService
from app.services.gemini_service import GeminiService
from app.services.resource_finder import ResourceFinderService

class AssessmentEngineService:
    """
    Deterministic Assessment & Gap Analysis Engine.
    Evaluates repository code snapshots against job requirements with deterministic validation:
    - Multi-signal evidence retrieval via requirement aliases / synonyms / imports
    - Code vs README / Dependency declaration separation
    - 1-indexed line-range citation validation
    - Commit SHA binding
    - Role-aware seniority depth rules (intern/junior/mid/senior/lead)
    - Real verified learning resources (YouTube + official docs) & concrete practice task
    - Weighted match percentage calculation
    """

    DEPENDENCY_DOC_FILES = (
        "requirements.txt", "package.json", "setup.py", "pyproject.toml",
        "gemfile", "go.mod", "pom.xml", "cargo.toml", "readme.md", "readme"
    )

    @classmethod
    def is_dependency_or_doc_file(cls, path: str) -> bool:
        norm = path.lower()
        base = os.path.basename(norm)
        return any(base == doc or base.startswith("readme") for doc in cls.DEPENDENCY_DOC_FILES)

    @classmethod
    def validate_citation(
        cls,
        citation: CitationItem,
        tree_paths: List[str],
        file_content: Optional[str] = None,
    ) -> bool:
        # Rule 1: Path must exist in repository snapshot
        if citation.file_path not in tree_paths and not any(p.endswith(citation.file_path) for p in tree_paths):
            return False
        # Rule 2: Line numbers must be 1-indexed and valid
        if citation.start_line < 1 or citation.end_line < citation.start_line:
            return False
        # Rule 3: Commit SHA must be valid
        if not citation.commit_sha or len(citation.commit_sha) < 7:
            return False
        # Rule 4: Excerpt must be the real file text at those lines
        if file_content is not None:
            lines = file_content.splitlines()
            if citation.end_line > len(lines):
                return False
            actual = "\n".join(lines[citation.start_line - 1:citation.end_line])
            if citation.snippet_text.strip() != actual.strip():
                return False
        return True

    @classmethod
    async def ensure_requirement_aliases(
        cls,
        requirements: List[Requirement],
        session: Optional[Session] = None
    ) -> Dict[int, List[str]]:
        """
        Retrieves or generates cached aliases for all requirements in ONE call.
        """
        needed = []
        result_map: Dict[int, List[str]] = {}

        for req in requirements:
            if req.aliases:
                try:
                    result_map[req.id] = json.loads(req.aliases)
                    continue
                except Exception:
                    pass
            needed.append({"id": req.id, "title": req.title, "category": req.category})

        if needed:
            expansions = await GeminiService.expand_requirements_aliases(needed)
            for req in requirements:
                if req.id not in result_map:
                    tokens = expansions.get(req.title)
                    if not tokens:
                        clean_words = re.findall(r'[A-Za-z0-9+#]+', req.title)
                        tokens = list(set([req.title] + clean_words))
                    result_map[req.id] = tokens
                    req.aliases = json.dumps(tokens)
                    if session:
                        session.add(req)
            if session:
                try:
                    session.commit()
                except Exception as e:
                    print(f"Failed to commit aliases: {e}")

        return result_map

    @classmethod
    async def extract_evidence_for_requirement(
        cls,
        requirement: Requirement,
        repo: Repository,
        tree_paths: List[str],
        aliases: List[str],
        content_cache: Dict[str, Optional[str]]
    ) -> Dict[str, List[CitationItem]]:
        """
        Searches repo using multi-signal aliases across imports, declarations, and code.
        """
        candidate_extensions = (
            ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
            ".sql", ".yml", ".yaml", "Dockerfile", "requirements.txt", "package.json"
        )

        code_snippets: List[CitationItem] = []
        doc_dep_snippets: List[CitationItem] = []
        seen_keys = set()

        # Deduplicate and sort search terms (longer terms first)
        search_terms = sorted(list(set([requirement.title] + aliases)), key=len, reverse=True)
        term_lower_set = {t.lower() for t in search_terms if len(t) >= 3}
        manifest_names = {"requirements.txt", "pyproject.toml", "package.json", "dockerfile", "docker-compose.yml", "setup.py"}

        scored_candidates = []
        for path in tree_paths:
            plow = path.lower()
            if not any(plow.endswith(ext) or plow == ext for ext in candidate_extensions):
                continue
            # Deprioritize github issue/discussion templates, docs translations, and vendor dirs
            is_github_meta = plow.startswith(".github/") or "/.github/" in plow
            is_doc = any(d in plow for d in ("/docs/", "\\docs\\", "docs/", "docs\\", "docs_src/"))
            is_test = plow.startswith("test") or "/tests/" in plow or "\\tests\\" in plow
            base = os.path.basename(plow)

            score = 0
            # True root manifests
            if (base in manifest_names or plow in manifest_names) and not is_github_meta:
                score += 120
            if any(t in base for t in term_lower_set):
                score += 70
            elif any(t in plow for t in term_lower_set):
                score += 40

            if not is_doc and not is_test and not is_github_meta:
                score += 50  # Core application source code
            elif is_test:
                score += 20  # Tests are useful
            elif is_github_meta:
                score -= 50  # Templates/workflows heavily deprioritized unless keyword is CI
            else:
                score -= 30  # Docs heavily deprioritized

            scored_candidates.append((score, path))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        candidate_paths = [p for _, p in scored_candidates[:10]]

        for path in candidate_paths:
            if path not in content_cache:
                content_cache[path] = await GitHubScannerService.fetch_file_content(
                    repo.full_name, path, repo.latest_commit_sha or "main"
                )
            content = content_cache[path]
            if content:
                for term in search_terms:
                    found = GitHubScannerService.extract_line_range_snippets(
                        code_text=content,
                        keyword=term,
                        file_path=path,
                        commit_sha=repo.latest_commit_sha or "HEAD",
                        owner_repo=repo.full_name
                    )
                    for item in found:
                        unique_key = (item.file_path, item.start_line, item.end_line)
                        if unique_key in seen_keys:
                            continue
                        seen_keys.add(unique_key)

                        is_dep_doc = cls.is_dependency_or_doc_file(item.file_path)
                        cit = CitationItem(
                            file_path=item.file_path,
                            start_line=item.start_line,
                            end_line=item.end_line,
                            commit_sha=item.commit_sha,
                            snippet_text=item.snippet_text,
                            github_url=item.github_url,
                            is_dependency_or_doc_only=is_dep_doc
                        )
                        if cls.validate_citation(cit, tree_paths, content):
                            if is_dep_doc:
                                doc_dep_snippets.append(cit)
                            else:
                                code_snippets.append(cit)
                    if len(code_snippets) >= 8:
                        break

        return {
            "code_snippets": code_snippets,
            "doc_dep_snippets": doc_dep_snippets
        }

    @classmethod
    async def evaluate_all_requirements(
        cls,
        job: Job,
        requirements: List[Requirement],
        repo: Repository,
        tree_paths: List[str],
        content_cache: Optional[Dict[str, Optional[str]]] = None,
        session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        End-to-end evaluation for all requirements of a job:
        - 1 call to expand aliases if not cached
        - Multi-signal evidence collection
        - 1 batched LLM evaluation call across all skills
        - Resource finder queries with caching
        - Deterministic fallback if LLM is unavailable
        """
        if content_cache is None:
            content_cache = {}

        # 1. Ensure aliases are cached on requirements
        alias_map = await cls.ensure_requirement_aliases(requirements, session)

        # Parse role profile
        role_prof = {}
        if job.role_profile:
            try:
                role_prof = json.loads(job.role_profile)
            except Exception:
                pass
        seniority = role_prof.get("seniority", "mid")

        # 2. Extract evidence for all requirements
        extracted_evidence: Dict[int, Dict[str, List[CitationItem]]] = {}
        skill_payloads = []

        for req in requirements:
            req_aliases = alias_map.get(req.id, [req.title])
            ev = await cls.extract_evidence_for_requirement(req, repo, tree_paths, req_aliases, content_cache)
            extracted_evidence[req.id] = ev

            skill_payloads.append({
                "requirement_id": req.id,
                "requirement_title": req.title,
                "category": req.category,
                "requirement_type": req.requirement_type.value,
                "job_source_snippet": req.source_snippet,
                "code_snippets": [
                    {"file": c.file_path, "lines": f"{c.start_line}-{c.end_line}", "code": c.snippet_text}
                    for c in ev["code_snippets"][:5]
                ],
                "doc_dep_snippets": [
                    {"file": c.file_path, "lines": f"{c.start_line}-{c.end_line}", "text": c.snippet_text}
                    for c in ev["doc_dep_snippets"][:5]
                ]
            })

        # 3. Batched LLM Evaluation
        llm_response = await GeminiService.evaluate_all_skills_batched(role_prof, skill_payloads, repo.full_name)
        llm_eval_map: Dict[int, Dict[str, Any]] = {}
        llm_model = None
        llm_rationale = None

        if llm_response and "error" not in llm_response:
            llm_model = llm_response.get("model")
            llm_rationale = llm_response.get("rationale")
            for item in llm_response.get("evaluations", []):
                req_id = item.get("requirement_id")
                if req_id is not None:
                    llm_eval_map[req_id] = item

        # 4. Synthesize Skill Assessment Results
        skill_results: List[SkillAssessmentResult] = []

        for req in requirements:
            ev = extracted_evidence.get(req.id, {"code_snippets": [], "doc_dep_snippets": []})
            code_snippets = ev["code_snippets"]
            doc_dep_snippets = ev["doc_dep_snippets"]
            llm_eval = llm_eval_map.get(req.id)

            llm_used = False
            practice_task = None

            if llm_eval:
                llm_used = True
                status_raw = str(llm_eval.get("status", "unmet")).lower()
                status = AssessmentStatus(status_raw) if status_raw in ("met", "partial", "unmet") else AssessmentStatus.UNMET
                confidence = float(llm_eval.get("confidence_score", 0.8))
                reason = str(llm_eval.get("reason", ""))
                limitations = [str(x) for x in llm_eval.get("limitations", [])]
                next_step = llm_eval.get("next_step")
                practice_task = llm_eval.get("practice_task")

                shown_code = code_snippets[:5]
                cited_indices = [i for i in llm_eval.get("cited_code_ids", []) if isinstance(i, int) and i < len(shown_code)]
                cited = [shown_code[i] for i in cited_indices]

                # Deterministic validation of the LLM verdict against real code evidence
                if not code_snippets and not doc_dep_snippets:
                    status = AssessmentStatus.UNMET
                    confidence = 0.0
                    cited = []
                    code_snippets = []
                    reason = f"No evidence of '{req.title}' found in inspected repository files for {repo.full_name}."
                elif status == AssessmentStatus.MET and not cited:
                    # If LLM claimed 'met' but provided no valid citations from code
                    if len(code_snippets) >= 2:
                        cited = code_snippets[:2]
                    elif len(code_snippets) == 1:
                        status = AssessmentStatus.PARTIAL
                        cited = code_snippets[:1]
                    else:
                        status = AssessmentStatus.PARTIAL if doc_dep_snippets else AssessmentStatus.UNMET
                elif status == AssessmentStatus.MET and not code_snippets:
                    status = AssessmentStatus.PARTIAL if doc_dep_snippets else AssessmentStatus.UNMET
                    limitations.append("Overridden: 'met' cannot be granted without executable code")
                elif status == AssessmentStatus.UNMET and code_snippets:
                    status = AssessmentStatus.NEEDS_REVIEW
                    limitations.append("Validation: 'unmet' claimed but code evidence exists")

                # Seniority depth enforcement
                if seniority in ("senior", "lead") and status == AssessmentStatus.MET and len(code_snippets) < 2:
                    status = AssessmentStatus.PARTIAL
                    limitations.append(f"Senior depth requirement: single shallow usage insufficient for {seniority} level")

                if cited:
                    code_snippets = cited + [c for c in code_snippets if c not in cited]
                elif not doc_dep_snippets and not code_snippets:
                    code_snippets = []
            else:
                # Deterministic Fallback Rules
                if len(code_snippets) >= 2:
                    status = AssessmentStatus.MET
                    confidence = 0.95
                    reason = f"Substantial code implementation found demonstrating '{req.title}' across {len(code_snippets)} code citations."
                    limitations = []
                    next_step = None
                elif len(code_snippets) == 1:
                    status = AssessmentStatus.PARTIAL
                    confidence = 0.70
                    reason = f"Minimal implementation found for '{req.title}' (1 citation in code)."
                    limitations = ["Limited depth of usage in source files"]
                    next_step = f"Expand implementation of {req.title} with additional endpoints, modules, or tests."
                elif len(doc_dep_snippets) > 0:
                    status = AssessmentStatus.PARTIAL
                    confidence = 0.40
                    reason = f"Found '{req.title}' declared in dependency/docs, but no actual substantive usage detected in executable code."
                    limitations = ["Declared in manifest/documentation only, missing functional implementation"]
                    next_step = f"Implement functional code utilizing {req.title} instead of only manifest declarations."
                else:
                    status = AssessmentStatus.UNMET
                    confidence = 0.0
                    reason = f"No evidence of '{req.title}' found in inspected repository files."
                    limitations = ["Skill not demonstrated in repository"]
                    next_step = f"Build a feature or service showcasing {req.title} to address this gap."

                practice_task = f"Implement a feature in {repo.full_name} showcasing production-ready {req.title} with unit tests."

            # Find verified resources for gaps/weak skills
            resources: List[LearningResource] = []
            if status in (AssessmentStatus.PARTIAL, AssessmentStatus.UNMET, AssessmentStatus.NEEDS_REVIEW):
                resources = await ResourceFinderService.get_resources_for_skill(
                    skill=req.title,
                    role_title=job.title,
                    seniority=seniority,
                    session=session
                )
                for r in resources:
                    r.requirement_id = req.id

            selected_citations = (code_snippets if code_snippets else doc_dep_snippets)[:5]

            skill_results.append(
                SkillAssessmentResult(
                    requirement_id=req.id or 0,
                    requirement_title=req.title,
                    category=req.category,
                    requirement_type=req.requirement_type.value,
                    weight=req.weight,
                    source_snippet=req.source_snippet,
                    status=status,
                    confidence_score=confidence,
                    reason=reason,
                    limitations=limitations,
                    next_step=next_step,
                    citations=selected_citations,
                    resources=resources,
                    practice_task=practice_task,
                    llm_used=llm_used,
                    llm_model=llm_model if llm_used else None,
                    llm_response=llm_eval if llm_used else None,
                )
            )

        return {
            "skill_results": skill_results,
            "llm_rationale": llm_rationale,
            "llm_model": llm_model
        }

    @classmethod
    async def evaluate_requirement(
        cls,
        requirement: Requirement,
        repo: Repository,
        tree_paths: List[str],
        content_cache: Optional[Dict[str, Optional[str]]] = None
    ) -> SkillAssessmentResult:
        """
        Backward-compatible single requirement evaluation.
        """
        if content_cache is None:
            content_cache = {}

        aliases = [requirement.title]
        if requirement.aliases:
            try:
                aliases = json.loads(requirement.aliases)
            except Exception:
                pass
        else:
            clean_words = re.findall(r'[A-Za-z0-9+#]+', requirement.title)
            aliases = list(set([requirement.title] + clean_words))

        ev = await cls.extract_evidence_for_requirement(requirement, repo, tree_paths, aliases, content_cache)
        code_snippets = ev["code_snippets"]
        doc_dep_snippets = ev["doc_dep_snippets"]

        from app.services.gemini_service import GeminiService
        llm_eval = await GeminiService.evaluate_skill_with_llm(
            requirement_title=requirement.title,
            category=requirement.category,
            requirement_type=requirement.requirement_type.value,
            job_source_snippet=requirement.source_snippet,
            code_snippets=[
                {"file": c.file_path, "lines": f"{c.start_line}-{c.end_line}", "code": c.snippet_text}
                for c in code_snippets[:5]
            ],
            doc_dep_snippets=[
                {"file": c.file_path, "lines": f"{c.start_line}-{c.end_line}", "text": c.snippet_text}
                for c in doc_dep_snippets[:5]
            ]
        )

        llm_used = False
        llm_model = None
        practice_task = None
        if llm_eval and "error" not in llm_eval:
            llm_used = True
            llm_model = llm_eval.get("model")
            status = AssessmentStatus(llm_eval["status"])
            confidence = llm_eval["confidence_score"]
            reason = llm_eval["reason"]
            limitations = llm_eval.get("limitations", [])
            next_step = llm_eval.get("next_step")
            practice_task = f"Implement a module utilizing {requirement.title} in {repo.full_name}."
            shown_code = code_snippets[:5]
            cited = [shown_code[i] for i in llm_eval.get("cited_code_ids", []) if i < len(shown_code)]
            if status == AssessmentStatus.MET and not cited:
                status = AssessmentStatus.NEEDS_REVIEW
            elif status == AssessmentStatus.MET and not code_snippets:
                status = AssessmentStatus.NEEDS_REVIEW
            elif status == AssessmentStatus.UNMET and code_snippets:
                status = AssessmentStatus.NEEDS_REVIEW
            if cited:
                code_snippets = cited + [c for c in code_snippets if c not in cited]
        else:
            if len(code_snippets) >= 2:
                status = AssessmentStatus.MET
                confidence = 0.95
                reason = f"Substantial code implementation found demonstrating '{requirement.title}' across {len(code_snippets)} code citations."
                limitations = []
                next_step = None
            elif len(code_snippets) == 1:
                status = AssessmentStatus.PARTIAL
                confidence = 0.70
                reason = f"Minimal implementation found for '{requirement.title}' (1 citation in code)."
                limitations = ["Limited depth of usage in source files"]
                next_step = f"Expand implementation of {requirement.title}."
            elif len(doc_dep_snippets) > 0:
                status = AssessmentStatus.PARTIAL
                confidence = 0.40
                reason = f"Found '{requirement.title}' declared in dependency/docs, but no actual substantive usage detected in executable code."
                limitations = ["Declared in manifest/documentation only, missing functional implementation"]
                next_step = f"Implement functional code utilizing {requirement.title} instead of only manifest declarations."
            else:
                status = AssessmentStatus.UNMET
                confidence = 0.0
                reason = f"No evidence of '{requirement.title}' found in inspected repository files."
                limitations = ["Skill not demonstrated in repository"]
                next_step = f"Build a feature or service showcasing {requirement.title} to address this gap."
            practice_task = f"Add {requirement.title} implementation with tests to {repo.full_name}."

        resources = []
        if status in (AssessmentStatus.PARTIAL, AssessmentStatus.UNMET, AssessmentStatus.NEEDS_REVIEW):
            resources = await ResourceFinderService.get_resources_for_skill(
                skill=requirement.title,
                role_title="Software Engineer",
                seniority="mid"
            )

        selected_citations = (code_snippets if code_snippets else doc_dep_snippets)[:5]

        return SkillAssessmentResult(
            requirement_id=requirement.id or 0,
            requirement_title=requirement.title,
            category=requirement.category,
            requirement_type=requirement.requirement_type.value,
            weight=requirement.weight,
            source_snippet=requirement.source_snippet,
            status=status,
            confidence_score=confidence,
            reason=reason,
            limitations=limitations,
            next_step=next_step,
            citations=selected_citations,
            resources=resources,
            practice_task=practice_task,
            llm_used=llm_used,
            llm_model=llm_model,
            llm_response=llm_eval if llm_used else None,
        )

    @classmethod
    def calculate_summary(cls, skill_results: List[SkillAssessmentResult]) -> AssessmentSummary:
        total = len(skill_results)
        if total == 0:
            return AssessmentSummary(
                total_skills=0,
                met=0,
                partial=0,
                unmet=0,
                overall_match_percentage=0.0,
                weighted_score=0.0
            )

        met_count = sum(1 for s in skill_results if s.status == AssessmentStatus.MET)
        partial_count = sum(1 for s in skill_results if s.status == AssessmentStatus.PARTIAL)
        unmet_count = sum(1 for s in skill_results if s.status == AssessmentStatus.UNMET)

        # Calculate weighted scores
        total_possible_weight = sum(s.weight for s in skill_results)
        earned_weight = 0.0

        for s in skill_results:
            if s.status == AssessmentStatus.MET:
                earned_weight += s.weight * 1.0
            elif s.status == AssessmentStatus.PARTIAL:
                earned_weight += s.weight * 0.5

        weighted_score = round(earned_weight, 2)
        match_percentage = round((earned_weight / total_possible_weight * 100), 1) if total_possible_weight > 0 else 0.0

        return AssessmentSummary(
            total_skills=total,
            met=met_count,
            partial=partial_count,
            unmet=unmet_count,
            needs_review=sum(1 for s in skill_results if s.status == AssessmentStatus.NEEDS_REVIEW),
            overall_match_percentage=match_percentage,
            weighted_score=weighted_score
        )
