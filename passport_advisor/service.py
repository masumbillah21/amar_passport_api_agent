from __future__ import annotations

from passport_advisor.agents import (
    ChancellorOfTheExchequer,
    CrewAIOrchestrator,
    DocumentArchitect,
    PolicyGuardian,
)
from passport_advisor.models import ApplicantProfile, PassportReadinessReport, ScenarioParseResult
from passport_advisor.report import render_bangla_markdown, render_english_markdown
from passport_advisor.scenario_parser import ScenarioParser


class PassportReadinessService:
    """Application service that coordinates the three domain agents."""

    def __init__(self) -> None:
        self.policy_guardian = PolicyGuardian()
        self.fee_calculator = ChancellorOfTheExchequer()
        self.document_architect = DocumentArchitect()
        self.crewai = CrewAIOrchestrator()
        self.scenario_parser = ScenarioParser()

    def generate_report(self, profile: ApplicantProfile) -> PassportReadinessReport:
        policy = self.policy_guardian.evaluate(profile)
        fees = self.fee_calculator.calculate(profile, policy)
        checklist = self.document_architect.build(profile, policy)
        crew_result = self.crewai.run(profile, policy, fees, checklist)

        flags = list(dict.fromkeys([*policy.flags, *checklist.flags]))

        english_markdown = render_english_markdown(profile, policy, fees, checklist, flags)
        bangla_markdown = render_bangla_markdown(policy, fees, checklist, flags)
        combined_markdown = "\n\n".join(
            [
                "## Passport Readiness Report (English)",
                english_markdown,
                "## পাসপোর্ট প্রস্তুতি রিপোর্ট (বাংলা)",
                bangla_markdown,
            ]
        )

        return PassportReadinessReport(
            profile=profile,
            validity_years=policy.permitted_validity_years,
            delivery_type=profile.delivery_speed,
            required_identification=policy.required_identification,
            total_fee_bdt=fees.total_fee_bdt,
            base_fee_bdt=fees.base_fee_bdt,
            vat_bdt=fees.vat_bdt,
            documents_needed=checklist.documents,
            flags=flags,
            english_markdown=english_markdown,
            bangla_markdown=bangla_markdown,
            combined_markdown=combined_markdown,
            agent_trace=crew_result.trace,
        )

    def generate_report_from_scenario(
        self,
        scenario: str,
    ) -> PassportReadinessReport:
        profile = self.scenario_parser.parse(scenario)
        return self.generate_report(profile)

    def parse_scenario(self, scenario: str) -> ScenarioParseResult:
        return self.scenario_parser.parse_to_draft(scenario)
