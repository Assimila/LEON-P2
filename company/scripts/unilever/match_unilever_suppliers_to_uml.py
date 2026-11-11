#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from common.uml_tools import load_uml_rows, normalize_company_name, write_csv


COMPANY_DIR = SCRIPT_DIR.parents[1]
DEFAULT_REPORT_PATH = COMPANY_DIR / "report" / "unilever-palm-oil-suppliers-2024.pdf"
DEFAULT_UML_CSV_PATH = COMPANY_DIR / "UML" / "UML-Dec-2024.csv"
DEFAULT_OUTPUT_DIR = COMPANY_DIR / "results" / "unilever" / "uml"

# Conservative aliases for known naming variants between the report and UML.
ALIAS_EXACT = {
    "golden agriresources": "golden agri resources",
}
ALIAS_PREFIX = {
    "new britain oils": "new britain palm oil",
    "perkebunan nusantara": "perkebunan nusantara",
}


def extract_suppliers(pdf_path: Path):
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("pdftotext is required to process the Unilever PDF report.") from exc

    suppliers = []
    for line in result.stdout.splitlines():
        match = re.match(r"^\s*(\d{1,3})\s+(.*?)\s*$", line)
        if not match:
            continue
        supplier_no = int(match.group(1))
        supplier_name = match.group(2).strip()
        if supplier_name.lower().startswith("page "):
            continue
        suppliers.append(
            {
                "Supplier No": supplier_no,
                "Supplier Name": supplier_name,
                "Normalized Supplier Name": normalize_company_name(supplier_name),
            }
        )
    return suppliers


def build_company_index(uml_rows):
    index = defaultdict(list)
    for row in uml_rows:
        for key in (row.get("_norm_group_company", ""), row.get("_norm_parent_company", "")):
            if key:
                index[key].append(row)
    return index


def dedupe_rows(rows):
    seen = set()
    deduped = []
    for row in rows:
        key = row.get("UML ID") or (row.get("Group Name"), row.get("Parent Company"), row.get("Mill Name"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def match_supplier(supplier_key: str, company_index):
    if supplier_key in company_index:
        return dedupe_rows(company_index[supplier_key]), "exact", supplier_key

    alias_exact_key = ALIAS_EXACT.get(supplier_key)
    if alias_exact_key and alias_exact_key in company_index:
        return dedupe_rows(company_index[alias_exact_key]), "alias_exact", alias_exact_key

    alias_prefix = ALIAS_PREFIX.get(supplier_key)
    if alias_prefix:
        rows = []
        for company_key, matches in company_index.items():
            if company_key.startswith(alias_prefix):
                rows.extend(matches)
        rows = dedupe_rows(rows)
        if rows:
            return rows, "alias_prefix", alias_prefix

    return [], "unmatched", ""


def summarize_values(rows, field):
    values = []
    seen = set()
    for row in rows:
        value = (row.get(field) or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return "; ".join(values)


def build_outputs(report_path: Path, uml_rows, uml_fieldnames):
    suppliers = extract_suppliers(report_path)
    company_index = build_company_index(uml_rows)

    summary_rows = []
    matched_rows = []
    for supplier in suppliers:
        supplier_key = supplier["Normalized Supplier Name"]
        matches, match_type, match_key = match_supplier(supplier_key, company_index)
        summary_rows.append(
            {
                **supplier,
                "Match Status": "matched" if matches else "unmatched",
                "Match Type": match_type,
                "Match Key": match_key,
                "Matched UML Rows": len(matches),
                "Matched UML IDs": summarize_values(matches, "UML ID"),
                "Matched Group Names": summarize_values(matches, "Group Name"),
                "Matched Parent Companies": summarize_values(matches, "Parent Company"),
                "Matched Countries": summarize_values(matches, "Country"),
            }
        )
        for match in matches:
            matched_rows.append(
                {
                    "Supplier No": supplier["Supplier No"],
                    "Supplier Name": supplier["Supplier Name"],
                    "Normalized Supplier Name": supplier_key,
                    "Match Type": match_type,
                    "Match Key": match_key,
                    **match,
                }
            )

    summary_fieldnames = [
        "Supplier No",
        "Supplier Name",
        "Normalized Supplier Name",
        "Match Status",
        "Match Type",
        "Match Key",
        "Matched UML Rows",
        "Matched UML IDs",
        "Matched Group Names",
        "Matched Parent Companies",
        "Matched Countries",
    ]
    matched_fieldnames = [
        "Supplier No",
        "Supplier Name",
        "Normalized Supplier Name",
        "Match Type",
        "Match Key",
        *uml_fieldnames,
    ]
    return summary_rows, summary_fieldnames, matched_rows, matched_fieldnames


def main():
    parser = argparse.ArgumentParser(description="Match Unilever tier-1 palm oil suppliers to UML companies.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Path to Unilever supplier PDF")
    parser.add_argument("--uml-csv", default=str(DEFAULT_UML_CSV_PATH), help="Path to UML CSV")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for CSV outputs")
    args = parser.parse_args()

    report_path = Path(args.report)
    uml_csv_path = Path(args.uml_csv)
    output_dir = Path(args.output_dir)

    uml_rows, uml_fieldnames = load_uml_rows(uml_csv_path)
    summary_rows, summary_fieldnames, matched_rows, matched_fieldnames = build_outputs(report_path, uml_rows, uml_fieldnames)

    stem = report_path.stem
    suppliers_output = output_dir / f"suppliers_{stem}.csv"
    matches_output = output_dir / f"matched_mills_{stem}.csv"
    write_csv(suppliers_output, summary_rows, summary_fieldnames)
    write_csv(matches_output, matched_rows, matched_fieldnames)

    matched_supplier_count = sum(1 for row in summary_rows if row["Match Status"] == "matched")
    unmatched_supplier_count = len(summary_rows) - matched_supplier_count
    print(f"Suppliers extracted: {len(summary_rows)}")
    print(f"Matched suppliers: {matched_supplier_count}")
    print(f"Unmatched suppliers: {unmatched_supplier_count}")
    print(f"Matched UML mill rows: {len(matched_rows)}")
    print(f"Supplier summary: {suppliers_output}")
    print(f"Matched mills: {matches_output}")


if __name__ == "__main__":
    main()
