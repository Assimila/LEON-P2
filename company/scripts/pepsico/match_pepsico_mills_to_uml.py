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
DEFAULT_REPORT_PATH = COMPANY_DIR / "report" / "2024-global-palm-oil-mill-list.pdf"
DEFAULT_UML_CSV_PATH = COMPANY_DIR / "UML" / "UML-Dec-2024.csv"
DEFAULT_OUTPUT_DIR = COMPANY_DIR / "results" / "pepsico" / "uml"

UML_TOKEN_PATTERN = re.compile(r"^PO\d{10}$", re.IGNORECASE)
NO_UML_PATTERN = re.compile(r"^NO UML ID$", re.IGNORECASE)
ROW_END_PATTERN = re.compile(r"(PO\d{10}|NO UML ID|No UML ID)\s*$")


def load_pdf_pages(pdf_path: Path):
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("pdftotext is required to process PepsiCo PDF reports.") from exc
    return result.stdout.split("\f")


def parse_row(parts, page_number):
    if len(parts) == 9:
        (
            group_company,
            parent_company,
            mill_name,
            latitude_text,
            longitude_text,
            country,
            state_or_province,
            district,
            uml_token,
        ) = parts
    elif len(parts) == 8:
        (
            group_company,
            parent_company,
            mill_name,
            latitude_text,
            longitude_text,
            country,
            state_or_province,
            uml_token,
        ) = parts
        district = ""
    else:
        return None

    if not UML_TOKEN_PATTERN.match(uml_token) and not NO_UML_PATTERN.match(uml_token):
        return None

    return {
        "Report Page": page_number,
        "Group Company": group_company.strip(),
        "Parent Company": parent_company.strip(),
        "Mill Name": mill_name.strip(),
        "Report Latitude": parse_decimal(latitude_text),
        "Report Longitude": parse_decimal(longitude_text),
        "Country": country.strip(),
        "State / Province": state_or_province.strip(),
        "District": district.strip(),
        "UML ID": uml_token.strip().upper(),
    }


def parse_rows(pages):
    rows = []
    in_table = False

    for page_number, page in enumerate(pages, start=1):
        for line in page.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if "Group Company" in stripped and "UML ID" in stripped:
                in_table = True
                continue
            if not in_table:
                continue
            if not ROW_END_PATTERN.search(stripped):
                continue

            row = parse_row(re.split(r"\s{2,}", stripped), page_number)
            if row is not None:
                rows.append(row)

    return rows


def build_outputs(report_path: Path, uml_rows, uml_fieldnames):
    uml_by_id = {row["UML ID"]: row for row in uml_rows if row.get("UML ID")}
    rows = parse_rows(load_pdf_pages(report_path))

    matched_rows = []
    no_uml_id_rows = []
    missing_uml_rows = []
    for row in rows:
        uml_id = row["UML ID"]
        if uml_id == "NO UML ID":
            no_uml_id_rows.append(row)
            continue
        uml_row = uml_by_id.get(uml_id)
        if uml_row is None:
            missing_uml_rows.append(row)
            continue
        matched_rows.append({**row, **uml_row})

    summary_rows = [
        {
            "Total Parsed Rows": len(rows),
            "Matched UML Rows": len(matched_rows),
            "Unique Matched Mills": len({row["UML ID"] for row in matched_rows}),
            "NO UML ID Rows": len(no_uml_id_rows),
            "Missing UML ID Rows": len(missing_uml_rows),
            "Unique Group Companies": len({row["Group Company"] for row in rows if row.get("Group Company")}),
            "Unique Parent Companies": len({row["Parent Company"] for row in rows if row.get("Parent Company")}),
            "Unique Countries": len({row["Country"] for row in rows if row.get("Country")}),
        }
    ]
    summary_fieldnames = [
        "Total Parsed Rows",
        "Matched UML Rows",
        "Unique Matched Mills",
        "NO UML ID Rows",
        "Missing UML ID Rows",
        "Unique Group Companies",
        "Unique Parent Companies",
        "Unique Countries",
    ]
    row_fieldnames = [
        "Report Page",
        "Group Company",
        "Parent Company",
        "Mill Name",
        "Report Latitude",
        "Report Longitude",
        "Country",
        "State / Province",
        "District",
        "UML ID",
    ]
    matched_fieldnames = [*row_fieldnames, *uml_fieldnames]
    return (
        summary_rows,
        summary_fieldnames,
        matched_rows,
        matched_fieldnames,
        no_uml_id_rows,
        missing_uml_rows,
        row_fieldnames,
    )


def main():
    parser = argparse.ArgumentParser(description="Parse PepsiCo palm oil mill disclosure and join mills to UML rows.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Path to PepsiCo PDF report")
    parser.add_argument("--uml-csv", default=str(DEFAULT_UML_CSV_PATH), help="Path to UML CSV")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for PepsiCo outputs")
    args = parser.parse_args()

    report_path = Path(args.report)
    uml_csv_path = Path(args.uml_csv)
    output_dir = Path(args.output_dir)

    uml_rows, uml_fieldnames = load_uml_rows(uml_csv_path)
    (
        summary_rows,
        summary_fieldnames,
        matched_rows,
        matched_fieldnames,
        no_uml_id_rows,
        missing_uml_rows,
        row_fieldnames,
    ) = build_outputs(report_path, uml_rows, uml_fieldnames)

    stem = report_path.stem
    summary_output = output_dir / f"summary_{stem}.csv"
    matched_output = output_dir / f"matched_mills_{stem}.csv"
    no_uml_output = output_dir / f"no_uml_id_rows_{stem}.csv"
    missing_output = output_dir / f"missing_uml_ids_{stem}.csv"
    write_csv(summary_output, summary_rows, summary_fieldnames, encoding="utf-8")
    write_csv(matched_output, matched_rows, matched_fieldnames, encoding="utf-8")
    write_csv(no_uml_output, no_uml_id_rows, row_fieldnames, encoding="utf-8")
    write_csv(missing_output, missing_uml_rows, row_fieldnames, encoding="utf-8")

    print(f"Total parsed rows: {summary_rows[0]['Total Parsed Rows']}")
    print(f"Matched UML rows: {summary_rows[0]['Matched UML Rows']}")
    print(f"Unique matched mills: {summary_rows[0]['Unique Matched Mills']}")
    print(f"NO UML ID rows: {summary_rows[0]['NO UML ID Rows']}")
    print(f"Missing UML ID rows: {summary_rows[0]['Missing UML ID Rows']}")
    print(f"Summary: {summary_output}")
    print(f"Matched mills: {matched_output}")
    print(f"NO UML ID rows: {no_uml_output}")
    print(f"Missing UML IDs: {missing_output}")


if __name__ == "__main__":
    main()
