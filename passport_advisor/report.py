from __future__ import annotations

from passport_advisor.models import (
    ApplicantProfile,
    ChecklistResult,
    EligibilityDecision,
    FeeBreakdown,
)


def render_english_markdown(
    profile: ApplicantProfile,
    policy: EligibilityDecision,
    fees: FeeBreakdown,
    checklist: ChecklistResult,
    flags: list[str],
) -> str:
    document_text = ", ".join(checklist.documents)
    flag_text = "; ".join(flags) if flags else "None"
    location = profile.location or "Not specified"

    lines = [
        "| Field | Result |",
        "| --- | --- |",
        f"| Applicant Age | {profile.age} |",
        f"| Location | {location} |",
        f"| Validity | {policy.permitted_validity_years} Years |",
        f"| Delivery Type | {profile.delivery_speed.value.replace('_', ' ').title()} |",
        f"| Required Identification | {policy.required_identification} |",
        f"| Base Fee | {fees.base_fee_bdt} BDT |",
        f"| VAT (15%) | {fees.vat_bdt} BDT |",
        f"| Total Fee | {fees.total_fee_bdt} BDT |",
        f"| Documents Needed | {document_text} |",
        f"| Flags | {flag_text} |",
    ]
    return "\n".join(lines)


def render_bangla_markdown(
    policy: EligibilityDecision,
    fees: FeeBreakdown,
    checklist: ChecklistResult,
    flags: list[str],
) -> str:
    document_text = ", ".join(checklist.documents)
    flag_text = "; ".join(flags) if flags else "কোনো সমস্যা ধরা পড়েনি"

    lines = [
        "| বিষয় | ফলাফল |",
        "| --- | --- |",
        f"| পাসপোর্টের মেয়াদ | {policy.permitted_validity_years} বছর |",
        f"| প্রয়োজনীয় পরিচয়পত্র | {policy.required_identification} |",
        f"| মোট ফি | {fees.total_fee_bdt} টাকা |",
        f"| প্রয়োজনীয় কাগজপত্র | {document_text} |",
        f"| সতর্কতা | {flag_text} |",
    ]
    return "\n".join(lines)
