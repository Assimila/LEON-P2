from __future__ import annotations

from pathlib import Path

import pandas as pd


ENCODINGS = ("utf-8", "utf-8-sig", "latin1", "cp1252")


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = (
        out.columns
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
    )
    return out


def _read_csv_with_fallback(path: Path) -> pd.DataFrame:
    last_err: Exception | None = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as exc:  # pragma: no cover
            last_err = exc
    raise RuntimeError(f"Failed to read mill CSV '{path}': {last_err}")


def _parse_coord(value: object, *, is_latitude: bool) -> float:
    if pd.isna(value):
        return float("nan")

    s = str(value).strip().replace("\xa0", "").replace(" ", "")
    if not s:
        return float("nan")

    if "," in s and "." not in s and s.count(",") == 1:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(",", "")

    try:
        num = float(s)
    except ValueError:
        return float("nan")

    limit = 90.0 if is_latitude else 180.0
    if abs(num) > limit and abs(num) <= (90_000_000 if is_latitude else 180_000_000):
        # Fix values where decimal separator was dropped (e.g., 109332467 -> 109.332467).
        num = num / 1_000_000.0

    return num


def load_mills(path: Path, *, limit: int | None = None) -> pd.DataFrame:
    df_raw = _read_csv_with_fallback(path)
    df = _normalise_columns(df_raw)

    required = {
        "mill_id": "uml_id",
        "mill_name": "mill_name",
        "latitude": "latitude",
        "longitude": "longitude",
        "iso": "iso",
        "country": "country",
    }
    missing = [src for src in required.values() if src not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in mills CSV: {missing}")

    out = pd.DataFrame({
        "mill_id": df[required["mill_id"]].astype(str).str.strip(),
        "mill_name": df[required["mill_name"]].astype(str).str.strip(),
        "latitude": df[required["latitude"]].map(lambda v: _parse_coord(v, is_latitude=True)),
        "longitude": df[required["longitude"]].map(lambda v: _parse_coord(v, is_latitude=False)),
        "iso": df[required["iso"]].astype(str).str.strip(),
        "country": df[required["country"]].astype(str).str.strip(),
    })

    out = out.dropna(subset=["latitude", "longitude"]).copy()
    out = out[out["latitude"].between(-90, 90)]
    out = out[out["longitude"].between(-180, 180)]

    if limit is not None and limit > 0:
        out = out.head(limit)

    return out.reset_index(drop=True)
