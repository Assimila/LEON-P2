#!/usr/bin/env python3
import csv
import math
import re
import unicodedata
from pathlib import Path


LEGAL_NAME_TOKENS = {
    "ab",
    "berhad",
    "bhd",
    "co",
    "company",
    "corp",
    "corporation",
    "gmbh",
    "group",
    "holding",
    "holdings",
    "inc",
    "incorporated",
    "kg",
    "limited",
    "llc",
    "ltd",
    "nv",
    "plc",
    "private",
    "pt",
    "publ",
    "pte",
    "sa",
    "sdn",
    "tbk",
}
KEEP_SINGLE_LETTER_TOKENS = {"i", "v", "x"}


def ascii_fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return text.encode("ascii", "ignore").decode("ascii")


def normalize_text(value: str) -> str:
    value = ascii_fold(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalize_company_name(value: str) -> str:
    value = ascii_fold(value).lower().replace("&", " and ")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    tokens = [
        token
        for token in value.split()
        if token not in LEGAL_NAME_TOKENS and (len(token) > 1 or token in KEEP_SINGLE_LETTER_TOKENS)
    ]
    return " ".join(tokens)


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
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_uml_rows(csv_path: Path):
    rows = []
    with csv_path.open(newline="", encoding="latin-1") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row["Latitude"] = parse_decimal(row.get("Latitude", ""))
            row["Longitude"] = parse_decimal(row.get("Longitude", ""))
            row["_norm_parent"] = normalize_text(row.get("Parent Company", ""))
            row["_norm_group"] = normalize_text(row.get("Group Name", ""))
            row["_norm_mill"] = normalize_text(row.get("Mill Name", ""))
            row["_norm_parent_company"] = normalize_company_name(row.get("Parent Company", ""))
            row["_norm_group_company"] = normalize_company_name(row.get("Group Name", ""))
            rows.append(row)
    return rows, reader.fieldnames


def write_csv(path: Path, rows, fieldnames, *, encoding: str = "latin-1"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding=encoding) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
