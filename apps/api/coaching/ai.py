"""AI coaching pipeline (FR-7). Builds a PII-free summary of a client's last
4 weeks, calls the Anthropic Messages API for suggestions, validates the
response with Pydantic, retries once on bad JSON, then falls back to
deterministic rules-only suggestions. Budget-checked before ever spending.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

import anthropic
import pydantic
from django.conf import settings
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from pydantic import BaseModel

from attendance.models import Attendance
from coaching.domain.flags import (
    ProteinDay,
    WeightEntry,
    WorkoutLogEntry,
    low_attendance,
    low_protein,
    missed_leg_day,
    weight_stall,
)
from coaching.domain.progress import attendance_pct, goal_progress_pct
from coaching.models import BodyMeasurement, ClientProfile, CoachingReport, DietLog, WorkoutLog
from coaching.services import EXPECTED_VISITS_PER_WEEK

logger = logging.getLogger(__name__)

LOOKBACK_WEEKS = 4
SYSTEM_PROMPT = """You are a fitness coaching assistant for a gym in Nepal. \
You will receive a compact JSON summary of one client's last 4 weeks of \
training, body measurements, attendance, and nutrition, plus any \
rule-based risk flags already computed. Respond with STRICT JSON ONLY, no \
markdown, no prose outside the JSON object, matching exactly this shape:
{"summary": "<2-3 sentence plain-language summary>", \
"suggestions": [{"type": "workout|diet|recovery|attendance|general", \
"text_en": "<suggestion in English>", "text_ne": "<the same suggestion in \
Nepali>", "reason": "<short reason tying it to the data>"}]}
Provide 2-4 suggestions. Never invent data not present in the summary."""


class Suggestion(BaseModel):
    type: Literal["workout", "diet", "recovery", "attendance", "general"]
    text_en: str
    text_ne: str
    reason: str


class CoachingSuggestions(BaseModel):
    summary: str
    suggestions: list[Suggestion]


# USD per million tokens, this implementation's own snapshot — update when
# Anthropic repricing happens, not fetched live.
PRICING_USD_PER_MTOK: dict[str, dict[str, Decimal]] = {
    "claude-sonnet-5": {"input": Decimal("3.00"), "output": Decimal("15.00")},
}
_DEFAULT_PRICING = PRICING_USD_PER_MTOK["claude-sonnet-5"]


def build_summary_payload(
    member_id: str,
    primary_goal: str,
    measurements: list[dict],
    workout_logs: list[dict],
    attendance: dict,
    macros: dict,
    flags: list[str],
    progress: dict,
) -> dict[str, Any]:
    """Pure — no Django, no HTTP. The only identifier in here is the
    member's opaque UUID (needed to attribute the response back); no name,
    phone, email, or photo URL field exists in this function at all.
    """
    return {
        "member_id": member_id,
        "primary_goal": primary_goal,
        "measurements": measurements,
        "workout_logs": workout_logs,
        "attendance": attendance,
        "macros": macros,
        "flags": flags,
        "progress": progress,
    }


@dataclass(frozen=True)
class AnthropicResponse:
    text: str
    input_tokens: int
    output_tokens: int


def call_anthropic(payload: dict[str, Any], *, model: str, api_key: str) -> AnthropicResponse:
    """Thin wrapper — the only function that touches the network, and the
    one tests mock via unittest.mock.patch('coaching.ai.call_anthropic').
    Returns just the text + token counts the caller needs, not the full
    SDK Message object, so a test's mock return value is a plain small
    dataclass rather than needing to fake the SDK's response shape.
    """
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    first_block = response.content[0]
    if not isinstance(first_block, anthropic.types.TextBlock):
        raise ValueError(f"Unexpected Anthropic response block type: {type(first_block)!r}")
    return AnthropicResponse(
        text=first_block.text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def parse_and_validate(raw_text: str) -> CoachingSuggestions | None:
    """Never raises — returns None on any parse/validation failure so the
    caller can retry once then fall back to rules_only_suggestions().
    """
    try:
        return CoachingSuggestions.model_validate_json(raw_text)
    except (ValueError, pydantic.ValidationError):
        return None


_FLAG_SUGGESTIONS: dict[str, Suggestion] = {
    "missed_leg_day": Suggestion(
        type="workout",
        text_en="No leg day in over a week — try to fit in a lower-body session soon.",
        text_ne="एक हप्तादेखि खुट्टाको अभ्यास छैन — छिट्टै लोअर-बडी सेशन गर्नुहोस्।",
        reason="missed_leg_day",
    ),
    "weight_stall": Suggestion(
        type="diet",
        text_en="Weight has barely moved in three weeks — discuss a calorie adjustment.",
        text_ne="तौल तीन हप्तादेखि लगभग उस्तै छ — ट्रेनरसँग क्यालोरी समायोजनको कुरा गर्नुहोस्।",
        reason="weight_stall",
    ),
    "low_protein": Suggestion(
        type="diet",
        text_en="Protein intake has been below target on several days — add a protein source.",
        text_ne="प्रोटिन सेवन धेरै दिन लक्ष्यभन्दा कम छ — खानामा थप प्रोटिन स्रोत थप्नुहोस्।",
        reason="low_protein",
    ),
    "low_attendance": Suggestion(
        type="attendance",
        text_en="Attendance has dropped below half of what's expected — let's adjust the schedule.",
        text_ne="जिम उपस्थिति अपेक्षित भन्दा आधाभन्दा कम छ — तपाईंलाई मिल्ने समयतालिका खोजौं।",
        reason="low_attendance",
    ),
}


def rules_only_suggestions(flags: list[str]) -> CoachingSuggestions:
    """Deterministic fallback — one canned Suggestion per active flag,
    always succeeds, no LLM involved.
    """
    suggestions = [_FLAG_SUGGESTIONS[f] for f in flags if f in _FLAG_SUGGESTIONS]
    if not suggestions:
        suggestions = [
            Suggestion(
                type="general",
                text_en="Keep up the consistent work — no specific concerns this week.",
                text_ne="निरन्तर मेहनत जारी राख्नुहोस् — यस हप्ता कुनै विशेष चिन्ता छैन।",
                reason="no_flags",
            )
        ]
    return CoachingSuggestions(
        summary="Rules-based summary (AI unavailable or budget exceeded).", suggestions=suggestions
    )


def _cost_npr(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    rate = PRICING_USD_PER_MTOK.get(model, _DEFAULT_PRICING)
    usd = (Decimal(input_tokens) / Decimal(1_000_000)) * rate["input"] + (
        Decimal(output_tokens) / Decimal(1_000_000)
    ) * rate["output"]
    return (usd * settings.ANTHROPIC_USD_TO_NPR_RATE).quantize(Decimal("0.01"))


def _month_spend_npr(gym: Any) -> Decimal:
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = CoachingReport.objects.filter(gym=gym, created_at__gte=month_start).aggregate(
        total=Coalesce(Sum("cost_npr"), Decimal("0.00"))
    )["total"]
    return total


@dataclass
class ClientSummaryInputs:
    payload: dict[str, Any]
    flags: list[str]


def _gather_client_summary(profile: ClientProfile, week_start: date) -> ClientSummaryInputs:
    """ORM-touching glue: builds the pure flags-engine dataclasses from
    real querysets, then the PII-free payload dict from the same data.
    """
    member = profile.member
    lookback_start = week_start - timedelta(weeks=LOOKBACK_WEEKS)

    measurement_qs = BodyMeasurement.objects.filter(
        member=member, measured_on__gte=lookback_start, measured_on__lte=week_start
    ).order_by("measured_on")
    measurements = list(measurement_qs)

    workout_qs = WorkoutLog.objects.filter(
        member=member, logged_on__gte=lookback_start, logged_on__lte=week_start
    ).select_related("exercise")
    workout_logs = list(workout_qs)

    diet_qs = DietLog.objects.filter(
        member=member, logged_on__gte=lookback_start, logged_on__lte=week_start
    )
    diet_logs = list(diet_qs)

    visits_last_4w = (
        Attendance.objects.filter(
            member=member, check_in_at__date__gte=lookback_start, check_in_at__date__lte=week_start
        )
        .values_list("check_in_at__date", flat=True)
        .distinct()
        .count()
    )
    expected_visits_4w = EXPECTED_VISITS_PER_WEEK * LOOKBACK_WEEKS

    flag_results: list[str] = []
    weight_entries = [
        WeightEntry(measured_on=m.measured_on, weight_kg=float(m.weight_kg)) for m in measurements
    ]
    if weight_stall(weight_entries, week_start):
        flag_results.append("weight_stall")

    log_entries = [
        WorkoutLogEntry(logged_on=w.logged_on, muscle_groups=frozenset({w.exercise.muscle_group}))
        for w in workout_logs
    ]
    if missed_leg_day(log_entries, week_start):
        flag_results.append("missed_leg_day")

    protein_target = float(profile.diet_plan.protein_g) if profile.diet_plan else 0.0
    protein_days = [ProteinDay(day=d.logged_on, protein_g=float(d.protein_g)) for d in diet_logs]
    if low_protein(protein_days, protein_target):
        flag_results.append("low_protein")

    if low_attendance(visits_last_4w, expected_visits_4w):
        flag_results.append("low_attendance")

    current_weight = (
        float(measurements[-1].weight_kg) if measurements else float(profile.starting_weight_kg)
    )
    progress = {
        "goal_progress_pct": goal_progress_pct(
            float(profile.starting_weight_kg), current_weight, float(profile.target_weight_kg)
        ),
        "attendance_pct": attendance_pct(visits_last_4w, expected_visits_4w),
    }

    avg_protein_pct = 0.0
    if protein_target > 0 and protein_days:
        avg_protein_pct = (
            sum(d.protein_g for d in protein_days) / len(protein_days) / protein_target * 100
        )

    payload = build_summary_payload(
        member_id=str(member.pk),
        primary_goal=profile.primary_goal,
        measurements=[
            {
                "date": m.measured_on.isoformat(),
                "weight_kg": float(m.weight_kg),
                "body_fat_pct": float(m.body_fat_pct) if m.body_fat_pct is not None else None,
            }
            for m in measurements
        ],
        workout_logs=[
            {
                "date": w.logged_on.isoformat(),
                "muscle_group": w.exercise.muscle_group,
                "total_sets": len(w.sets),
            }
            for w in workout_logs
        ],
        attendance={"visits_last_4w": visits_last_4w, "expected_visits_4w": expected_visits_4w},
        macros={"avg_protein_pct_of_target": round(avg_protein_pct, 1)},
        flags=flag_results,
        progress=progress,
    )
    return ClientSummaryInputs(payload=payload, flags=flag_results)


def generate_weekly_report(profile: ClientProfile, week_start: date) -> CoachingReport:
    """The orchestrator. Budget check happens BEFORE the Anthropic call —
    that's the only way skipping actually skips the spend. Retries once on
    bad JSON, then falls back to rules_only_suggestions(). Idempotent
    against a re-run via update_or_create on (gym, member, week_start, kind).
    """
    gym = profile.gym
    inputs = _gather_client_summary(profile, week_start)

    budget = Decimal(str(gym.settings.get("ai_budget_npr_monthly", 2000)))
    model_used = ""
    tokens_used = 0
    cost = Decimal("0.00")

    if _month_spend_npr(gym) >= budget:
        logger.info("coaching.ai: budget exceeded for gym=%s, skipping Anthropic call", gym.id)
        suggestions = rules_only_suggestions(inputs.flags)
    else:
        suggestions = None
        response: AnthropicResponse | None = None
        for _attempt in range(2):
            try:
                response = call_anthropic(
                    inputs.payload,
                    model=settings.ANTHROPIC_MODEL,
                    api_key=settings.ANTHROPIC_API_KEY,
                )
            except anthropic.APIError as exc:
                logger.warning("coaching.ai: Anthropic API error: %s", exc)
                response = None
                break
            suggestions = parse_and_validate(response.text)
            if suggestions is not None:
                break
        if suggestions is None:
            suggestions = rules_only_suggestions(inputs.flags)
        else:
            assert response is not None
            model_used = settings.ANTHROPIC_MODEL
            tokens_used = response.input_tokens + response.output_tokens
            cost = _cost_npr(model_used, response.input_tokens, response.output_tokens)

    assert suggestions is not None  # both branches above always resolve it
    report, _created = CoachingReport.objects.update_or_create(
        gym=gym,
        member=profile.member,
        week_start=week_start,
        kind=CoachingReport.Kind.MEMBER,
        defaults={
            "org": gym.org,
            "flags": inputs.flags,
            "suggestions": [s.model_dump() for s in suggestions.suggestions],
            "status": CoachingReport.Status.DRAFT,
            "model": model_used,
            "tokens_used": tokens_used,
            "cost_npr": cost,
        },
    )
    return report


def generate_branch_report(gym: Any, week_start: date) -> CoachingReport:
    """Pure DB rollup of that week's member CoachingReport rows — no second
    LLM call. Totals of flags, top risks, trainer approval rate, token cost.
    """
    member_reports = list(
        CoachingReport.objects.filter(
            gym=gym, week_start=week_start, kind=CoachingReport.Kind.MEMBER
        )
    )
    flag_counts: dict[str, int] = {}
    for report in member_reports:
        for flag in report.flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
    top_risks = sorted(flag_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]

    reviewed = [r for r in member_reports if r.status != CoachingReport.Status.DRAFT]
    approved = [r for r in reviewed if r.status == CoachingReport.Status.APPROVED]
    approval_rate = (len(approved) / len(reviewed) * 100) if reviewed else 0.0
    total_cost = sum((r.cost_npr for r in member_reports), Decimal("0.00"))

    branch_report, _created = CoachingReport.objects.update_or_create(
        gym=gym,
        member=None,
        week_start=week_start,
        kind=CoachingReport.Kind.BRANCH,
        defaults={
            "org": gym.org,
            "flags": {
                "flag_counts": [{"flag": f, "count": c} for f, c in flag_counts.items()],
                "approval_rate_pct": round(approval_rate, 1),
                "reports_reviewed": len(reviewed),
                "reports_approved": len(approved),
            },
            "suggestions": [
                {
                    "type": "general",
                    "text_en": f"Top risk this week: {name} ({count} client(s)).",
                    "text_ne": "",
                    "reason": name,
                }
                for name, count in top_risks
            ],
            "status": CoachingReport.Status.DRAFT,
            "model": "",
            "tokens_used": 0,
            "cost_npr": total_cost,
        },
    )
    return branch_report
