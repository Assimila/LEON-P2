#!/usr/bin/env python3
import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from common.uml_tools import load_uml_rows, write_csv


COMPANY_DIR = SCRIPT_DIR.parents[1]
DEFAULT_REPORT_PATH = COMPANY_DIR / "report" / "responsible-sourcing-disclosure-palm-oil.pdf"
DEFAULT_UML_CSV_PATH = COMPANY_DIR / "UML" / "UML-Dec-2024.csv"
DEFAULT_OUTPUT_DIR = COMPANY_DIR / "results" / "nestle" / "uml"

UML_TOKEN_PATTERN = re.compile(r"^(PO\d{10})(\*)?$", re.IGNORECASE)
NO_UML_PATTERN = re.compile(r"^NO UML MATCH$", re.IGNORECASE)
ROW_END_PATTERN = re.compile(r"(PO\d{10}\*?|NO UML MATCH|No UML Match)\s*$")


def load_pdf_pages(pdf_path: Path):
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("pdftotext is required to process Nestle PDF reports.") from exc
    return result.stdout.split("\f")


def split_middle_fields(parts):
    middle = parts[1:-2]
    if len(middle) == 1:
        return middle[0], ""
    if len(middle) == 2:
        return middle[0], middle[1]
    if len(middle) == 3:
        return " ".join(middle[:2]), middle[2]
    split_idx = len(middle) // 2
    return " ".join(middle[:split_idx]), " ".join(middle[split_idx:])


def parse_rows(pages):
    rows = []
    in_table = False

    for page_number, page in enumerate(pages, start=1):
        for line in page.splitlines():
            if not line.strip():
                continue
            if "Direct Supplier" in line and "UML ID" in line:
                in_table = True
                continue
            if not in_table:
                continue
            if not ROW_END_PATTERN.search(line):
                continue

            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) < 4:
                continue

            supplier = parts[0].strip()
            country = parts[-2].strip()
            uml_token = parts[-1].strip()
            mill_company, mill_name = split_middle_fields(parts)

            uml_match = UML_TOKEN_PATTERN.match(uml_token)
            no_uml_match = NO_UML_PATTERN.match(uml_token)
            if uml_match:
                uml_id = uml_match.group(1).upper()
                no_buy_flag = "yes" if uml_match.group(2) else "no"
            elif no_uml_match:
                uml_id = "NO UML MATCH"
                no_buy_flag = "no"
            else:
                continue

            rows.append(
                {
                    "Report Page": page_number,
                    "Direct Supplier": supplier,
                    "Mill Company": mill_company.strip(),
                    "Mill Name": mill_name.strip(),
                    "Country": country,
                    "UML ID": uml_id,
                    "No Buy Flag": no_buy_flag,
                }
            )
    return rows


def build_outputs(report_path: Path, uml_rows, uml_fieldnames):
    uml_by_id = {row["UML ID"]: row for row in uml_rows if row.get("UML ID")}
    rows = parse_rows(load_pdf_pages(report_path))

    matched_rows = []
    no_uml_match_rows = []
    missing_uml_rows = []
    for row in rows:
        uml_id = row["UML ID"]
        if uml_id == "NO UML MATCH":
            no_uml_match_rows.append(row)
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
            "NO UML MATCH Rows": len(no_uml_match_rows),
            "Missing UML ID Rows": len(missing_uml_rows),
            "Unique Direct Suppliers": len({row["Direct Supplier"] for row in rows}),
            "Unique Mill Companies": len({row["Mill Company"] for row in rows}),
        }
    ]

    summary_fieldnames = [
        "Total Parsed Rows",
        "Matched UML Rows",
        "Unique Matched Mills",
        "NO UML MATCH Rows",
        "Missing UML ID Rows",
        "Unique Direct Suppliers",
        "Unique Mill Companies",
    ]
    row_fieldnames = ["Report Page", "Direct Supplier", "Mill Company", "Mill Name", "Country", "UML ID", "No Buy Flag"]
    matched_fieldnames = [*row_fieldnames, *uml_fieldnames]
    unique_matched_rows = build_unique_mill_rows(matched_rows, uml_fieldnames)
    unique_matched_fieldnames = [
        "UML ID",
        "Occurrence Count",
        "Direct Supplier Count",
        "Direct Suppliers",
        "Report Pages",
        "Any No Buy Flag",
        "Reported Mill Companies",
        "Reported Mill Names",
        "Reported Countries",
        *uml_fieldnames[1:],
    ]
    return (
        summary_rows,
        summary_fieldnames,
        matched_rows,
        matched_fieldnames,
        unique_matched_rows,
        unique_matched_fieldnames,
        no_uml_match_rows,
        row_fieldnames,
        missing_uml_rows,
    )


