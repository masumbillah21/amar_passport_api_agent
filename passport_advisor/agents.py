from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
import sys

from passport_advisor.data import LOCAL_REFERENCE_DB
from passport_advisor.models import (
    ApplicantProfile,
    ChecklistResult,
    CrewExecution,
    EligibilityDecision,
    FeeBreakdown,
    Profession,
)

# CrewAI telemetry tries to register signal handlers on import. In FastAPI sync
# endpoints that import can happen in a worker thread, which raises warnings.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")


class _TeeStream:
    """Write CrewAI verbose output to both console and the in-memory trace buffer."""

    def __init__(self, *streams: object) -> None:
        self._streams = streams

    def write(self, value: str) -> int:
        for stream in self._streams:
            stream.write(value)
        return len(value)

    def flush(self) -> None:
        for stream in self._streams:
            if hasattr(stream, "flush"):
                stream.flush()


class PolicyGuardian:
    """Eligibility agent for passport validity and identification rules."""

    role = "Bangladesh Passport Policy Expert"
    goal = "Determine passport validity and identity document requirements."
    backstory = (
        "A senior policy analyst who interprets Bangladesh e-passport rules and "
        "flags age-related inconsistencies before an application proceeds."
    )

    def evaluate(self, profile: ApplicantProfile) -> EligibilityDecision:
        flags: list[str] = []

        if profile.age < 18:
            permitted_validity = 5
            required_id = "Birth Registration (English)"
            age_band = "minor_under_18"
            if profile.requested_validity_years == 10:
                flags.append(
                    "Applicants under 18 are not eligible for a 10-year passport. Switched to 5 years."
                )
            if not profile.has_birth_registration:
                flags.append("Birth Registration is required for applicants under 18.")
        elif profile.age > 65:
            permitted_validity = 5
            required_id = "NID Card"
            age_band = "senior_over_65"
            if profile.requested_validity_years == 10:
                flags.append(
                    "Applicants over 65 are restricted to a 5-year passport. Switched to 5 years."
                )
            if not profile.has_nid:
                flags.append("NID is required for applicants over 65.")
        else:
            permitted_validity = profile.requested_validity_years or 10
            required_id = "NID Card"
            age_band = "adult"
            if not profile.has_nid:
                flags.append("Adult applicants should provide a valid NID.")

        explanation = (
            f"Age {profile.age} falls into the '{age_band}' policy band, so the permitted "
            f"validity is {permitted_validity} years and the core identification is {required_id}."
        )

        return EligibilityDecision(
            permitted_validity_years=permitted_validity,
            required_identification=required_id,
            age_band=age_band,
            flags=flags,
            explanation=explanation,
        )


class ChancellorOfTheExchequer:
    """Fee calculator using the 2026 reference fee table."""

    role = "Financial Auditor"
    goal = "Calculate the exact fee including 15% VAT from the 2026 fee table."
    backstory = (
        "A meticulous auditor who always reconciles the final payable amount with the "
        "official fee schedule and uses a local fallback dataset when live sources are unavailable."
    )

    def calculate(self, profile: ApplicantProfile, policy: EligibilityDecision) -> FeeBreakdown:
        fee_table = LOCAL_REFERENCE_DB["fees_2026"][f"{profile.page_count}_pages"][
            f"{policy.permitted_validity_years}_years"
        ]
        total_fee = int(fee_table[profile.delivery_speed.value])
        base_fee = (total_fee * 100) // 115
        vat = total_fee - base_fee

        return FeeBreakdown(
            page_count=profile.page_count,
            delivery_speed=profile.delivery_speed,
            validity_years=policy.permitted_validity_years,
            base_fee_bdt=base_fee,
            vat_bdt=vat,
            total_fee_bdt=total_fee,
            used_local_fallback=True,
        )


class DocumentArchitect:
    """Checklist specialist for tailored document preparation."""

    role = "Documentation Officer"
    goal = "Generate a clean, customized document checklist for the applicant."
    backstory = (
        "A documentation specialist who builds application checklists based on identity, "
        "profession, and special conditions such as minor status or name changes."
    )

    def build(self, profile: ApplicantProfile, policy: EligibilityDecision) -> ChecklistResult:
        docs: list[str] = []
        flags: list[str] = []

        if policy.age_band == "minor_under_18":
            docs.extend(LOCAL_REFERENCE_DB["required_docs"]["minor_under_18"])
        else:
            docs.extend(LOCAL_REFERENCE_DB["required_docs"]["adult"])

        profession_map = {
            Profession.GOVERNMENT_STAFF: "government_staff",
            Profession.PRIVATE_SECTOR: "private_sector",
            Profession.STUDENT: "student",
            Profession.BUSINESS_OWNER: "business_owner",
        }
        profession_key = profession_map.get(profile.profession)
        if profession_key:
            docs.extend(LOCAL_REFERENCE_DB["required_docs"][profession_key])

        if profile.name_changed:
            docs.extend(LOCAL_REFERENCE_DB["required_docs"]["name_change"])

        docs.append(policy.required_identification)
        deduplicated_docs = list(dict.fromkeys(docs))

        if profile.profession != Profession.OTHER and not profile.has_profession_proof:
            flags.append("A profession-related proof document is missing from the applicant profile.")

        explanation = (
            "The checklist combines the base rule set, age-specific requirements, and "
            "profession-specific supporting documents."
        )
        return ChecklistResult(documents=deduplicated_docs, flags=flags, explanation=explanation)


