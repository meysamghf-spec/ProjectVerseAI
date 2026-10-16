"""Deterministic natural-language requirement extraction.

Values found in the prompt or in structured fields are recorded as known.
Defaults applied by the application are recorded as assumptions. Nothing in
the assumption list is presented as something the user typed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.text import normalize_digits, normalize_for_search

WORD_NUMBERS = {
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
}

TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("construction", ["building", "construction", "residential", "tower", "basement", "storey", "story",
                      "ساختمان", "مسکونی", "برج", "زیرزمین", "اداری", "تجاری", "طبقه"]),
    ("software", ["software", "application", "mobile app", "web app", "api", "saas", "codebase",
                  "نرم افزار", "اپلیکیشن", "وب سایت", "سامانه", "اپ موبایل"]),
    ("manufacturing", ["manufacturing", "factory", "production line", "assembly plant", "fabrication",
                       "کارخانه", "خط تولید", "مونتاژ"]),
    ("infrastructure", ["highway", "bridge", "railway", "rail ", "infrastructure", "pipeline", "runway",
                        "بزرگراه", "آزادراه", "راه آهن", "تونل", "خط لوله", "زیرساخت", "سد ", "پل "]),
    ("urban", ["urban", "district", "neighborhood", "neighbourhood", "masterplan", "master plan", "city block",
               "شهری", "محله", "شهرک", "طرح جامع"]),
    ("logistics", ["logistics", "warehouse", "distribution", "supply chain", "fleet", "last mile",
                   "لجستیک", "انبار", "توزیع", "زنجیره تامین"]),
    ("research", ["research", "r&d", "laboratory", "experiment", "clinical", "پژوهش", "تحقیق", "آزمایشگاه"]),
    ("event", ["conference", "festival", "wedding", "exhibition", "event planning", "venue",
               "همایش", "جشنواره", "عروسی", "نمایشگاه"]),
]

PERSIAN_SCALES = {"هزار": 1e3, "میلیون": 1e6, "میلیارد": 1e9, "همت": 1e12, "تریلیون": 1e12}
_FA_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"


@dataclass
class FieldRecord:
    key: str
    value: object
    origin: str
    confidence: float
    note: str = ""


@dataclass
class Extraction:
    project_type: str
    project_type_origin: str
    known: list[FieldRecord] = field(default_factory=list)
    inferred: list[FieldRecord] = field(default_factory=list)
    assumptions: list[FieldRecord] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    original_prompt: str = ""
    confidence: float = 0.0
    values: dict = field(default_factory=dict)


def _number(token: str) -> float:
    return float(token.replace(",", ""))


def _word_or_number(token: str) -> int | None:
    lowered = token.lower()
    if lowered in WORD_NUMBERS:
        return WORD_NUMBERS[lowered]
    if re.fullmatch(r"\d+", token):
        return int(token)
    return None


def _classify(prompt: str, explicit: str | None) -> tuple[str, str, float]:
    if explicit:
        return explicit.strip().lower().replace(" ", "_").replace("-", "_"), "user", 1.0
    scores: dict[str, int] = {}
    lowered = normalize_for_search(prompt) + " "
    for name, keywords in TYPE_KEYWORDS:
        scores[name] = sum(1 for keyword in keywords if keyword in lowered)
    best = max(scores.values(), default=0)
    if best == 0:
        return "custom", "inferred", 0.3
    winners = [name for name, score in scores.items() if score == best]
    return winners[0], "inferred", min(0.9, 0.45 + 0.15 * best)


def _find_persian_money(prompt: str) -> tuple[float, str] | None:
    """'۱۵ میلیارد تومان' -> (150_000_000_000, 'IRR'); toman is stored as rial (x10). '2 میلیون دلار' -> USD."""

    match = re.search(_FA_NUM + r"\s*(هزار|میلیون|میلیارد|همت|تریلیون)?\s*(تومان|تومن|ریال|دلار|یورو)", prompt)
    if not match:
        match = re.search(_FA_NUM + r"\s*(همت)()", prompt)
    if not match:
        return None
    amount = _number(match.group(1)) * PERSIAN_SCALES.get(match.group(2) or "", 1)
    unit = match.group(3)
    if match.group(2) == "همت":
        unit = "تومان"  # همت = هزار میلیارد تومان
    if unit in {"تومان", "تومن"}:
        return amount * 10, "IRR"
    if unit == "ریال":
        return amount, "IRR"
    return amount, "USD" if unit == "دلار" else "EUR"


def _find_money(prompt: str) -> tuple[float, str] | None:
    persian = _find_persian_money(prompt)
    if persian:
        return persian
    patterns = [
        r"([$€£])\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(million|billion|m|bn)?",
        r"(\d+(?:\.\d+)?)\s*(million|billion)\s*(usd|dollars|eur|euros|gbp|pounds)?",
        r"\b(?:budget of|budget)\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\b",
    ]
    match = re.search(patterns[0], prompt, flags=re.IGNORECASE)
    if match:
        symbol, number, scale = match.group(1), _number(match.group(2)), (match.group(3) or "").lower()
        currency = {"$": "USD", "€": "EUR", "£": "GBP"}.get(symbol, "USD")
        amount = _scale(number, scale)
        return amount, currency
    match = re.search(patterns[1], prompt, flags=re.IGNORECASE)
    if match:
        number = _number(match.group(1))
        scale = match.group(2).lower()
        unit = (match.group(3) or "").lower()
        currency = "USD"
        if unit in {"eur", "euros"}:
            currency = "EUR"
        elif unit in {"gbp", "pounds"}:
            currency = "GBP"
        return _scale(number, scale), currency
    match = re.search(patterns[2], prompt, flags=re.IGNORECASE)
    if match:
        return _number(match.group(1)), "USD"
    return None


def _scale(number: float, scale: str) -> float:
    if scale in {"million", "m"}:
        return number * 1_000_000
    if scale in {"billion", "bn"}:
        return number * 1_000_000_000
    return number


def _find_area(prompt: str) -> tuple[float, str] | None:
    match = re.search(
        r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(square meters|square metres|sqm|sq\.?\s*m|m²|m2|square feet|sq\.?\s*ft|ft²|ft2)",
        prompt,
        flags=re.IGNORECASE,
    ) or re.search(_FA_NUM + r"\s*(متر\s*مربع|مترمربع)", prompt)
    if not match:
        return None
    value = _number(match.group(1))
    unit = match.group(2).lower()
    if "feet" in unit or "ft" in unit:
        return value * 0.092903, "sqft_converted"
    return value, "sqm"


def _find_count(prompt: str, pattern: str) -> int | None:
    match = re.search(pattern, prompt, flags=re.IGNORECASE)
    if not match:
        return None
    return _word_or_number(match.group(1))


def extract_requirements(prompt: str, structured: dict | None = None, today: date | None = None) -> Extraction:
    structured = structured or {}
    today = today or date.today()
    extraction = Extraction(project_type="custom", project_type_origin="inferred", original_prompt=prompt)
    # Persian/Arabic digits and separators become ASCII so the patterns below can read numbers.
    prompt = normalize_digits(prompt).replace("ي", "ی").replace("ك", "ک")

    project_type, origin, type_confidence = _classify(prompt, structured.get("category"))
    extraction.project_type = project_type
    extraction.project_type_origin = origin
    record_list = extraction.known if origin == "user" else extraction.inferred
    record_list.append(
        FieldRecord("project_type", project_type, origin, type_confidence, "Classification from keywords or the category field.")
    )

    floors = structured.get("floors")
    if floors is None:
        floors = _find_count(
            prompt,
            r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*[- ]?(?:story|stories|storey|storeys|floors?)",
        )
        if floors is None:
            floors = _find_count(prompt, r"(\d+)\s*طبقه(?!\s*(?:ی\s*)?(?:زیرزمین|منفی|پارکینگ))")
        if floors is not None:
            extraction.known.append(FieldRecord("floors", floors, "user", 0.95, "Read from the prompt."))
    else:
        extraction.known.append(FieldRecord("floors", int(floors), "user", 1.0, "Structured input."))

    basements = structured.get("basements")
    if basements is None:
        basements = _find_count(
            prompt,
            r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+basement",
        )
        if basements is None:
            basements = _find_count(prompt, r"(\d+)\s*طبقه\s*(?:ی\s*)?(?:زیرزمین|منفی|پارکینگ)")
        if basements is not None:
            extraction.known.append(FieldRecord("basements", basements, "user", 0.95, "Read from the prompt."))
    else:
        extraction.known.append(FieldRecord("basements", int(basements), "user", 1.0, "Structured input."))

    area = structured.get("gfa_sqm")
    area_note = "Structured input."
    if area is None:
        found = _find_area(prompt)
        if found:
            area, unit = found
            area_note = "Read from the prompt."
            if unit == "sqft_converted":
                extraction.assumptions.append(
                    FieldRecord(
                        "area_conversion",
                        0.092903,
                        "assumption",
                        0.7,
                        "Square feet were converted to square meters with the factor 0.092903.",
                    )
                )
                area_note = "Converted from square feet in the prompt."
            extraction.known.append(FieldRecord("gfa_sqm", area, "user", 0.9, area_note))
    else:
        extraction.known.append(FieldRecord("gfa_sqm", float(area), "user", 1.0, area_note))

    budget = structured.get("budget_amount")
    currency = structured.get("currency")
    if budget is None:
        found_money = _find_money(prompt)
        if found_money:
            budget, detected_currency = found_money
            currency = currency or detected_currency
            extraction.known.append(
                FieldRecord("budget_amount", budget, "user", 0.9, "Read from the prompt. This is a target, not a quotation.")
            )
            extraction.known.append(FieldRecord("currency", currency, "user", 0.8, "Inferred from the currency symbol or word."))
    else:
        extraction.known.append(FieldRecord("budget_amount", float(budget), "user", 1.0, "Structured input."))
        if currency:
            extraction.known.append(FieldRecord("currency", currency, "user", 1.0, "Structured input."))

    if structured.get("usd_exchange_rate"):
        extraction.known.append(
            FieldRecord("usd_exchange_rate", float(structured["usd_exchange_rate"]), "user", 1.0, "Structured input.")
        )

    months = structured.get("duration_months")
    if months is None:
        match = re.search(r"(\d+(?:\.\d+)?)\s*[- ]?months?", prompt, flags=re.IGNORECASE) or re.search(
            r"(\d+(?:\.\d+)?)\s*ماه", prompt
        )
        years = None if match else re.search(r"(\d{1,2}(?:\.\d+)?)\s*سال", prompt)
        if match:
            months = float(match.group(1))
        elif years:
            months = float(years.group(1)) * 12
        if months is not None:
            extraction.known.append(FieldRecord("duration_months", months, "user", 0.9, "Read from the prompt."))
    else:
        extraction.known.append(FieldRecord("duration_months", float(months), "user", 1.0, "Structured input."))

    name = structured.get("name")
    if name:
        extraction.known.append(FieldRecord("name", name, "user", 1.0, "Structured input."))
    else:
        extraction.assumptions.append(
            FieldRecord("name", _default_name(project_type), "assumption", 0.4, "No project name was provided.")
        )

    location = structured.get("location")
    if location:
        extraction.known.append(FieldRecord("location", location, "user", 1.0, "Structured input."))
    else:
        extraction.missing.append("location")

    start = structured.get("start_date")
    if start:
        extraction.known.append(FieldRecord("start_date", str(start), "user", 1.0, "Structured input."))
    else:
        extraction.missing.append("start_date")
        extraction.assumptions.append(
            FieldRecord(
                "start_date",
                today.isoformat(),
                "assumption",
                0.2,
                "No start date was provided. The extraction date is used so scheduling can proceed.",
            )
        )

    deadline = structured.get("deadline")
    if deadline:
        extraction.known.append(FieldRecord("deadline", str(deadline), "user", 1.0, "Structured input."))
    elif months is not None and start:
        extraction.missing.append("deadline")
    else:
        extraction.missing.append("deadline")

    team = structured.get("team_size")
    if team is None:
        match = re.search(
            r"team of\s+(\d+)|(\d+)\s+(?:people|person|staff)|(\d+)\s*نفر", prompt, flags=re.IGNORECASE
        )
        if match:
            team = int(match.group(1) or match.group(2) or match.group(3))
            extraction.known.append(FieldRecord("team_size", team, "user", 0.85, "Read from the prompt."))
        else:
            extraction.missing.append("team_size")
    else:
        extraction.known.append(FieldRecord("team_size", int(team), "user", 1.0, "Structured input."))

    if project_type == "construction":
        if floors is None:
            extraction.missing.append("floors")
            extraction.assumptions.append(
                FieldRecord("floors", 4, "assumption", 0.2, "Floor count was not stated. A 4-story placeholder is used.")
            )
            floors = 4
        if basements is None:
            extraction.missing.append("basements")
            extraction.assumptions.append(
                FieldRecord("basements", 0, "assumption", 0.3, "Basement count was not stated and defaults to zero.")
            )
            basements = 0
        if area is None:
            extraction.missing.append("gfa_sqm")
            extraction.assumptions.append(
                FieldRecord(
                    "gfa_sqm",
                    float(floors) * 800.0,
                    "assumption",
                    0.2,
                    "Gross floor area was not stated. 800 square meters per floor is a placeholder.",
                )
            )
        extraction.assumptions.append(
            FieldRecord("floor_to_floor_height_m", 3.2, "assumption", 0.35, "Typical planning placeholder, not a measured story height.")
        )
        extraction.assumptions.append(
            FieldRecord("basement_height_m", 3.0, "assumption", 0.35, "Basement story height placeholder.")
        )
        extraction.assumptions.append(
            FieldRecord("aspect_ratio", 1.5, "assumption", 0.3, "Plan aspect ratio length/width used only for the conceptual massing.")
        )
    if currency and not any(record.key == "currency" for record in extraction.known):
        extraction.known.append(FieldRecord("currency", currency, "user", 1.0, "Structured input."))
    if currency is None:
        currency = "USD"
        extraction.assumptions.append(
            FieldRecord("currency", "USD", "assumption", 0.3, "No currency was stated. USD is the editable default.")
        )
    extraction.assumptions.append(
        FieldRecord("month_length_days", 30, "assumption", 0.5, "A planning month is 30 calendar days in this model.")
    )
    extraction.assumptions.append(
        FieldRecord(
            "work_calendar",
            {"skip_weekends": False, "hours_per_day": 8, "days_per_week": 7, "holiday_dates": []},
            "assumption",
            0.4,
            "The default calendar counts every calendar day as a working day.",
        )
    )

    for optional in ("labor_rates", "material_prices", "equipment", "constraints", "risk_tolerance"):
        if structured.get(optional) in (None, "", [], {}):
            extraction.missing.append(optional)
        else:
            extraction.known.append(
                FieldRecord(optional, structured.get(optional), "user", 1.0, "Structured input.")
            )

    extraction.warnings.append(
        "Extracted numbers are planning inputs. They are not a measured survey, a quotation, or an engineering design."
    )
    extraction.values = _collapse(extraction)
    extraction.confidence = _confidence(extraction)
    return extraction


def _default_name(project_type: str) -> str:
    labels = {
        "construction": "Construction project",
        "software": "Software project",
        "manufacturing": "Manufacturing project",
        "infrastructure": "Infrastructure project",
        "urban": "Urban development",
        "logistics": "Logistics project",
        "research": "Research project",
        "event": "Event plan",
        "custom": "Custom project",
    }
    return labels.get(project_type, "Project")


def _collapse(extraction: Extraction) -> dict:
    values: dict = {}
    for bucket in (extraction.assumptions, extraction.inferred, extraction.known):
        for record in bucket:
            values[record.key] = record.value
    values["project_type"] = extraction.project_type
    return values


def _confidence(extraction: Extraction) -> float:
    known = len(extraction.known)
    assumed = len(extraction.assumptions)
    missing = len(extraction.missing)
    total = known + assumed + missing
    if total == 0:
        return 0.2
    # Coverage of user-provided fields. This is not a statistical confidence interval.
    score = known / total
    return round(max(0.15, min(0.9, score)), 2)