def build_unique_mill_rows(matched_rows, uml_fieldnames):
    rows_by_id = collections.defaultdict(list)
    for row in matched_rows:
        rows_by_id[row["UML ID"]].append(row)

    unique_rows = []
    for uml_id, rows in sorted(rows_by_id.items()):
        base = {field: rows[0].get(field, "") for field in uml_fieldnames}
        suppliers = sorted({row["Direct Supplier"] for row in rows if row.get("Direct Supplier")})
        pages = sorted({int(row["Report Page"]) for row in rows if row.get("Report Page")})
        reported_companies = sorted({row["Mill Company"] for row in rows if row.get("Mill Company")})
        reported_names = sorted({row["Mill Name"] for row in rows if row.get("Mill Name")})
        reported_countries = sorted({row["Country"] for row in rows if row.get("Country")})
        unique_rows.append(
            {
                "UML ID": uml_id,
                "Occurrence Count": len(rows),
                "Direct Supplier Count": len(suppliers),
                "Direct Suppliers": "; ".join(suppliers),
                "Report Pages": ", ".join(str(page) for page in pages),
                "Any No Buy Flag": "yes" if any(row.get("No Buy Flag") == "yes" for row in rows) else "no",
                "Reported Mill Companies": "; ".join(reported_companies),
                "Reported Mill Names": "; ".join(reported_names),
                "Reported Countries": "; ".join(reported_countries),
                **base,
            }
        )
    return unique_rows


def main():
    parser = argparse.ArgumentParser(description="Parse Nestle palm oil disclosure and join mills to UML rows.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Path to Nestle PDF report")
    parser.add_argument("--uml-csv", default=str(DEFAULT_UML_CSV_PATH), help="Path to UML CSV")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for Nestle outputs")
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
        unique_matched_rows,
        unique_matched_fieldnames,
        no_uml_match_rows,
        row_fieldnames,
        missing_uml_rows,
    ) = build_outputs(report_path, uml_rows, uml_fieldnames)

    stem = report_path.stem
    summary_output = output_dir / f"summary_{stem}.csv"
    matched_output = output_dir / f"matched_mills_{stem}.csv"
    unique_matched_output = output_dir / f"unique_mills_{stem}.csv"
    no_uml_output = output_dir / f"no_uml_match_rows_{stem}.csv"
    missing_output = output_dir / f"missing_uml_ids_{stem}.csv"
    write_csv(summary_output, summary_rows, summary_fieldnames, encoding="utf-8")
    write_csv(matched_output, matched_rows, matched_fieldnames, encoding="utf-8")
    write_csv(unique_matched_output, unique_matched_rows, unique_matched_fieldnames, encoding="utf-8")
    write_csv(no_uml_output, no_uml_match_rows, row_fieldnames, encoding="utf-8")
    write_csv(missing_output, missing_uml_rows, row_fieldnames, encoding="utf-8")

    print(f"Total parsed rows: {summary_rows[0]['Total Parsed Rows']}")
    print(f"Matched UML rows: {summary_rows[0]['Matched UML Rows']}")
    print(f"Unique matched mills: {summary_rows[0]['Unique Matched Mills']}")
    print(f"NO UML MATCH rows: {summary_rows[0]['NO UML MATCH Rows']}")
    print(f"Missing UML ID rows: {summary_rows[0]['Missing UML ID Rows']}")
    print(f"Summary: {summary_output}")
    print(f"Matched mills: {matched_output}")
    print(f"Unique mills: {unique_matched_output}")
    print(f"NO UML MATCH rows: {no_uml_output}")
    print(f"Missing UML IDs: {missing_output}")


if __name__ == "__main__":
    main()
