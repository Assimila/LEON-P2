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

from common.uml_tools import load_uml_rows, write_csv


COMPANY_DIR = SCRIPT_DIR.parents[1]
DEFAULT_REPORT_PATH = COMPANY_DIR / "report" / "palm-oil-mill-list-july-december-2022.pdf"
DEFAULT_UML_CSV_PATH = COMPANY_DIR / "UML" / "UML-Dec-2024.csv"
DEFAULT_OUTPUT_DIR = COMPANY_DIR / "results" / "ferrero" / "uml"
UML_ID_PATTERN = re.compile(r"PO\d{10}")
ESTATE_COLUMN_PATTERN = re.compile(r"\bESTATE\b")


def load_pdf_pages(pdf_path: Path):
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit("pdftotext is required to process Ferrero PDF reports.") from exc
    return result.stdout.split("\f")


def page_has_mill_table(page_text: str) -> bool:
    upper = page_text.upper()
    return "UML ID NUMBER" in upper and ESTATE_COLUMN_PATTERN.search(upper) is None


def group_contiguous_pages(page_numbers):
    groups = []
    current = []
    for page_number in page_numbers:
        if not current or page_number == current[-1] + 1:
            current.append(page_number)
        else:
            groups.append(current)
            current = [page_number]
    if current:
        groups.append(current)
    return groups


def discover_sections(pages):
    mill_pages = [index for index, page in enumerate(pages, start=1) if page_has_mill_table(page)]
    groups = group_contiguous_pages(mill_pages)
    sections = []
    for idx, page_group in enumerate(groups, start=1):
        if idx == 1:
            name = "ferrero_core"
        elif idx == 2:
            name = "acquired_brands"
        else:
            name = f"section_{idx}"
        sections.append({"Section": name, "Pages": page_group})
    return sections


def extract_section_ids(pages, page_numbers):
    ids_by_key = {}
    raw_id_count = 0
    for page_number in page_numbers:
        page_text = pages[page_number - 1]
        ids = UML_ID_PATTERN.findall(page_text)
        raw_id_count += len(ids)
        for uml_id in ids:
            entry = ids_by_key.setdefault(uml_id, {"UML ID": uml_id, "Report Pages": [], "Occurrences": 0})
            entry["Occurrences"] += 1
            if page_number not in entry["Report Pages"]:
                entry["Report Pages"].append(page_number)
    ordered = list(ids_by_key.values())
    for row in ordered:
        row["Report Pages"] = ", ".join(str(page) for page in row["Report Pages"])
    return ordered, raw_id_count


def build_outputs(report_path: Path, uml_rows, uml_fieldnames):
    uml_by_id = {row["UML ID"]: row for row in uml_rows if row.get("UML ID")}
    pages = load_pdf_pages(report_path)
    sections = discover_sections(pages)
    if not sections:
        raise SystemExit("No Ferrero mill-list sections were detected in the PDF.")

    summary_rows = []
    matched_rows_by_section = {}
    missing_rows = []
    for section in sections:
        extracted_rows, raw_id_count = extract_section_ids(pages, section["Pages"])
        missing_ids = []
        matched_count = 0
        section_matched_rows = []
        for extracted in extracted_rows:
            uml_row = uml_by_id.get(extracted["UML ID"])
            if uml_row is None:
                missing_ids.append(extracted["UML ID"])
                missing_rows.append(
                    {
                        "Section": section["Section"],
                        "UML ID": extracted["UML ID"],
                        "Report Pages": extracted["Report Pages"],
                        "Occurrences": extracted["Occurrences"],
                    }
                )
                continue
            matched_count += 1
            section_matched_rows.append(
                {
                    "Section": section["Section"],
                    "Report Pages": extracted["Report Pages"],
                    "Occurrences": extracted["Occurrences"],
                    **uml_row,
                }
            )
        matched_rows_by_section[section["Section"]] = section_matched_rows

        summary_rows.append(
            {
                "Section": section["Section"],
                "Start Page": section["Pages"][0],
                "End Page": section["Pages"][-1],
                "Page Count": len(section["Pages"]),
                "Raw UML IDs": raw_id_count,
                "Unique UML IDs": len(extracted_rows),
                "Matched UML IDs": matched_count,
                "Missing UML IDs": len(missing_ids),
                "Missing UML ID List": "; ".join(missing_ids),
            }
        )

    summary_fieldnames = [
        "Section",
        "Start Page",
        "End Page",
        "Page Count",
        "Raw UML IDs",
        "Unique UML IDs",
        "Matched UML IDs",
        "Missing UML IDs",
        "Missing UML ID List",
    ]
    matched_fieldnames = ["Section", "Report Pages", "Occurrences", *uml_fieldnames]
    missing_fieldnames = ["Section", "UML ID", "Report Pages", "Occurrences"]
    return (
        summary_rows,
        summary_fieldnames,
        matched_rows_by_section,
        matched_fieldnames,
        missing_rows,
        missing_fieldnames,
    )


def main():
    parser = argparse.ArgumentParser(description="Extract Ferrero mill-list UML IDs and join them to UML rows.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Path to Ferrero PDF report")
    parser.add_argument("--uml-csv", default=str(DEFAULT_UML_CSV_PATH), help="Path to UML CSV")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for Ferrero outputs")
    args = parser.parse_args()

    report_path = Path(args.report)
    uml_csv_path = Path(args.uml_csv)
    output_dir = Path(args.output_dir)

    uml_rows, uml_fieldnames = load_uml_rows(uml_csv_path)
    summary_rows, summary_fieldnames, matched_rows_by_section, matched_fieldnames, missing_rows, missing_fieldnames = build_outputs(
        report_path, uml_rows, uml_fieldnames
    )

    stem = report_path.stem
    summary_output = output_dir / f"sections_{stem}.csv"
    missing_output = output_dir / f"missing_uml_ids_{stem}.csv"
    write_csv(summary_output, summary_rows, summary_fieldnames)
    match_outputs = {}
    for section_name, rows in matched_rows_by_section.items():
        path = output_dir / f"matched_mills_{section_name}_{stem}.csv"
        write_csv(path, rows, matched_fieldnames)
        match_outputs[section_name] = path
    write_csv(missing_output, missing_rows, missing_fieldnames)

    print(f"Sections found: {len(summary_rows)}")
    for row in summary_rows:
        print(
            f"{row['Section']}: pages={row['Start Page']}-{row['End Page']}, "
            f"unique_ids={row['Unique UML IDs']}, missing={row['Missing UML IDs']}"
        )
    for section_name, path in match_outputs.items():
        print(f"Matched mills ({section_name}): {path}")
    print(f"Section summary: {summary_output}")
    print(f"Missing UML IDs: {missing_output}")


if __name__ == "__main__":
    main()
