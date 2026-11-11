#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

import pdfplumber


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = SCRIPT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from common.uml_tools import haversine_km, load_uml_rows, normalize_text, parse_decimal, write_csv


COMPANY_DIR = SCRIPT_DIR.parents[1]
DEFAULT_UML_CSV_PATH = COMPANY_DIR / "UML" / "UML-Dec-2024.csv"
DEFAULT_REPORT_PATTERNS = (
    "danone-overall-mill-list-*.pdf",
    "mill-and-plantation-list-*.pdf",
)
DEFAULT_OUTPUT_DIR = COMPANY_DIR / "results" / "danone" / "uml"


def _clean_header(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _canonical_header(value: str, *, for_part_b: bool) -> str:
    cleaned = _clean_header(value)
    key = re.sub(r"[^a-z0-9]+", "", cleaned.lower())
    if key == "latitude":
        return "Latitude"
    if key == "longitude":
        return "Longitude"
    if key == "plantationlatitude":
        return "Plantation Latitude"
    if key in ("plantationlongitude", "plantationlong", "plantationlongi", "plantationlongitud"):
        return "Plantation Longitude"
    if key in ("starlingmillid", "umlid", "umllid", "umleid"):
        return "UML ID"
    if for_part_b and key.startswith("partb"):
        return "UML ID"
    return cleaned


def _is_part_a_header(headers):
    header_set = {header.lower() for header in headers if header}
    has_latlon = "latitude" in header_set and "longitude" in header_set
    has_mill_name = any("mill name" in header.lower() for header in headers if header)
    has_plantation = any("plantation" in header.lower() for header in headers if header)
    return has_latlon and has_mill_name and not has_plantation


def _is_part_b_header(headers):
    normalized = [re.sub(r"[^a-z0-9]+", "", header.lower()) for header in headers if header]
    return any("plantation" in header for header in normalized)


def extract_danone_part_a(pdf_path: Path):
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        last_page = min(len(pdf.pages), 8)
        for page_index in range(1, last_page):
            page = pdf.pages[page_index]
            for table in page.extract_tables():
                if not table or not table[0]:
                    continue
                headers = [_canonical_header(header, for_part_b=False) for header in table[0]]
                if not _is_part_a_header(headers):
                    continue
                for row in table[1:]:
                    if not any(row):
                        continue
                    cleaned = [(cell or "").replace("\n", " ").strip() for cell in row]
                    record = dict(zip(headers, cleaned))
                    record["Latitude"] = parse_decimal(record.get("Latitude", ""))
                    record["Longitude"] = parse_decimal(record.get("Longitude", ""))
                    rows.append(record)
    return rows


def extract_danone_part_b(pdf_path: Path):
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) <= 8:
            return rows
        last_page = min(len(pdf.pages), 28)
        for page_index in range(8, last_page):
            page = pdf.pages[page_index]
            for table in page.extract_tables():
                if not table or not table[0]:
                    continue
                headers = [_canonical_header(header, for_part_b=True) for header in table[0]]
                if not _is_part_b_header(headers):
                    continue
                for row in table[1:]:
                    if not any(row):
                        continue
                    cleaned = [(cell or "").replace("\n", " ").strip() for cell in row]
                    record = dict(zip(headers, cleaned))
                    if "U ML ID" in record and "UML ID" not in record:
                        record["UML ID"] = record.get("U ML ID", "")
                    record["Plantation Latitude"] = parse_decimal(record.get("Plantation Latitude", ""))
                    record["Plantation Longitude"] = parse_decimal(record.get("Plantation Longitude", ""))
                    rows.append(record)
    return rows


def match_part_a_by_distance(danone_rows, uml_rows):
    matches = []
    for drow in danone_rows:
        best = None
        best_distance = None
        for urow in uml_rows:
            dist = None
            if drow.get("Latitude") is not None and drow.get("Longitude") is not None:
                if urow.get("Latitude") is not None and urow.get("Longitude") is not None:
                    dist = haversine_km(drow.get("Latitude"), drow.get("Longitude"), urow.get("Latitude"), urow.get("Longitude"))
            if dist is None:
                continue
            if best is None or dist < best_distance:
                best = urow
                best_distance = dist
        if best is not None:
            matches.append(best)
    return matches


