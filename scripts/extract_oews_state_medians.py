"""Extract all-occupation wages by state from the BLS OEWS state workbook.

Writes studies/state_roi/data/raw/oews_may2025_state_all_occupations.csv,
which the 50-state ROI pipeline reads. This is the only step that needs a
non-standard-library package (openpyxl), so it runs once when OEWS updates,
not on every model run.

Usage:
    python scripts/extract_oews_state_medians.py path/to/oesm25st.zip
"""

from __future__ import annotations

import csv
import hashlib
import io
import sys
import zipfile
from pathlib import Path

from openpyxl import load_workbook

OUT = Path(__file__).resolve().parents[1] / "studies" / "state_roi" / "data" / "raw"
OUT_FILE = OUT / "oews_may2025_state_all_occupations.csv"
COLUMNS = ("AREA", "PRIM_STATE", "AREA_TITLE", "TOT_EMP", "A_MEDIAN", "A_MEAN")


def main(zip_path: str) -> None:
    raw = Path(zip_path).read_bytes()
    print(f"sha256 {hashlib.sha256(raw).hexdigest()}")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".xlsx"))
        sheet = load_workbook(io.BytesIO(archive.read(name)), read_only=True).active
        rows = sheet.iter_rows(values_only=True)
        header = [str(h) for h in next(rows)]
        index = {c: header.index(c) for c in (*COLUMNS, "OCC_CODE")}
        kept = [r for r in rows if r[index["OCC_CODE"]] == "00-0000"]
    with OUT_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([c.lower() for c in COLUMNS])
        for r in kept:
            writer.writerow([r[index[c]] for c in COLUMNS])
    print(f"wrote {len(kept)} areas to {OUT_FILE}")


if __name__ == "__main__":
    main(sys.argv[1])
