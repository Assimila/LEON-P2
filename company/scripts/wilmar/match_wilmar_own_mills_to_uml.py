#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from common.uml_tools import load_uml_rows, parse_decimal, write_csv


COMPANY_DIR = SCRIPT_DIR.parents[1]
DEFAULT_REPORT_PATH = COMPANY_DIR / "report" / "wilmar-own-mill_wilmar-sustainability-241231.pdf"
DEFAULT_UML_CSV_PATH = COMPANY_DIR / "UML" / "UML-Dec-2024.csv"
DEFAULT_OUTPUT_DIR = COMPANY_DIR / "results" / "wilmar" / "uml"

ROW_START_PATTERN = re.compile(r"^\s*(\d+)\s{2,}(.*)$")
COUNTRIES = {"Indonesia", "Malaysia", "Ghana", "Nigeria"}
def is_header_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped == "Wilmar Own Mill List":
        return True
    if stripped.startswith("No") and "Parent company" in stripped and "UML ID" in stripped:
        return True
    if stripped.startswith("Last Updated"):
        return True
    return False


def load_pdf_text(pdf_path: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("pdftotext is required to process Wilmar PDF reports.") from exc
    return result.stdout


def parse_certifications(parts):
    values = list(parts)
    while len(values) < 4:
        values.insert(0, "")
    values = values[-4:]
    return {
        "RSPO Reported": values[0],
        "MSPO Reported": values[1],
        "ISPO Reported": values[2],
        "ISCC Reported": values[3],
    }


def is_continuation_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped in COUNTRIES:
        return False
    if stripped.startswith("*"):
        return False
    return not is_header_line(stripped)


def parse_rows(text: str):
    current_country = ""
    rows = []
    pending_prefix = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in COUNTRIES:
            current_country = stripped
            continue
        if stripped.startswith("*") or is_header_line(stripped):
            continue

        row_match = ROW_START_PATTERN.match(line)
        if row_match:
            parts = re.split(r"\s{2,}", stripped)
            if len(parts) < 6:
                continue
            row_no = parts[0]
            parent_company = parts[1]
            mill_name_raw = parts[2]
            uml_id = parts[3]
            latitude = parse_decimal(parts[4].replace("°", ""))
            longitude = parse_decimal(parts[5].replace("°", ""))
            address = parts[6] if len(parts) >= 7 else ""
            certifications = parse_certifications(parts[7:])
            if pending_prefix:
                prefix = " ".join(pending_prefix).strip()
                address = f"{prefix} {address}".strip() if address else prefix
                pending_prefix = []

            rows.append(
                {
                    "Report Country": current_country,
                    "Report Row No": row_no,
                    "Report Parent Company": parent_company,
                    "Report Mill Name": mill_name_raw.rstrip("*").strip(),
                    "Independent Mill Flag": "yes" if mill_name_raw.endswith("*") else "no",
                    "UML ID": uml_id,
                    "Report Latitude": latitude,
                    "Report Longitude": longitude,
                    "Report Address": address,
                    **certifications,
                }
            )
            continue

        if not rows:
            pending_prefix.append(stripped)
            continue
        if is_continuation_line(line):
            if rows[-1]["Report Address"]:
                pending_prefix.append(stripped)
            else:
                rows[-1]["Report Address"] = stripped

    if pending_prefix and rows:
        suffix = " ".join(pending_prefix).strip()
        rows[-1]["Report Address"] = f"{rows[-1]['Report Address']} {suffix}".strip()

    return rows


def build_outputs(report_path: Path, uml_rows, uml_fieldnames):
    uml_by_id = {row["UML ID"]: row for row in uml_rows if row.get("UML ID")}
    rows = parse_rows(load_pdf_text(report_path))

    matched_rows = []
    missing_rows = []
    for row in rows:
        uml_row = uml_by_id.get(row["UML ID"])
        if uml_row is None:
            missing_rows.append(row)
            continue
        matched_rows.append({**row, **uml_row})

    summary_rows = [
        {
            "Total Parsed Rows": len(rows),
            "Matched UML Rows": len(matched_rows),
            "Missing UML ID Rows": len(missing_rows),
            "Unique Report Countries": len({row["Report Country"] for row in rows}),
            "Independent Mill Rows": sum(1 for row in rows if row["Independent Mill Flag"] == "yes"),
        }
    ]
    summary_fieldnames = [
        "Total Parsed Rows",
        "Matched UML Rows",
        "Missing UML ID Rows",
        "Unique Report Countries",
        "Independent Mill Rows",
    ]
    row_fieldnames = [
        "Report Country",
        "Report Row No",
        "Report Parent Company",
        "Report Mill Name",
        "Independent Mill Flag",
        "UML ID",
        "Report Latitude",
        "Report Longitude",
        "Report Address",
        "RSPO Reported",
        "MSPO Reported",
        "ISPO Reported",
        "ISCC Reported",
    ]
    matched_fieldnames = [*row_fieldnames, *uml_fieldnames]
    return summary_rows, summary_fieldnames, matched_rows, matched_fieldnames, missing_rows, row_fieldnames


def main():
    parser = argparse.ArgumentParser(description="Parse Wilmar own mill disclosure and join rows to UML.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Path to Wilmar PDF report")
    parser.add_argument("--uml-csv", default=str(DEFAULT_UML_CSV_PATH), help="Path to UML CSV")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for Wilmar outputs")
    args = parser.parse_args()

    report_path = Path(args.report)
    uml_csv_path = Path(args.uml_csv)
    output_dir = Path(args.output_dir)

    uml_rows, uml_fieldnames = load_uml_rows(uml_csv_path)
    summary_rows, summary_fieldnames, matched_rows, matched_fieldnames, missing_rows, row_fieldnames = build_outputs(
        report_path, uml_rows, uml_fieldnames
    )

    stem = report_path.stem
    summary_output = output_dir / f"summary_{stem}.csv"
    matched_output = output_dir / f"matched_mills_{stem}.csv"
    missing_output = output_dir / f"missing_uml_ids_{stem}.csv"
    write_csv(summary_output, summary_rows, summary_fieldnames, encoding="utf-8")
    write_csv(matched_output, matched_rows, matched_fieldnames, encoding="utf-8")
    write_csv(missing_output, missing_rows, row_fieldnames, encoding="utf-8")

    print(f"Total parsed rows: {summary_rows[0]['Total Parsed Rows']}")
    print(f"Matched UML rows: {summary_rows[0]['Matched UML Rows']}")
    print(f"Missing UML ID rows: {summary_rows[0]['Missing UML ID Rows']}")
    print(f"Summary: {summary_output}")
    print(f"Matched mills: {matched_output}")
    print(f"Missing UML IDs: {missing_output}")


if __name__ == "__main__":
    main()
