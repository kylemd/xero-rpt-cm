"""
Generate account-type reporting-code rules from financial report layouts and template charts.

Usage:
    uv run python tools/generate_account_type_rules.py

Outputs:
    SystemFiles/Account_Types_Fixed.json  (overwritten)
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import logging
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FINANCIAL_REPORTS = [
    PROJECT_ROOT / "financial-reports" / "Report01_Trading-Statement.json",
    PROJECT_ROOT / "financial-reports" / "Report02_Detailed-Profit-and-Loss.json",
    PROJECT_ROOT / "financial-reports" / "Report03_Balance-Sheet.json",
]
TEMPLATE_DIR = PROJECT_ROOT / "ChartOfAccounts"
OUTPUT_PATH = PROJECT_ROOT / "SystemFiles" / "Account_Types_Fixed.json"
logger = logging.getLogger("account_type_rules")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
ALLOW_AMBIGUOUS = os.getenv("ACCOUNT_RULES_ALLOW_AMBIGUOUS", "").lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class ReportContext:
    report: str
    path: Tuple[str, ...]


def load_report_codes() -> Dict[str, List[ReportContext]]:
    """Return mapping of reporting_code -> list of contexts gathered from report layouts."""

    def iter_nodes(node: dict, path: Tuple[str, ...], report_name: str):
        name = node.get("Name")
        node_type = str(node.get("$type", ""))
        include_name = "Layout.LayoutGroup" in node_type
        if include_name:
            if not isinstance(name, str) or not name.strip():
                logger.error("Missing hierarchy name for node in %s with path %s", report_name, path)
                raise ValueError(f"Missing hierarchy level in report {report_name}")
            next_path = path + (name,)
        else:
            next_path = path

        value = node.get("Value")
        if isinstance(value, str) and value.startswith("ReportCode::"):
            code = value.split("::", 1)[1]
            contexts[code].append(ReportContext(report=report_name, path=next_path))

        for child in node.get("Children", []) or []:
            if isinstance(child, dict):
                iter_nodes(child, next_path, report_name)

    contexts: Dict[str, List[ReportContext]] = defaultdict(list)
    for report_path in FINANCIAL_REPORTS:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        for child in data.get("Children", []) or []:
            if isinstance(child, dict):
                iter_nodes(child, tuple(), report_path.name)
    return contexts


def collect_type_usage() -> Tuple[Dict[str, set], Dict[str, str]]:
    """Return (report_code -> set(account types), normalized_type -> display name)."""
    code_to_types: Dict[str, set] = defaultdict(set)
    type_display: Dict[str, str] = {}

    for csv_path in sorted(TEMPLATE_DIR.glob("*.csv")):
        df = pd.read_csv(csv_path, dtype=str).fillna("")
        for _, row in df.iterrows():
            rc = str(row.get("Reporting Code", "") or "").strip()
            acc_type = str(row.get("Type", "") or "").strip()
            if not rc or not acc_type:
                continue
            norm = acc_type.lower()
            if norm not in type_display:
                type_display[norm] = acc_type
            code_to_types[rc].add(norm)
    return code_to_types, type_display


def determine_prefix(code: str) -> str:
    parts = code.split(".")
    if len(parts) <= 2:
        return code
    if parts[1] in {"CUR", "NCA"}:
        return ".".join(parts[:3])
    return ".".join(parts[:2])


def to_camel_case(text: str) -> str:
    words = [w for w in text.strip().split() if w]
    return " ".join(w.capitalize() if w else "" for w in words)


def normalise_path(path: Iterable[str]) -> List[str]:
    seen = set()
    normalised: List[str] = []
    for raw in path:
        if raw is None or str(raw).strip() == "":
            logger.error("Missing hierarchy level in path %s", list(path))
            raise ValueError(f"Missing hierarchy level in path {list(path)}")
        camel = to_camel_case(raw)
        key = camel.lower()
        if key in seen:
            message = f"Ambiguous hierarchy level '{camel}' in path {list(path)}"
            logger.error(message)
            if not ALLOW_AMBIGUOUS:
                raise ValueError(message)
            continue
        seen.add(key)
        normalised.append(camel)
    return normalised


def build_rules(
    report_codes: Dict[str, List[ReportContext]],
    code_to_types: Dict[str, set],
    type_display: Dict[str, str],
) -> Dict[str, dict]:
    type_to_codes: Dict[str, set] = defaultdict(set)
    for code, types in code_to_types.items():
        for t in types:
            type_to_codes[t].add(code)

    rules: Dict[str, dict] = {}
    for norm_type, codes in sorted(type_to_codes.items()):
        display = type_display.get(norm_type, norm_type.title())
        allowed_codes = sorted(codes)
        prefixes = sorted({determine_prefix(code) for code in allowed_codes})

        contexts = []
        seen_ctx = set()
        for code in allowed_codes:
            for ctx in report_codes.get(code, []):
                normalised_path = tuple(normalise_path(ctx.path))
                key = (ctx.report, normalised_path)
                if key in seen_ctx:
                    continue
                seen_ctx.add(key)
                contexts.append(
                    {
                        "report": ctx.report,
                        "hierarchy": list(normalised_path),
                    }
                )

        rules[display] = {
            "allowed_codes": allowed_codes,
            "allowed_prefixes": prefixes,
            "sections": contexts,
        }

    return rules


def main() -> None:
    report_codes = load_report_codes()
    code_to_types, type_display = collect_type_usage()
    rules = build_rules(report_codes, code_to_types, type_display)
    OUTPUT_PATH.write_text(json.dumps(rules, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
