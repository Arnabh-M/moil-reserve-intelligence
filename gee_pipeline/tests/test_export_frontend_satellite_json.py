"""The frontend satellite JSON must end at the last date that has rainfall."""

from __future__ import annotations

import csv
import json

from gee_pipeline.export_frontend_satellite_json import export_frontend_satellite_json, last_rainfall_date


def _write_csv(path, rows):
    fields = ["site_id", "date", "rainfall_mm", "soil_moisture_m3m3", "lst_day_c", "ndvi", "ndvi_age_days"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def test_last_rainfall_date_ignores_null_rows():
    data = {"a": [{"date": "2026-01-01", "rainfall_mm": 1.0}, {"date": "2026-01-02", "rainfall_mm": None}]}
    assert last_rainfall_date(data) == "2026-01-01"
    assert last_rainfall_date({"a": [{"date": "2026-01-02", "rainfall_mm": None}]}) is None


def test_export_drops_trailing_all_null_day(tmp_path):
    rows = [
        {"site_id": s, "date": d, "rainfall_mm": 2.5 if d != "2026-01-03" else ""}
        for s in ("balaghat", "nagpur")
        for d in ("2026-01-01", "2026-01-02", "2026-01-03")
    ]
    csv_path, out = tmp_path / "f.csv", tmp_path / "out.json"
    _write_csv(csv_path, rows)
    export_frontend_satellite_json(csv_path=str(csv_path), meta_path=str(tmp_path / "none.json"), out_json_path=str(out))
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["latest_date"] == "2026-01-02"
    for recs in payload["sites"].values():
        assert recs[-1]["date"] == "2026-01-02"
