#!/usr/bin/env python3
"""Audit and optionally standardize all user first/last names.

Default mode is read-only and writes an XLSX audit report.  Use ``--apply``
only after reviewing the generated report; every update is parameterized and
only applies deterministic formatting/transliteration, never guessed spelling.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import get_conn
from name_standardization import is_latin_name, potential_duplicate_key, standardize_legacy_name


def display_name(row: dict, first: str, last: str) -> str:
    return f"{first} {last}".strip() or f"USER #{int(row.get('id') or 0)}"


def role_for(login_type: int) -> str:
    return {1: "new_student", 2: "existing_student", 3: "teacher", 4: "admin", 5: "support"}.get(login_type, f"type_{login_type}")


def audit_rows(rows: list[dict]) -> list[dict]:
    audited: list[dict] = []
    for row in rows:
        old_first = str(row.get("first_name") or "").strip()
        old_last = str(row.get("last_name") or "").strip()
        proposed_first = standardize_legacy_name(old_first)
        proposed_last = standardize_legacy_name(old_last)
        issues: list[str] = []
        if not old_first or not old_last:
            issues.append("missing_name")
        if not is_latin_name(proposed_first) or not is_latin_name(proposed_last):
            issues.append("manual_review_invalid_characters")
        if old_first != proposed_first or old_last != proposed_last:
            if any("\u0400" <= char <= "\u052F" for char in f"{old_first}{old_last}"):
                issues.append("cyrillic_transliterated")
            else:
                issues.append("canonical_uppercase_or_apostrophe")
        audited.append({
            "id": int(row.get("id") or 0),
            "login_id": str(row.get("login_id") or ""),
            "role": role_for(int(row.get("login_type") or 0)),
            "old_first": old_first,
            "old_last": old_last,
            "new_first": proposed_first,
            "new_last": proposed_last,
            "old_full": display_name(row, old_first, old_last),
            "new_full": display_name(row, proposed_first, proposed_last),
            "issues": ", ".join(issues) or "already_standard",
            "can_apply": not any(issue.startswith("manual_review") or issue == "missing_name" for issue in issues),
            "changed": old_first != proposed_first or old_last != proposed_last,
            "exact_key": f"{proposed_first}|{proposed_last}",
            "potential_key": potential_duplicate_key(proposed_first, proposed_last),
        })
    return audited


def duplicate_groups(audited: list[dict], key_name: str, *, potential_only: bool) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in audited:
        if item[key_name].strip("|"):
            groups[item[key_name]].append(item)
    groups = {key: values for key, values in groups.items() if len(values) > 1}
    if potential_only:
        groups = {
            key: values
            for key, values in groups.items()
            if len({item["exact_key"] for item in values}) > 1
        }
    return dict(sorted(groups.items()))


def style_sheet(sheet) -> None:
    header_fill = PatternFill("solid", fgColor="1F4E78")
    warning_fill = PatternFill("solid", fgColor="FFF2CC")
    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = header_fill
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        values = [len(str(cell.value or "")) for cell in column]
        sheet.column_dimensions[column[0].column_letter].width = min(52, max(12, max(values, default=12) + 2))
    for row in sheet.iter_rows(min_row=2):
        if any("manual_review" in str(cell.value or "") or "cyrillic" in str(cell.value or "") for cell in row):
            for cell in row:
                cell.fill = warning_fill


def write_report(path: Path, audited: list[dict], exact: dict[str, list[dict]], potential: dict[str, list[dict]], applied: int) -> None:
    workbook = Workbook()
    summary = workbook.active
    summary.title = "SUMMARY"
    summary.append(["User name standardization report", datetime.now().isoformat(timespec="seconds")])
    summary.append(["Total users", len(audited)])
    summary.append(["Rows needing change", sum(1 for item in audited if item["changed"])])
    summary.append(["Rows updated in this run", applied])
    summary.append(["Manual-review rows", sum(1 for item in audited if not item["can_apply"])])
    summary.append(["Exact duplicate groups", len(exact)])
    summary.append(["Potential spelling duplicate groups", len(potential)])
    style_sheet(summary)

    audit = workbook.create_sheet("NAME AUDIT")
    audit.append(["USER ID", "LOGIN ID", "ROLE", "OLD FIRST NAME", "OLD LAST NAME", "HOW IT WAS WRITTEN", "NEW FIRST NAME", "NEW LAST NAME", "STANDARD FORM", "STATUS / REASON", "CAN APPLY", "CHANGED", "EXACT DUPLICATE KEY", "POTENTIAL DUPLICATE KEY"])
    for item in audited:
        audit.append([
            item["id"], item["login_id"], item["role"], item["old_first"], item["old_last"], item["old_full"],
            item["new_first"], item["new_last"], item["new_full"], item["issues"], "YES" if item["can_apply"] else "NO",
            "YES" if item["changed"] else "NO", item["exact_key"], item["potential_key"],
        ])
    style_sheet(audit)

    for title, groups, label in (("EXACT DUPLICATES", exact, "STANDARD FULL NAME"), ("POTENTIAL DUPLICATES", potential, "SIMILARITY KEY")):
        sheet = workbook.create_sheet(title)
        sheet.append([label, "USER ID", "LOGIN ID", "OLD FULL NAME", "STANDARD FULL NAME", "STATUS / REASON"])
        for key, members in groups.items():
            for item in members:
                sheet.append([key, item["id"], item["login_id"], item["old_full"], item["new_full"], item["issues"]])
        style_sheet(sheet)

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply safe deterministic name updates after creating the report")
    parser.add_argument("--report", type=Path, required=True, help="destination XLSX path")
    args = parser.parse_args()

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, login_id, login_type, first_name, last_name FROM users ORDER BY id ASC")
        audited = audit_rows([dict(row) for row in (cur.fetchall() or [])])
        exact = duplicate_groups(audited, "exact_key", potential_only=False)
        potential = duplicate_groups(audited, "potential_key", potential_only=True)
        applied = 0
        if args.apply:
            for item in audited:
                if not item["changed"] or not item["can_apply"]:
                    continue
                cur.execute(
                    "UPDATE users SET first_name=?, last_name=? WHERE id=?",
                    (item["new_first"], item["new_last"], item["id"]),
                )
                applied += int(cur.rowcount or 0)
            conn.commit()
        write_report(args.report, audited, exact, potential, applied)
    finally:
        conn.close()
    print(f"report:{args.report} applied:{applied} exact_duplicate_groups:{len(exact)} potential_duplicate_groups:{len(potential)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
