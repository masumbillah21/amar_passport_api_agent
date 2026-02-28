from __future__ import annotations

from datetime import date
import re

from passport_advisor.models import (
    ApplicantProfile,
    ApplicantProfileDraft,
    DeliverySpeed,
    Profession,
    ScenarioParseResult,
)

SMALL_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
TENS_NUMBER_WORDS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
NUMBER_TOKEN_PATTERN = r"(\d{1,4}|[a-z]+(?:[\s-][a-z]+){0,2})"


class ScenarioParser:
    """Parse a simple natural-language passport scenario into an applicant profile."""

    def parse_to_draft(self, scenario: str) -> ScenarioParseResult:
        text = self._normalize_text(scenario)

        age = self._extract_age(text)
        profession = self._extract_profession(text)
        page_count = self._extract_page_count(text)
        delivery_speed = self._extract_delivery_speed(text)
        requested_validity_years = self._extract_requested_validity(text)
        has_nid = self._extract_document_status(
            text,
            ["nid", "national id", "national id card"],
        )
        has_birth_registration = self._extract_document_status(
            text,
            ["birth registration", "birth certificate", "birth reg"],
        )
        has_profession_proof = self._extract_optional_boolean(
            text,
            positive_candidates=[
                "i have profession proof",
                "i can provide profession proof",
                "i have office id",
                "i have employment proof",
            ],
            negative_candidates=[
                "no profession proof",
                "without profession proof",
                "do not have profession proof",
                "don't have profession proof",
                "cannot provide profession proof",
            ],
        )
        name_changed = self._extract_optional_boolean(
            text,
            positive_candidates=[
                "name changed",
                "marriage certificate",
                "changed my name",
                "have an affidavit",
                "i changed my surname",
            ],
            negative_candidates=[
                "name not changed",
                "my name has not changed",
            ],
        )
        location = self._extract_location(scenario)

        draft = ApplicantProfileDraft(
            age=age,
            profession=profession,
            page_count=page_count,
            delivery_speed=delivery_speed,
            requested_validity_years=requested_validity_years,
            has_nid=has_nid,
            has_birth_registration=has_birth_registration,
            has_profession_proof=has_profession_proof,
            name_changed=name_changed,
            location=location,
        )

        missing_fields: list[str] = []
        parser_notes: list[str] = []

        if age is None:
            missing_fields.append("age")
            parser_notes.append("Age was not clearly identified. Please enter it before generating.")
        if profession is None:
            parser_notes.append("Profession was not explicit. Review the profession before generating.")
        if page_count is None:
            parser_notes.append("Page count was not explicit. Review 48 pages vs 64 pages.")
        if delivery_speed is None:
            parser_notes.append("Delivery speed was not explicit. Review regular, express, or super express.")
        if has_nid is None:
            parser_notes.append("NID availability was not explicit. Review the identity document details.")
        if age is not None and age < 18 and has_birth_registration is None:
            parser_notes.append("Birth registration was not explicit for a minor applicant.")

        return ScenarioParseResult(
            draft=draft,
            missing_fields=missing_fields,
            parser_notes=parser_notes,
        )

    def parse(self, scenario: str) -> ApplicantProfile:
        result = self.parse_to_draft(scenario)
        draft = result.draft
        if draft.age is None:
            raise ValueError("Could not determine applicant age from the input scenario.")

        return ApplicantProfile(
            age=draft.age,
            profession=draft.profession or Profession.OTHER,
            page_count=draft.page_count or 48,
            delivery_speed=draft.delivery_speed or DeliverySpeed.REGULAR,
            requested_validity_years=draft.requested_validity_years,
            has_nid=True if draft.has_nid is None else draft.has_nid,
            has_birth_registration=False
            if draft.has_birth_registration is None
            else draft.has_birth_registration,
            has_profession_proof=True
            if draft.has_profession_proof is None
            else draft.has_profession_proof,
            name_changed=False if draft.name_changed is None else draft.name_changed,
            location=draft.location,
        )

    @staticmethod
    def _normalize_text(scenario: str) -> str:
        return " ".join(scenario.lower().strip().split())

    @staticmethod
    def _contains_any(text: str, candidates: list[str]) -> bool:
        return any(candidate in text for candidate in candidates)

    @staticmethod
    def _extract_age(text: str) -> int | None:
        patterns = [
            rf"\b{NUMBER_TOKEN_PATTERN}\s*-\s*year\s*-\s*old\b",
            rf"\b{NUMBER_TOKEN_PATTERN}\s*years?\s*old\b",
            rf"\b(?:age|aged|i am|i'm|im)\s+{NUMBER_TOKEN_PATTERN}\b",
            rf"\b{NUMBER_TOKEN_PATTERN}\s*(?:yo|y/o)\b",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = ScenarioParser._to_number_phrase(match.group(1))
                if value is not None:
                    return value

        birth_year_match = re.search(r"\bborn in (\d{4})\b", text)
        if birth_year_match:
            birth_year = int(birth_year_match.group(1))
            current_year = date.today().year
            if 1900 <= birth_year <= current_year:
                return current_year - birth_year
        return None

    @staticmethod
    def _extract_profession(text: str) -> Profession | None:
        if (
            "private sector" in text
            or "private employee" in text
            or "private sector employee" in text
            or "corporate employee" in text
            or "job holder" in text
            or "working in a company" in text
        ):
            return Profession.PRIVATE_SECTOR
        if any(
            phrase in text
            for phrase in [
                "government officer",
                "government employee",
                "government staff",
                "govt officer",
                "govt employee",
                "govt staff",
                "public servant",
                "civil servant",
            ]
        ) or ("government" in text or "govt" in text):
            return Profession.GOVERNMENT_STAFF
        if "student" in text:
            return Profession.STUDENT
        if any(
            phrase in text
            for phrase in [
                "business owner",
                "businessman",
                "businesswoman",
                "entrepreneur",
                "run a business",
                "own a business",
                "trader",
            ]
        ):
            return Profession.BUSINESS_OWNER
        if any(
            phrase in text
            for phrase in [
                "employee",
                "engineer",
                "developer",
                "teacher",
                "doctor",
                "consultant",
                "freelancer",
                "officer",
            ]
        ):
            return Profession.PRIVATE_SECTOR
        return None

    @staticmethod
    def _extract_page_count(text: str) -> int | None:
        patterns = [
            rf"\b{NUMBER_TOKEN_PATTERN}\s*-\s*page\b",
            rf"\b{NUMBER_TOKEN_PATTERN}\s*pages?\b",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = ScenarioParser._to_number_phrase(match.group(1))
                if value in {48, 64}:
                    return value
        return None

    @staticmethod
    def _extract_delivery_speed(text: str) -> DeliverySpeed | None:
        if "super express" in text:
            return DeliverySpeed.SUPER_EXPRESS
        if "asap" in text or "emergency" in text:
            return DeliverySpeed.EXPRESS
        deadline_days = ScenarioParser._extract_deadline_days(text)
        if deadline_days is not None:
            if deadline_days <= 3:
                return DeliverySpeed.SUPER_EXPRESS
            if deadline_days <= 14:
                return DeliverySpeed.EXPRESS
            return DeliverySpeed.REGULAR
        if "express" in text or "urgent" in text or "urgently" in text:
            return DeliverySpeed.EXPRESS
        if "regular" in text or "normal delivery" in text:
            return DeliverySpeed.REGULAR
        return None

    @staticmethod
    def _extract_requested_validity(text: str) -> int | None:
        patterns = [
            rf"\b{NUMBER_TOKEN_PATTERN}\s*-\s*year\b",
            rf"\b{NUMBER_TOKEN_PATTERN}\s*years?\b",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                value = ScenarioParser._to_number_phrase(match.group(1))
                if value in {5, 10}:
                    return value
        return None

    @staticmethod
    def _extract_location(scenario: str) -> str | None:
        patterns = [
            r"\bi live in\s+([a-zA-Z .'-]+)",
            r"\bi am based in\s+([a-zA-Z .'-]+)",
            r"\bi am located in\s+([a-zA-Z .'-]+)",
            r"\bfrom\s+([a-zA-Z .'-]+)",
            r"\blocation is\s+([a-zA-Z .'-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, scenario, flags=re.IGNORECASE)
            if match:
                location = re.split(
                    r"\b(?:and|with|because|but|so|for)\b",
                    match.group(1),
                    maxsplit=1,
                    flags=re.IGNORECASE,
                )[0].strip(" .,'\"")
                return location or None
        return None

    @staticmethod
    def _extract_document_status(text: str, aliases: list[str]) -> bool | None:
        for alias in aliases:
            negative_patterns = [
                rf"\bdo not have (?:an? )?{re.escape(alias)}\b",
                rf"\bdon't have (?:an? )?{re.escape(alias)}\b",
                rf"\bdo not have my {re.escape(alias)}\b",
                rf"\bdo not have {re.escape(alias)}\b",
                rf"\bdon't have {re.escape(alias)}\b",
                rf"\bwithout (?:an? )?{re.escape(alias)}\b",
                rf"\bno {re.escape(alias)}\b",
                rf"\bhave no {re.escape(alias)}\b",
                rf"\bmy {re.escape(alias)} is missing\b",
            ]
            if any(re.search(pattern, text) for pattern in negative_patterns):
                return False

        for alias in aliases:
            positive_patterns = [
                rf"\bi have (?:an? )?{re.escape(alias)}\b",
                rf"\bi have my {re.escape(alias)}\b",
                rf"\bwith (?:an? )?{re.escape(alias)}\b",
                rf"\bhas (?:an? )?{re.escape(alias)}\b",
            ]
            if any(re.search(pattern, text) for pattern in positive_patterns):
                return True

        return None

    @staticmethod
    def _extract_optional_boolean(
        text: str,
        positive_candidates: list[str],
        negative_candidates: list[str],
    ) -> bool | None:
        if ScenarioParser._contains_any(text, negative_candidates):
            return False
        if ScenarioParser._contains_any(text, positive_candidates):
            return True
        return None

    @staticmethod
    def _extract_deadline_days(text: str) -> int | None:
        if "today" in text or "tonight" in text:
            return 0
        if "tomorrow" in text:
            return 1
        if "next week" in text:
            return 7

        patterns = [
            rf"\bwithin\s+{NUMBER_TOKEN_PATTERN}\s+(hour|hours|day|days|week|weeks)\b",
            rf"\bneed(?: it| this| the passport| passport)?\s+(?:within|in)\s+{NUMBER_TOKEN_PATTERN}\s+(hour|hours|day|days|week|weeks)\b",
            rf"\bby\s+{NUMBER_TOKEN_PATTERN}\s+(hour|hours|day|days|week|weeks)\b",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                quantity = ScenarioParser._to_number_phrase(match.group(1))
                if quantity is None:
                    continue
                unit = match.group(2)
                if unit.startswith("hour"):
                    return max(1, (quantity + 23) // 24)
                if unit.startswith("week"):
                    return quantity * 7
                return quantity
        return None

    @staticmethod
    def _to_number_phrase(value: str) -> int | None:
        normalized = value.lower().replace("-", " ").strip()
        if normalized.isdigit():
            return int(normalized)

        parts = [part for part in normalized.split() if part and part != "and"]
        if not parts:
            return None
        if len(parts) == 1:
            return SMALL_NUMBER_WORDS.get(parts[0], TENS_NUMBER_WORDS.get(parts[0]))
        if len(parts) == 2 and parts[0] in TENS_NUMBER_WORDS and parts[1] in SMALL_NUMBER_WORDS:
            return TENS_NUMBER_WORDS[parts[0]] + SMALL_NUMBER_WORDS[parts[1]]
        return None