class CrewAIOrchestrator:
    """Optional CrewAI enrichment layer.

    The business decision stays deterministic. CrewAI is used only to provide an
    additional multi-agent reasoning trace when dependencies and credentials exist.
    """

    role = "Virtual Consular Officer Crew"

    def run(
        self,
        profile: ApplicantProfile,
        policy: EligibilityDecision,
        fees: FeeBreakdown,
        checklist: ChecklistResult,
    ) -> CrewExecution:
        try:
            from crewai import Agent, Crew, LLM, Process, Task
        except ImportError:
            return CrewExecution(
                status="skipped",
                notes="CrewAI is not installed. Used the local rule engine and fallback database.",
            )

        if not self._has_llm_credentials():
            return CrewExecution(
                status="skipped",
                notes=(
                    "CrewAI is enabled but no LLM API key is configured. "
                    "Used the local rule engine and fallback database."
                ),
            )

        trace_buffer = StringIO()

        try:
            stdout_stream = _TeeStream(sys.stdout, trace_buffer)
            stderr_stream = _TeeStream(sys.stderr, trace_buffer)

            with redirect_stdout(stdout_stream), redirect_stderr(stderr_stream):
                llm = self._build_llm(LLM)

                print("[CrewAI] Starting multi-agent execution")
                print("[CrewAI] Agent 1: The Policy Guardian")
                policy_agent = Agent(
                    role="The Policy Guardian",
                    goal="Validate eligibility and passport validity rules for Bangladesh e-passports.",
                    backstory=PolicyGuardian.backstory,
                    llm=llm,
                    verbose=True,
                )
                print("[CrewAI] Agent 2: The Chancellor of the Exchequer")
                fee_agent = Agent(
                    role="The Chancellor of the Exchequer",
                    goal="Calculate 2026 passport fees including 15% VAT.",
                    backstory=ChancellorOfTheExchequer.backstory,
                    llm=llm,
                    verbose=True,
                )
                print("[CrewAI] Agent 3: The Document Architect")
                document_agent = Agent(
                    role="The Document Architect",
                    goal="Create the final document checklist for the applicant.",
                    backstory=DocumentArchitect.backstory,
                    llm=llm,
                    verbose=True,
                )

                policy_task = Task(
                    description=(
                        "Review the applicant profile and summarize the eligibility decision.\n"
                        f"Applicant profile: {profile.model_dump()}\n"
                        f"Deterministic decision: {policy.model_dump()}"
                    ),
                    agent=policy_agent,
                    expected_output="A short policy summary confirming validity and identification rules.",
                )
                fee_task = Task(
                    description=(
                        "Use the policy context to confirm the fee calculation from the 2026 table.\n"
                        f"Deterministic fee breakdown: {fees.model_dump()}"
                    ),
                    agent=fee_agent,
                    context=[policy_task],
                    expected_output="A short fee summary with base fee, VAT, and total payable amount.",
                )
                document_task = Task(
                    description=(
                        "Prepare the customized checklist using the policy and fee context.\n"
                        f"Deterministic checklist: {checklist.model_dump()}"
                    ),
                    agent=document_agent,
                    context=[policy_task, fee_task],
                    expected_output="A short checklist summary for the applicant.",
                )

                print("[CrewAI] Execution order:")
                print("[CrewAI] 1. The Policy Guardian -> eligibility validation")
                print("[CrewAI] 2. The Chancellor of the Exchequer -> fee validation")
                print("[CrewAI] 3. The Document Architect -> checklist validation")

                crew = Crew(
                    agents=[policy_agent, fee_agent, document_agent],
                    tasks=[policy_task, fee_task, document_task],
                    process=Process.sequential,
                    verbose=True,
                )
                print("[CrewAI] Kickoff started")
                result = crew.kickoff()
                print("[CrewAI] Kickoff completed")

            trace = trace_buffer.getvalue().strip() or None
            return CrewExecution(status="completed", notes=str(result), trace=trace)
        except Exception as exc:
            trace = trace_buffer.getvalue().strip() or None
            if trace:
                trace = f"{trace}\n\n[FALLBACK] CrewAI failed and local rules were used.\n{exc}"
            return CrewExecution(
                status="failed",
                notes=f"CrewAI execution failed. Used fallback rule engine instead. Details: {exc}",
                trace=trace,
            )

    @staticmethod
    def _has_llm_credentials() -> bool:
        return any(
            os.getenv(key)
            for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
        )

    @staticmethod
    def _build_llm(llm_cls: type) -> object:
        if os.getenv("GROQ_API_KEY"):
            return llm_cls(
                model=os.getenv("GROQ_MODEL", "groq/llama-3.3-70b-versatile"),
                temperature=0.2,
            )
        if os.getenv("OPENAI_API_KEY"):
            return llm_cls(
                model=os.getenv("OPENAI_MODEL_NAME", "openai/gpt-4o-mini"),
                temperature=0.2,
            )
        if os.getenv("ANTHROPIC_API_KEY"):
            return llm_cls(
                model=os.getenv("ANTHROPIC_MODEL", "anthropic/claude-3-5-sonnet-latest"),
                temperature=0.2,
            )
        if os.getenv("GEMINI_API_KEY"):
            return llm_cls(
                model=os.getenv("GEMINI_MODEL", "gemini/gemini-2.0-flash"),
                temperature=0.2,
            )
        raise RuntimeError("No supported LLM credentials are configured for CrewAI.")
