from __future__ import annotations

from pathlib import Path

import pandas as pd

from shed_deforestation.mills import load_mills


def test_load_mills_parses_malformed_coordinates(tmp_path: Path):
    csv_path = tmp_path / "mills.csv"
    df = pd.DataFrame(
        {
            "UML ID": ["A", "B", "C"],
            "Mill Name": ["m1", "m2", "m3"],
            "Latitude": ["8,7548", "\xa0-2.367572", "0.575884"],
            "Longitude": ["-83.2082", "\xa0102.791319", "109332467"],
            "ISO": ["CRI", "IDN", "IDN"],
            "Country": ["Costa Rica", "Indonesia", "Indonesia"],
        }
    )
    df.to_csv(csv_path, index=False)

    out = load_mills(csv_path)
    assert len(out) == 3

    row_c = out.loc[out["mill_id"] == "C"].iloc[0]
    assert abs(float(row_c["longitude"]) - 109.332467) < 1e-9