def match_part_b_by_uml_id(danone_rows, uml_rows):
    uml_by_id = {}
    uml_by_mill = {}
    for urow in uml_rows:
        uml_id = re.sub(r"\s+", "", (urow.get("UML ID") or ""))
        if uml_id:
            uml_by_id[uml_id] = urow
        mill_key = urow.get("_norm_mill")
        if mill_key:
            uml_by_mill.setdefault(mill_key, []).append(urow)

    matches = []
    for drow in danone_rows:
        uml_id = re.sub(r"\s+", "", (drow.get("UML ID") or ""))
        urow = uml_by_id.get(uml_id)
        if urow is None:
            mill_key = normalize_text(drow.get("Mill Name", ""))
            parent_key = normalize_text(drow.get("Other Parent Company Name (Company Group)", ""))
            group_key = normalize_text(drow.get("Mill Company Name", ""))
            candidates = uml_by_mill.get(mill_key, [])
            if candidates:
                if parent_key:
                    filtered = [candidate for candidate in candidates if candidate.get("_norm_parent") == parent_key or candidate.get("_norm_group") == parent_key]
                    if len(filtered) == 1:
                        urow = filtered[0]
                if urow is None and group_key:
                    filtered = [candidate for candidate in candidates if candidate.get("_norm_parent") == group_key or candidate.get("_norm_group") == group_key]
                    if len(filtered) == 1:
                        urow = filtered[0]
                if urow is None and len(candidates) == 1:
                    urow = candidates[0]

        if urow is not None:
            merged = dict(urow)
            merged["Plantation Latitude"] = drow.get("Plantation Latitude")
            merged["Plantation Longitude"] = drow.get("Plantation Longitude")
            matches.append(merged)
    return matches


def discover_danone_reports(report_dir: Path, patterns):
    pdf_paths = []
    for pattern in patterns:
        pdf_paths.extend(report_dir.glob(pattern))
    return sorted({path.resolve(): path for path in pdf_paths}.values(), key=lambda path: path.name)


def main():
    parser = argparse.ArgumentParser(description="Match Danone mill and plantation reports to UML rows.")
    parser.add_argument("--uml-csv", default=str(DEFAULT_UML_CSV_PATH), help="Path to UML CSV")
    parser.add_argument("--report-dir", default=str(COMPANY_DIR / "report"), help="Directory containing Danone report PDFs")
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        help="Glob pattern for Danone reports. Can be passed multiple times.",
    )
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for matched CSV outputs")
    args = parser.parse_args()

    uml_csv_path = Path(args.uml_csv)
    report_dir = Path(args.report_dir)
    output_dir = Path(args.output_dir)
    patterns = tuple(args.patterns or DEFAULT_REPORT_PATTERNS)

    uml_rows, fieldnames = load_uml_rows(uml_csv_path)
    pdf_paths = discover_danone_reports(report_dir, patterns)
    if not pdf_paths:
        raise SystemExit(f"No Danone PDF reports found in {report_dir} for patterns: {', '.join(patterns)}")

    plantations_fieldnames = list(fieldnames)
    for extra in ("Plantation Latitude", "Plantation Longitude"):
        if extra not in plantations_fieldnames:
            plantations_fieldnames.append(extra)

    print(f"Reports processed: {len(pdf_paths)}")
    print(f"Output directory: {output_dir}")
    for pdf_path in pdf_paths:
        part_a_rows = extract_danone_part_a(pdf_path)
        part_b_rows = extract_danone_part_b(pdf_path)
        matched_mills = match_part_a_by_distance(part_a_rows, uml_rows)
        matched_plantations = match_part_b_by_uml_id(part_b_rows, uml_rows)

        stem = pdf_path.stem
        mills_output_path = output_dir / f"matched_mills_{stem}.csv"
        plantations_output_path = output_dir / f"matched_plantations_{stem}.csv"

        write_csv(mills_output_path, matched_mills, fieldnames)
        write_csv(plantations_output_path, matched_plantations, plantations_fieldnames)
        print(f"{pdf_path.name}: Part A rows={len(part_a_rows)}, matched mills={len(matched_mills)}")
        print(f"{pdf_path.name}: Part B rows={len(part_b_rows)}, matched plantations={len(matched_plantations)}")
        print(f"Output mills: {mills_output_path}")
        print(f"Output plantations: {plantations_output_path}")


if __name__ == "__main__":
    main()
