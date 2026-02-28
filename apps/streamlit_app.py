from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
ENV_FILE_PATH = Path("/app/.env")
TRUTHY_VALUES = {"1", "true", "yes", "on"}
PROFESSION_OPTIONS = [
    "private_sector",
    "government_staff",
    "student",
    "business_owner",
    "other",
]
DELIVERY_OPTIONS = ["regular", "express", "super_express"]
VALIDITY_OPTIONS = ["Automatic", "5 years", "10 years"]

st.set_page_config(
    page_title="Bangladesh Passport Virtual Consular Officer",
    layout="wide",
)

st.title("Bangladesh Passport Virtual Consular Officer")
st.caption("Paste one natural-language scenario and get a readiness report.")

default_scenario = (
    "I am a 24-year-old private sector employee. I need a 64-page passport urgently "
    "because I have a business trip in two weeks. I have an NID and I live in Dhaka."
)

if "parsed_scenario" not in st.session_state:
    st.session_state["parsed_scenario"] = None
if "passport_report" not in st.session_state:
    st.session_state["passport_report"] = None


def _show_agent_thinking_enabled() -> bool:
    # Prefer the mounted .env file so UI toggles follow runtime config changes.
    if ENV_FILE_PATH.exists():
        try:
            for raw_line in ENV_FILE_PATH.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "SHOW_AGENT_THINKING":
                    return value.strip().lower() in TRUTHY_VALUES
        except OSError:
            pass
    return os.getenv("SHOW_AGENT_THINKING", "true").strip().lower() in TRUTHY_VALUES


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}{path}",
        json=payload,
        timeout=30,
    )
    if not response.ok:
        detail = None
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = None
        if isinstance(response_payload, dict):
            detail = response_payload.get("detail")
        message = detail or response.text or response.reason
        raise requests.HTTPError(message, response=response)
    return response.json()


def _option_index(options: list[Any], value: Any, fallback: int = 0) -> int:
    if value in options:
        return options.index(value)
    return fallback


def _draft_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


with st.form("scenario_parse_form"):
    scenario = st.text_area(
        "Applicant Scenario",
        key="scenario_input",
        value=default_scenario,
        height=180,
        help="Describe the applicant in plain English.",
    )
    parse_submitted = st.form_submit_button("Parse Scenario", use_container_width=True)

if parse_submitted:
    try:
        parsed = _post_json(
            "/passport/parse",
            {"scenario": scenario.strip()},
        )
    except requests.RequestException as exc:
        st.error(f"Backend request failed: {exc}")
    else:
        st.session_state["parsed_scenario"] = parsed
        st.session_state["passport_report"] = None

parsed_scenario = st.session_state.get("parsed_scenario")
passport_report = st.session_state.get("passport_report")

if parsed_scenario:
    draft = parsed_scenario["draft"]
    parser_notes = parsed_scenario.get("parser_notes", [])
    missing_fields = parsed_scenario.get("missing_fields", [])

    st.subheader("Review Details")
    st.caption("The app extracts what it can, then you confirm the final values before the report is generated.")

    if parser_notes:
        st.info("\n".join(parser_notes))
    if missing_fields:
        st.warning(
            "Please review the highlighted missing details before generating: "
            + ", ".join(missing_fields)
        )

    with st.form("review_details_form"):
        left_col, right_col = st.columns(2)

        with left_col:
            age_text = st.text_input(
                "Age",
                value="" if draft.get("age") is None else str(draft["age"]),
            )
            profession = st.selectbox(
                "Profession",
                options=PROFESSION_OPTIONS,
                index=_option_index(PROFESSION_OPTIONS, draft.get("profession"), fallback=4),
            )
            page_count = st.radio(
                "Page Count",
                options=[48, 64],
                index=_option_index([48, 64], draft.get("page_count"), fallback=0),
                horizontal=True,
            )
            delivery_speed = st.selectbox(
                "Delivery Speed",
                options=DELIVERY_OPTIONS,
                index=_option_index(DELIVERY_OPTIONS, draft.get("delivery_speed"), fallback=0),
            )
            requested_validity_label = st.selectbox(
                "Requested Validity",
                options=VALIDITY_OPTIONS,
                index=_option_index(
                    VALIDITY_OPTIONS,
                    {
                        None: "Automatic",
                        5: "5 years",
                        10: "10 years",
                    }.get(draft.get("requested_validity_years"), "Automatic"),
                ),
            )

        with right_col:
            has_nid = st.checkbox(
                "Applicant has NID",
                value=_draft_bool(draft.get("has_nid"), True),
            )
            has_birth_registration = st.checkbox(
                "Applicant has Birth Registration (English)",
                value=_draft_bool(draft.get("has_birth_registration"), False),
            )
            has_profession_proof = st.checkbox(
                "Applicant can provide profession proof",
                value=_draft_bool(draft.get("has_profession_proof"), True),
            )
            name_changed = st.checkbox(
                "Applicant has name-change documents",
                value=_draft_bool(draft.get("name_changed"), False),
            )
            location = st.text_input(
                "Location",
                value=draft.get("location") or "",
            )

        generate_submitted = st.form_submit_button("Generate Report", use_container_width=True)

    if generate_submitted:
        validation_errors: list[str] = []
        age_value: int | None = None

        stripped_age = age_text.strip()
        if not stripped_age:
            validation_errors.append("Age is required.")
        elif not stripped_age.isdigit():
            validation_errors.append("Age must be a whole number.")
        else:
            age_value = int(stripped_age)
            if not 0 <= age_value <= 120:
                validation_errors.append("Age must be between 0 and 120.")

        if validation_errors:
            st.error("\n".join(validation_errors))
        else:
            requested_validity_map = {"Automatic": None, "5 years": 5, "10 years": 10}
            payload = {
                "age": age_value,
                "profession": profession,
                "page_count": page_count,
                "delivery_speed": delivery_speed,
                "requested_validity_years": requested_validity_map[requested_validity_label],
                "has_nid": has_nid,
                "has_birth_registration": has_birth_registration,
                "has_profession_proof": has_profession_proof,
                "name_changed": name_changed,
                "location": location.strip() or None,
            }
            try:
                report = _post_json("/passport/report", payload)
            except requests.RequestException as exc:
                st.error(f"Backend request failed: {exc}")
            else:
                st.session_state["passport_report"] = report
                passport_report = report

if passport_report:
    st.subheader("Readiness Report")

    metric_col1, metric_col2 = st.columns(2)
    metric_col1.metric("Validity", f"{passport_report['validity_years']} Years")
    metric_col2.metric("Total Fee", f"{passport_report['total_fee_bdt']} BDT")

    if passport_report["flags"]:
        st.warning("\n".join(passport_report["flags"]))

    st.markdown(passport_report["combined_markdown"])

    if _show_agent_thinking_enabled() and passport_report.get("agent_trace"):
        with st.expander("Agent Thinking"):
            st.code(passport_report["agent_trace"], language="text")

    st.json(
        {
            "required_identification": passport_report["required_identification"],
            "documents_needed": passport_report["documents_needed"],
        }
    )
