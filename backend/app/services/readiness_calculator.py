import math
from typing import List, Dict, Any, Optional, Tuple
from app.models.entities import RequirementType, AssessmentStatus
from app.schemas.assessment import (
    SkillAssessmentResult,
    ReadinessPrediction,
    ReadinessDriver,
    WhatIfScore,
)

class ReadinessCalculator:
    """
    Computes a deterministic, explainable readiness prediction:
    - Score (0-100)
    - Band: "Not ready" | "Stretch" | "Competitive" | "Strong"
    - Confidence: "low" | "medium" | "high"
    - Top drivers (helps most) & top blockers (hurts most)
    - What-if projected score if top 3 blockers are resolved
    """

    @classmethod
    def calculate(
        cls,
        skills: List[SkillAssessmentResult],
        seniority: str = "mid",
        repo_signals: Optional[Dict[str, Any]] = None,
        llm_rationale: Optional[str] = None
    ) -> ReadinessPrediction:
        if not skills:
            return ReadinessPrediction(
                score=0,
                band="Not ready",
                confidence="low",
                rationale="No skills assessed.",
                top_drivers=[],
                top_blockers=[],
                what_if=None
            )

        if repo_signals is None:
            repo_signals = {}

        # 1. Base Weighted Score from Requirements
        # Required skills carry 1.5x effective weight compared to preferred (1.0x) or bonus (0.6x)
        total_effective_weight = 0.0
        earned_weight = 0.0

        skill_impacts: List[Tuple[SkillAssessmentResult, float, float]] = []  # (skill, weight_mult, earned)

        for s in skills:
            type_mult = 1.5 if s.requirement_type == RequirementType.REQUIRED.value else (
                1.0 if s.requirement_type == RequirementType.PREFERRED.value else 0.6
            )
            item_weight = s.weight * type_mult
            total_effective_weight += item_weight

            # Status points
            if s.status == AssessmentStatus.MET:
                # Evidence strength: citations bonus
                code_cits = [c for c in s.citations if not c.is_dependency_or_doc_only]
                cit_bonus = min(0.1, len(code_cits) * 0.02)
                item_earned = item_weight * min(1.0, 0.9 + cit_bonus)
            elif s.status == AssessmentStatus.PARTIAL:
                # Manifest only gives less for senior roles
                if seniority in ("senior", "lead"):
                    item_earned = item_weight * 0.35
                else:
                    item_earned = item_weight * 0.50
            elif s.status == AssessmentStatus.NEEDS_REVIEW:
                item_earned = item_weight * 0.20
            else:
                item_earned = 0.0

            earned_weight += item_earned
            skill_impacts.append((s, item_weight, item_earned))

        base_score = (earned_weight / total_effective_weight * 100) if total_effective_weight > 0 else 0.0

        # 2. Repo Signals Bonus / Penalty
        repo_mod = 0.0
        if repo_signals.get("has_tests"):
            repo_mod += 4.0
        if repo_signals.get("has_ci"):
            repo_mod += 3.0
        if repo_signals.get("is_tiny_repo"):
            repo_mod -= 5.0

        # Seniority penalty if senior/lead role has high proportion of partial/unmet
        unmet_or_partial_count = sum(1 for s in skills if s.status != AssessmentStatus.MET)
        if seniority in ("senior", "lead") and (unmet_or_partial_count / len(skills)) > 0.4:
            repo_mod -= 4.0

        final_score = int(max(0, min(100, round(base_score + repo_mod))))

        # 3. Determine Band
        if final_score >= 80:
            band = "Strong"
        elif final_score >= 65:
            band = "Competitive"
        elif final_score >= 45:
            band = "Stretch"
        else:
            band = "Not ready"

        # 4. Confidence level
        # Lower confidence when: NEEDS_REVIEW is high, repo is tiny, or rule-based fallback used
        needs_review_count = sum(1 for s in skills if s.status == AssessmentStatus.NEEDS_REVIEW)
        rule_based_count = sum(1 for s in skills if not s.llm_used)
        is_tiny = repo_signals.get("is_tiny_repo", False)

        if needs_review_count >= 2 or rule_based_count > (len(skills) / 2) or is_tiny:
            confidence = "low"
        elif needs_review_count == 1 or rule_based_count > 0:
            confidence = "medium"
        else:
            confidence = "high"

        # 5. Top drivers (top 3 skills that contributed the most earned points)
        sorted_by_earned = sorted(skill_impacts, key=lambda x: x[2], reverse=True)
        top_drivers: List[ReadinessDriver] = []
        for s, w, earned in sorted_by_earned[:3]:
            if earned > 0:
                pct = round((earned / total_effective_weight) * 100, 1)
                top_drivers.append(
                    ReadinessDriver(
                        skill=s.requirement_title,
                        impact=f"+{pct}% demonstrated evidence ({s.status.value})",
                        status=s.status.value
                    )
                )

        # 6. Top blockers (top 3 skills with highest missed weight)
        sorted_by_missed = sorted(skill_impacts, key=lambda x: (x[1] - x[2]), reverse=True)
        top_blockers: List[ReadinessDriver] = []
        closed_gap_titles = []
        potential_gain = 0.0

        for s, w, earned in sorted_by_missed:
            missed = w - earned
            if missed > 0.05 and len(top_blockers) < 3:
                pct = round((missed / total_effective_weight) * 100, 1)
                top_blockers.append(
                    ReadinessDriver(
                        skill=s.requirement_title,
                        impact=f"-{pct}% {s.requirement_type} gap ({s.status.value})",
                        status=s.status.value
                    )
                )
                closed_gap_titles.append(s.requirement_title)
                potential_gain += missed

        # 7. What-If Calculation: Projected score if the top 3 gaps are closed to MET
        projected_earned = earned_weight + potential_gain
        projected_score = min(100.0, round(((projected_earned / total_effective_weight) * 100) + repo_mod, 1)) if total_effective_weight > 0 else 0.0
        
        if projected_score >= 80:
            proj_band = "Strong"
        elif projected_score >= 65:
            proj_band = "Competitive"
        elif projected_score >= 45:
            proj_band = "Stretch"
        else:
            proj_band = "Not ready"

        what_if = WhatIfScore(
            projected_score=projected_score,
            projected_band=proj_band,
            gain=round(projected_score - final_score, 1),
            closed_gaps=closed_gap_titles
        )

        # Default plain-English rationale if none provided by LLM
        if not llm_rationale:
            blocker_text = f" Closing gaps in {', '.join(closed_gap_titles[:2])} would elevate this candidate profile." if closed_gap_titles else ""
            rationale = (
                f"Candidate matches {final_score}% of role expectations for a {seniority}-level position. "
                f"Evaluated across {len(skills)} technical requirements with {len(top_drivers)} core strengths demonstrated.{blocker_text}"
            )
        else:
            rationale = llm_rationale

        return ReadinessPrediction(
            score=final_score,
            band=band,
            confidence=confidence,
            rationale=rationale,
            top_drivers=top_drivers,
            top_blockers=top_blockers,
            what_if=what_if
        )
