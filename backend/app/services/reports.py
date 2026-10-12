"""Downloadable reports rendered from persisted project and simulation data."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone

from fpdf import FPDF
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Project, Report
from app.services.serialize import project_detail, scenario_payload

REPORT_TYPES = {"summary", "schedule", "budget", "resources", "risks", "scenarios", "full"}
FORMATS = {"json", "csv", "pdf", "xlsx"}


def _safe_cell(value) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_safe_cell(cell) for cell in row])
    return buffer.getvalue().encode("utf-8")


def collect_document(db: Session, project: Project) -> dict:
    detail = project_detail(db, project, include_samples=True)
    scenarios = [scenario_payload(db, row) for row in project.scenarios]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": get_settings().engine_version,
        "disclaimer": (
            "This report reproduces values stored by ProjectVerse AI. "
            "Assumptions and simulation timestamps are included. "
            "It is not a verified quotation, bid, or engineering certification."
        ),
        "project": {
            "id": detail["id"],
            "name": detail["name"],
            "category": detail["category"],
            "summary": detail["summary"],
            "currency": detail["currency"],
            "budget_amount": detail["budget_amount"],
            "start_date": detail["start_date"],
            "deadline": detail["deadline"],
            "confidence": detail["confidence"],
            "scene": detail["scene"],
            "specification": detail["specification"],
            "assumptions": detail["assumptions"],
            "validation": detail["validation"],
        },
        "tasks": detail["tasks"],
        "dependencies": detail["dependencies"],
        "cost_summary": detail["cost_summary"],
        "resources": detail["resources"],
        "risks": detail["risks"],
        "milestones": detail["milestones"],
        "deterministic": detail["latest_simulation"],
        "monte_carlo": detail["latest_monte_carlo"],
        "scenarios": scenarios,
    }


def _task_rows(document: dict) -> tuple[list[str], list[list]]:
    headers = [
        "code",
        "name",
        "phase",
        "duration",
        "start_offset",
        "finish_offset",
        "total_float",
        "critical",
        "baseline_finish",
        "start_date",
        "finish_date",
        "status",
    ]
    rows = [
        [
            task["code"],
            task["name"],
            task["phase"],
            task["duration"],
            task["start_offset"],
            task["finish_offset"],
            task["total_float"],
            task["is_critical"],
            task["baseline_finish"],
            task["start_date"],
            task["finish_date"],
            task["status"],
        ]
        for task in document["tasks"]
        if not task["is_summary"]
    ]
    return headers, rows


def _budget_rows(document: dict) -> tuple[list[str], list[list]]:
    summary = document["cost_summary"] or {"lines": [], "total": None, "variance": None}
    headers = ["code", "name", "category", "phase", "amount", "source", "source_date", "include_in_total", "notes"]
    rows = [
        [
            line["code"],
            line["name"],
            line["category"],
            line["phase"],
            line["amount"],
            line["source"],
            line["source_date"],
            line["include_in_total"],
            line["notes"],
        ]
        for line in summary["lines"]
    ]
    return headers, rows


def _risk_rows(document: dict) -> tuple[list[str], list[list]]:
    headers = ["code", "title", "category", "probability", "impact_cost", "impact_schedule_days", "score", "mitigation", "status"]
    rows = [
        [
            risk["code"],
            risk["title"],
            risk["category"],
            risk["probability"],
            risk["impact_cost"],
            risk["impact_schedule_days"],
            risk["score"],
            risk["mitigation"],
            risk["status"],
        ]
        for risk in document["risks"]
    ]
    return headers, rows


def _resource_rows(document: dict) -> tuple[list[str], list[list]]:
    peaks = []
    deterministic = document.get("deterministic") or {}
    result = deterministic.get("result") or {}
    for item in result.get("resource_peaks") or []:
        peaks.append([item["id"], item["name"], item["available"], item["peak"], item["overloaded"]])
    headers = ["code", "name", "available", "peak", "overloaded"]
    if not peaks:
        headers = ["code", "name", "available", "rate", "rate_source", "rate_date"]
        peaks = [
            [row["code"], row["name"], row["available"], row["rate"], row["rate_source"], row["rate_date"]]
            for row in document["resources"]
        ]
    return headers, peaks


def _scenario_rows(document: dict) -> tuple[list[str], list[list]]:
    headers = ["name", "description", "duration", "cost", "deadline_probability", "budget_probability", "notes"]
    rows = []
    for scenario in document["scenarios"]:
        det = ((scenario.get("deterministic") or {}).get("result")) or {}
        mc = ((scenario.get("monte_carlo") or {}).get("result")) or {}
        rows.append(
            [
                scenario["name"],
                scenario["description"],
                det.get("project_duration"),
                det.get("total_cost"),
                mc.get("deadline_probability"),
                mc.get("budget_probability"),
                " | ".join(scenario.get("notes") or []),
            ]
        )
    return headers, rows


def render_csv(document: dict, report_type: str) -> tuple[bytes, str]:
    sections = {
        "schedule": ("schedule.csv", _task_rows),
        "budget": ("budget.csv", _budget_rows),
        "resources": ("resources.csv", _resource_rows),
        "risks": ("risks.csv", _risk_rows),
        "scenarios": ("scenarios.csv", _scenario_rows),
    }
    if report_type in sections:
        filename, builder = sections[report_type]
        headers, rows = builder(document)
        return _csv_bytes(headers, rows), "text/csv"
    if report_type == "summary":
        project = document["project"]
        det = (document.get("deterministic") or {}).get("result") or {}
        headers = ["field", "value"]
        rows = [
            ["name", project["name"]],
            ["generated_at", document["generated_at"]],
            ["engine_version", document["engine_version"]],
            ["duration", det.get("project_duration")],
            ["total_cost", det.get("total_cost")],
            ["budget_variance", det.get("budget_variance")],
            ["disclaimer", document["disclaimer"]],
        ]
        return _csv_bytes(headers, rows), "text/csv"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, builder in (
            ("tasks.csv", _task_rows),
            ("budget.csv", _budget_rows),
            ("resources.csv", _resource_rows),
            ("risks.csv", _risk_rows),
            ("scenarios.csv", _scenario_rows),
        ):
            headers, rows = builder(document)
            archive.writestr(name, _csv_bytes(headers, rows))
        archive.writestr(
            "meta.json",
            json.dumps(
                {
                    "generated_at": document["generated_at"],
                    "engine_version": document["engine_version"],
                    "disclaimer": document["disclaimer"],
                },
                indent=2,
            ),
        )
    return buffer.getvalue(), "application/zip"


def _pdf_lines(document: dict, report_type: str) -> list[str]:
    project = document["project"]
    det = (document.get("deterministic") or {}).get("result") or {}
    mc = (document.get("monte_carlo") or {}).get("result") or {}
    lines = [
        "ProjectVerse AI report",
        f"Project: {project['name']}",
        f"Generated: {document['generated_at']}",
        f"Engine: {document['engine_version']}",
        document["disclaimer"],
        "",
        f"Category: {project['category']}",
        f"Summary: {project['summary']}",
        f"Budget target: {project['budget_amount']} {project['currency']}",
        f"Confidence score (coverage, not a statistical interval): {project['confidence']}",
    ]
    if report_type in {"summary", "full", "schedule"}:
        lines.append("")
        lines.append("Schedule")
        lines.append(
            f"Deterministic duration: {det.get('project_duration')} days. "
            f"Critical path: {', '.join(det.get('critical_path') or []) or 'not calculated'}"
        )
        for task in document["tasks"]:
            if task["is_summary"]:
                continue
            lines.append(
                f"{task['code']} {task['name']}: {task['duration']} days, "
                f"float {task['total_float']}, critical={task['is_critical']}"
            )
    if report_type in {"summary", "full", "budget"} and document["cost_summary"]:
        summary = document["cost_summary"]
        lines.append("")
        lines.append(
            f"Cost total {summary['total']} variance {summary['variance']} overrun {summary['overrun']}"
        )
        for line in summary["lines"]:
            if not line["include_in_total"]:
                continue
            lines.append(f"{line['category']} {line['name']}: {line['amount']} ({line['source']} {line['source_date']})")
    if report_type in {"summary", "full"} and mc:
        lines.append("")
        lines.append(
            f"Monte Carlo seed {mc.get('seed')} iterations {mc.get('iterations')}: "
            f"P50 {mc.get('result', {}).get('p50_duration') if mc.get('result') else None}"
        )
        result = mc.get("result") or {}
        lines.append(
            f"P50/P80/P90 duration {result.get('p50_duration')} / {result.get('p80_duration')} / {result.get('p90_duration')}"
        )
        lines.append(
            f"P50/P80/P90 cost {result.get('p50_cost')} / {result.get('p80_cost')} / {result.get('p90_cost')}"
        )
        lines.append(f"Deadline probability: {result.get('deadline_probability')}")
        lines.append(f"Budget probability: {result.get('budget_probability')}")
    if report_type in {"risks", "full", "summary"}:
        lines.append("")
        lines.append("Risks")
        for risk in document["risks"]:
            lines.append(
                f"{risk['code']} {risk['title']} p={risk['probability']} score={risk['score']}"
            )
    if report_type in {"scenarios", "full", "summary"}:
        lines.append("")
        lines.append("Scenarios")
        for scenario in document["scenarios"]:
            det_s = ((scenario.get("deterministic") or {}).get("result")) or {}
            lines.append(
                f"{scenario['name']}: duration {det_s.get('project_duration')} cost {det_s.get('total_cost')}"
            )
            for note in scenario.get("notes") or []:
                lines.append(f"  change: {note}")
    if report_type in {"resources", "full"}:
        lines.append("")
        lines.append("Resources")
        _, rows = _resource_rows(document)
        for row in rows:
            lines.append(" | ".join(str(cell) for cell in row))
    spec = project.get("specification") or {}
    lines.append("")
    lines.append("Recorded assumptions")
    for item in (spec.get("assumptions") or [])[:12]:
        lines.append(f"{item.get('key')}: {item.get('note') or item.get('value')}")
    return lines


def _pdf_text(value: str) -> str:
    safe = value.encode("latin-1", "replace").decode("latin-1").replace("\n", " ").strip()
    words = []
    for word in safe.split(" "):
        while len(word) > 90:
            words.append(word[:90])
            word = word[90:]
        if word:
            words.append(word)
    return " ".join(words)


def render_pdf(document: dict, report_type: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    width = pdf.epw
    for line in _pdf_lines(document, report_type):
        text = _pdf_text(line)
        pdf.set_x(pdf.l_margin)
        if not text:
            pdf.ln(4)
            continue
        pdf.multi_cell(width, 5, text)
    return bytes(pdf.output())


def render_xlsx(document: dict, report_type: str) -> bytes:
    workbook = Workbook()
    sheets = {
        "Summary": [["field", "value"], ["name", document["project"]["name"]], ["generated_at", document["generated_at"]], ["engine", document["engine_version"]], ["disclaimer", document["disclaimer"]]],
    }
    if report_type in {"schedule", "full", "summary"}:
        headers, rows = _task_rows(document)
        sheets["Schedule"] = [headers, *rows]
    if report_type in {"budget", "full", "summary"}:
        headers, rows = _budget_rows(document)
        sheets["Budget"] = [headers, *rows]
    if report_type in {"resources", "full"}:
        headers, rows = _resource_rows(document)
        sheets["Resources"] = [headers, *rows]
    if report_type in {"risks", "full", "summary"}:
        headers, rows = _risk_rows(document)
        sheets["Risks"] = [headers, *rows]
    if report_type in {"scenarios", "full", "summary"}:
        headers, rows = _scenario_rows(document)
        sheets["Scenarios"] = [headers, *rows]
    first = True
    for title, rows in sheets.items():
        worksheet = workbook.active if first else workbook.create_sheet(title)
        worksheet.title = title
        first = False
        for row in rows:
            worksheet.append([_safe_cell(cell) if isinstance(cell, str) else cell for cell in row])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def render_report(document: dict, report_format: str, report_type: str) -> tuple[bytes, str, str]:
    if report_format not in FORMATS or report_type not in REPORT_TYPES:
        raise ValueError("Unsupported report format or type.")
    stamp = document["generated_at"].replace(":", "").replace("-", "")
    project_id = document["project"]["id"][:8]
    if report_format == "json":
        payload = document if report_type == "full" else {key: document[key] for key in _json_keys(report_type)}
        payload = {
            "generated_at": document["generated_at"],
            "engine_version": document["engine_version"],
            "disclaimer": document["disclaimer"],
            **payload,
        }
        return json.dumps(payload, indent=2, default=str).encode("utf-8"), "application/json", f"projectverse-{project_id}-{report_type}-{stamp}.json"
    if report_format == "csv":
        body, media = render_csv(document, report_type)
        extension = "zip" if media == "application/zip" else "csv"
        return body, media, f"projectverse-{project_id}-{report_type}-{stamp}.{extension}"
    if report_format == "pdf":
        return render_pdf(document, report_type), "application/pdf", f"projectverse-{project_id}-{report_type}-{stamp}.pdf"
    body = render_xlsx(document, report_type)
    return body, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"projectverse-{project_id}-{report_type}-{stamp}.xlsx"


def _json_keys(report_type: str) -> dict:
    mapping = {
        "summary": ["project", "deterministic", "monte_carlo"],
        "schedule": ["tasks", "dependencies", "deterministic"],
        "budget": ["cost_summary", "deterministic"],
        "resources": ["resources", "deterministic"],
        "risks": ["risks"],
        "scenarios": ["scenarios", "deterministic"],
    }
    return {key: True for key in mapping[report_type]}


def store_report(db: Session, project: Project, report_format: str, report_type: str, filename: str, document: dict) -> Report:
    deterministic = document.get("deterministic") or {}
    row = Report(
        project_id=project.id,
        run_id=deterministic.get("id"),
        format=report_format,
        report_type=report_type,
        filename=filename,
        metadata_json={
            "generated_at": document["generated_at"],
            "engine_version": document["engine_version"],
            "disclaimer": document["disclaimer"],
            "has_monte_carlo": document.get("monte_carlo") is not None,
        },
    )
    db.add(row)
    db.flush()
    return row
