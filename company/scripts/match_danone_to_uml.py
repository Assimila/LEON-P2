#!/usr/bin/env python3
import csv
import math
import re
from pathlib import Path

import pdfplumber


UML_CSV_PATH = Path("UML/UML-Dec-2024.csv")
DANONE_REPORT_DIR = Path("report")
OUTPUT_DIR = Path("UML")


def normalize_text(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def parse_decimal(value: str):
    if value is None:
        return None
    cleaned = value.strip().replace(" ", "")
    if not cleaned:
        return None
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_uml_rows():
    rows = []
    with UML_CSV_PATH.open(newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["Latitude"] = parse_decimal(row.get("Latitude", ""))
            row["Longitude"] = parse_decimal(row.get("Longitude", ""))
            row["_norm_parent"] = normalize_text(row.get("Parent Company", ""))
            row["_norm_group"] = normalize_text(row.get("Group Name", ""))
            row["_norm_mill"] = normalize_text(row.get("Mill Name", ""))
            rows.append(row)
    return rows, reader.fieldnames


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
    if key in ("starlingmillid", "umlid", "umlid", "umllid", "umleid"):
        return "UML ID"
    if for_part_b and key.startswith("partb"):
        return "UML ID"
    return cleaned


def _is_part_a_header(headers):
    header_set = {h.lower() for h in headers if h}
    has_latlon = "latitude" in header_set and "longitude" in header_set
    has_mill_name = any("mill name" in h.lower() for h in headers if h)
    has_plantation = any("plantation" in h.lower() for h in headers if h)
    return has_latlon and has_mill_name and not has_plantation


def _is_part_b_header(headers):
    normalized = [re.sub(r"[^a-z0-9]+", "", h.lower()) for h in headers if h]
    return any("plantation" in h for h in normalized)


def extract_danone_part_a(pdf_path: Path):
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        last_page = min(len(pdf.pages), 8)
        for page_index in range(1, last_page):  # pages 2-8: Mill List
            page = pdf.pages[page_index]
            for table in page.extract_tables():
                if not table or not table[0]:
                    continue
                headers = [_canonical_header(h, for_part_b=False) for h in table[0]]
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
        for page_index in range(8, last_page):  # pages 9-28: Plantation List
            page = pdf.pages[page_index]
            for table in page.extract_tables():
                if not table or not table[0]:
                    continue
                headers = [_canonical_header(h, for_part_b=True) for h in table[0]]
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
                    filtered = [c for c in candidates if c.get("_norm_parent") == parent_key or c.get("_norm_group") == parent_key]
                    if len(filtered) == 1:
                        urow = filtered[0]
                if urow is None and group_key:
                    filtered = [c for c in candidates if c.get("_norm_parent") == group_key or c.get("_norm_group") == group_key]
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


def write_output(path, matches, fieldnames):
    with path.open("w", newline="", encoding="latin-1") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in matches:
            clean = {k: row.get(k, "") for k in fieldnames}
            writer.writerow(clean)


def main():
    uml_rows, fieldnames = load_uml_rows()
    pdf_paths = sorted(DANONE_REPORT_DIR.glob("*.pdf"))
    if not pdf_paths:
        raise SystemExit(f"No PDF reports found in {DANONE_REPORT_DIR}")

    plantations_fieldnames = list(fieldnames)
    for extra in ("Plantation Latitude", "Plantation Longitude"):
        if extra not in plantations_fieldnames:
            plantations_fieldnames.append(extra)

    print(f"Reports processed: {len(pdf_paths)}")
    for pdf_path in pdf_paths:
        part_a_rows = extract_danone_part_a(pdf_path)
        part_b_rows = extract_danone_part_b(pdf_path)
        matched_mills = match_part_a_by_distance(part_a_rows, uml_rows)
        matched_plantations = match_part_b_by_uml_id(part_b_rows, uml_rows)

        stem = pdf_path.stem
        mills_output_path = OUTPUT_DIR / f"matched_mills_{stem}.csv"
        plantations_output_path = OUTPUT_DIR / f"matched_plantations_{stem}.csv"

        write_output(mills_output_path, matched_mills, fieldnames)
        write_output(plantations_output_path, matched_plantations, plantations_fieldnames)
        print(f"{pdf_path.name}: Part A rows={len(part_a_rows)}, matched mills={len(matched_mills)}")
        print(f"{pdf_path.name}: Part B rows={len(part_b_rows)}, matched plantations={len(matched_plantations)}")
        print(f"Output mills: {mills_output_path}")
        print(f"Output plantations: {plantations_output_path}")


if __name__ == "__main__":
    main()
