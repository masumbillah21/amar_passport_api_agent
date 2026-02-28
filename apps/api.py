from __future__ import annotations

from fastapi import FastAPI
from fastapi import HTTPException

from passport_advisor.models import (
    ApplicantProfile,
    PassportReadinessReport,
    ScenarioInput,
    ScenarioParseResult,
)
from passport_advisor.service import PassportReadinessService

app = FastAPI(
    title="Bangladesh Passport Virtual Consular Officer",
    version="1.0.0",
    description="Deterministic passport readiness backend with optional CrewAI orchestration.",
)

service = PassportReadinessService()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/passport/report", response_model=PassportReadinessReport)
def build_passport_report(profile: ApplicantProfile) -> PassportReadinessReport:
    return service.generate_report(profile)


@app.post("/passport/text", response_model=PassportReadinessReport)
def build_passport_report_from_text(payload: ScenarioInput) -> PassportReadinessReport:
    try:
        return service.generate_report_from_scenario(scenario=payload.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/passport/parse", response_model=ScenarioParseResult)
def parse_passport_scenario(payload: ScenarioInput) -> ScenarioParseResult:
    return service.parse_scenario(scenario=payload.scenario)
