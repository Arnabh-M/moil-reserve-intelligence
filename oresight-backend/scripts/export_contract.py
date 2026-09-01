"""Export the OpenAPI schema and a human-readable API contract doc.

Starts the app in-process (TestClient, so it runs the real lifespan and hits
the real seeded local Postgres) and actually calls every endpoint to capture
a REAL example response - not a hand-written fake. The two write endpoints
(POST /equipment/{id}/status, POST /production) are captured for real too,
then their side effects are cleaned up so the seeded dev DB is left exactly
as it was before the script ran.

Run from the project root:

    python -m scripts.export_contract
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import timedelta  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.agents.watcher import WatcherAgent  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.graph_db import close_graph_driver, init_graph_driver  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Equipment, EquipmentStatus, ProductionRecord, RiskEvent  # noqa: E402


def _seed_linked_risk_event() -> tuple[int, int, str]:
    """Create ONE risk event that has a real Neo4j causal graph, so the
    contract's causal-graph / recommendations examples show a live traversal
    rather than the Postgres-only fallback.

    Marks an 'up' unit down directly via the ORM (not POST /equipment/{id}/
    status, which would create its own graph-less Postgres risk row), then
    runs the Watcher once so the risk is mirrored into Neo4j with a
    `CAUSES` edge. Returns (risk_event_id, equipment_id, original_reason)
    for `_cleanup_linked_risk_event` to undo.
    """
    db = SessionLocal()
    driver = init_graph_driver()
    try:
        equipment = (
            db.query(Equipment)
            .filter(Equipment.status == EquipmentStatus.UP)
            .order_by(Equipment.id)
            .first()
        )
        original_reason = equipment.status_reason
        original_change = equipment.last_status_change
        equipment.status = EquipmentStatus.DOWN
        equipment.last_status_change = datetime.now(timezone.utc)
        equipment.status_reason = "Contract capture — transient, cleaned up"
        db.commit()

        created = WatcherAgent(db, driver).check_for_changes(
            since=datetime.now(timezone.utc) - timedelta(minutes=10)
        )
        risk_event_id = next(
            c["id"]
            for c in created
            if c["site_id"] == equipment.site_id
            and c["risk_type"] == "equipment_failure"
        )

        # Restore the equipment row immediately; the risk event + its Neo4j
        # node stay until _cleanup runs after all captures.
        equipment.status = EquipmentStatus.UP
        equipment.last_status_change = original_change
        equipment.status_reason = original_reason
        db.commit()
        return risk_event_id, equipment.id, original_reason
    finally:
        db.close()


def _cleanup_linked_risk_event(risk_event_id: int) -> None:
    db = SessionLocal()
    driver = init_graph_driver()
    try:
        db.query(RiskEvent).filter(RiskEvent.id == risk_event_id).delete()
        db.commit()
        with driver.session() as session:
            session.run(
                "MATCH (r:RiskEvent {external_ref: $ref}) DETACH DELETE r",
                ref=str(risk_event_id),
            )
    finally:
        db.close()

DOCS_DIR = PROJECT_ROOT / "docs"
OPENAPI_PATH = DOCS_DIR / "openapi.json"
CONTRACT_PATH = DOCS_DIR / "API_CONTRACT.md"

BASE_URL_NOTE = "http://localhost:8000"
CORS_NOTE = "http://localhost:5173, http://localhost:3000, http://127.0.0.1:5173"

STATUS_TABLE = [
    ("GET", "/sites", "Live"),
    ("GET", "/sites/geojson", "Live"),
    ("GET", "/sites/{site_id}", "Live"),
    ("GET", "/sites/{site_id}/geojson", "Live"),
    ("GET", "/equipment", "Live"),
    ("POST", "/equipment/{equipment_id}/status", "Live"),
    ("GET", "/production", "Live"),
    ("POST", "/production", "Live"),
    ("GET", "/risk-events", "Live"),
    ("GET", "/reserve-zones", "Live (real DB query, not a mock)"),
    ("GET", "/kpi/summary", "Live"),
    ("GET", "/risk-events/{risk_event_id}/causal-graph", "Live - Neo4j traversal (up to 3 hops from the RiskEvent node); falls back to a single-node graph with graph_source='postgres_fallback' when the risk event has no Neo4j node yet"),
    ("GET", "/recommendations", "Live - PlannerAgent (candidate search + simulation-backed scoring)"),
    ("POST", "/simulate", "Live - SimulatorAgent (trained shortfall forecaster + Neo4j causal-chain traversal)"),
    ("GET", "/admin/jobs", "Live (scheduler introspection)"),
    ("GET", "/health", "Live"),
]


def _resolve_schema_type(schema: dict) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return _resolve_schema_type(schema["allOf"][0])
    if "enum" in schema:
        return " | ".join(repr(v) for v in schema["enum"])
    if "type" in schema:
        if schema["type"] == "array":
            return f"list[{_resolve_schema_type(schema.get('items', {}))}]"
        return schema["type"]
    if "anyOf" in schema:
        parts = [_resolve_schema_type(s) for s in schema["anyOf"] if s.get("type") != "null"]
        nullable = any(s.get("type") == "null" for s in schema["anyOf"])
        type_str = " | ".join(parts) if parts else "any"
        return f"{type_str} | null" if nullable else type_str
    return "any"


def _describe_params(operation: dict) -> list[dict]:
    params = []
    for p in operation.get("parameters", []):
        schema = p.get("schema", {})
        default = schema.get("default")
        params.append(
            {
                "name": p["name"],
                "in": p["in"],
                "required": p.get("required", False),
                "type": _resolve_schema_type(schema),
                "default": default,
                "description": p.get("description", ""),
            }
        )
    return params


def _describe_request_body(operation: dict, components: dict) -> list[dict] | None:
    body = operation.get("requestBody")
    if not body:
        return None
    schema = body["content"]["application/json"]["schema"]
    ref = schema.get("$ref")
    if ref:
        schema = components["schemas"][ref.rsplit("/", 1)[-1]]
    required_fields = set(schema.get("required", []))
    fields = []
    for name, prop in schema.get("properties", {}).items():
        fields.append(
            {
                "name": name,
                "type": _resolve_schema_type(prop),
                "required": name in required_fields,
            }
        )
    return fields


def _format_params_md(params: list[dict]) -> str:
    if not params:
        return "_None_"
    lines = []
    for p in params:
        req = "required" if p["required"] else "optional"
        default = f", default `{p['default']}`" if p["default"] is not None else ""
        desc = f" — {p['description']}" if p["description"] else ""
        lines.append(f"- `{p['name']}` ({p['in']}, `{p['type']}`, {req}{default}){desc}")
    return "\n".join(lines)


def _format_body_md(fields: list[dict] | None) -> str:
    if fields is None:
        return "_None_"
    lines = []
    for f in fields:
        req = "required" if f["required"] else "optional"
        lines.append(f"- `{f['name']}` (`{f['type']}`, {req})")
    return "\n".join(lines)


def main() -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    openapi_schema = app.openapi()
    OPENAPI_PATH.write_text(json.dumps(openapi_schema, indent=2), encoding="utf-8")
    print(f"Wrote {OPENAPI_PATH.relative_to(PROJECT_ROOT)}")

    components = openapi_schema.get("components", {})
    captured: list[dict[str, Any]] = []

    # Seed one Watcher-linked risk event so the causal-graph / recommendations
    # examples below capture a live Neo4j traversal. Removed in cleanup.
    linked_risk_event_id, _, _ = _seed_linked_risk_event()

    with TestClient(app) as client:
        # --- Sites ---
        r = client.get("/sites")
        sites = r.json()
        site_id = sites[0]["id"]
        captured.append({"group": "Sites", "method": "GET", "path": "/sites", "concrete": "/sites", "status": r.status_code, "body": sites})

        r = client.get(f"/sites/{site_id}")
        captured.append({"group": "Sites", "method": "GET", "path": "/sites/{site_id}", "concrete": f"/sites/{site_id}", "status": r.status_code, "body": r.json()})

        r = client.get(f"/sites/{site_id}/geojson")
        captured.append({"group": "Sites", "method": "GET", "path": "/sites/{site_id}/geojson", "concrete": f"/sites/{site_id}/geojson", "status": r.status_code, "body": r.json()})

        r = client.get("/sites/geojson")
        captured.append({"group": "Sites", "method": "GET", "path": "/sites/geojson", "concrete": "/sites/geojson", "status": r.status_code, "body": r.json()})

        # --- Equipment ---
        r = client.get("/equipment")
        equipment_list = r.json()
        captured.append({"group": "Equipment", "method": "GET", "path": "/equipment", "concrete": "/equipment", "status": r.status_code, "body": equipment_list})

        up_equipment = next(e for e in equipment_list if e["status"] == "up")
        eq_id = up_equipment["id"]
        original_reason = up_equipment["status_reason"]

        r = client.post(
            f"/equipment/{eq_id}/status",
            json={"status": "down", "reason": "Scheduled maintenance check (contract capture)"},
        )
        captured.append({
            "group": "Equipment",
            "method": "POST",
            "path": "/equipment/{equipment_id}/status",
            "concrete": f"/equipment/{eq_id}/status",
            "status": r.status_code,
            "body": r.json(),
            "note": "Marking equipment 'down' also inserts a new equipment_failure risk_events row (visible below in Risk & Graph) - this example shows that real side effect, then the script restores the equipment and deletes the risk event it created so the seeded demo data is untouched.",
        })

        risk_events_for_site = client.get(f"/risk-events?site_id={up_equipment['site_id']}&resolved=false").json()
        created_risk_event_id = max(e["id"] for e in risk_events_for_site)

        client.post(f"/equipment/{eq_id}/status", json={"status": "up", "reason": original_reason})

        # --- Production ---
        r = client.get(f"/production?site_id={site_id}&days=10")
        captured.append({"group": "Production", "method": "GET", "path": "/production", "concrete": f"/production?site_id={site_id}&days=10", "status": r.status_code, "body": r.json()})

        probe_date = "2027-01-01"
        production_payload = {"site_id": site_id, "date": probe_date, "actual_output": 1180.0, "target_output": 1250.0}
        r = client.post("/production", json=production_payload)
        created_production = r.json()
        captured.append({"group": "Production", "method": "POST", "path": "/production", "concrete": "/production", "status": r.status_code, "body": created_production})

        r = client.post("/production", json=production_payload)
        captured.append({
            "group": "Production",
            "method": "POST",
            "path": "/production",
            "concrete": "/production (duplicate site_id+date)",
            "status": r.status_code,
            "body": r.json(),
            "note": "Same (site_id, date) posted twice - the second call is rejected with 409.",
        })

        # --- Risk & Graph ---
        r = client.get("/risk-events")
        risk_events_all = r.json()
        captured.append({"group": "Risk & Graph", "method": "GET", "path": "/risk-events", "concrete": "/risk-events", "status": r.status_code, "body": risk_events_all})

        # `linked_risk_event_id` (seeded above via the Watcher) has a real
        # Neo4j causal graph; use it for the causal-graph + recommendations
        # examples so they show a live traversal, not the fallback.
        risk_event_id = linked_risk_event_id

        r = client.get(f"/reserve-zones?site_id={site_id}")
        captured.append({"group": "Risk & Graph", "method": "GET", "path": "/reserve-zones", "concrete": f"/reserve-zones?site_id={site_id}", "status": r.status_code, "body": r.json()})

        r = client.get(f"/risk-events/{risk_event_id}/causal-graph")
        captured.append({"group": "Risk & Graph", "method": "GET", "path": "/risk-events/{risk_event_id}/causal-graph", "concrete": f"/risk-events/{risk_event_id}/causal-graph", "status": r.status_code, "body": r.json(),
            "note": "graph_source='neo4j' is a live traversal. When a risk event has no Neo4j node yet (predates the Watcher sync, or Neo4j is down), the same endpoint returns HTTP 200 with a single-node graph and graph_source='postgres_fallback' plus an explanatory note - render a banner, not an empty canvas."})

        # --- Recommendations & Simulation ---
        r = client.get(f"/recommendations?risk_event_id={risk_event_id}")
        captured.append({"group": "Recommendations & Simulation", "method": "GET", "path": "/recommendations", "concrete": f"/recommendations?risk_event_id={risk_event_id}", "status": r.status_code, "body": r.json()})

        r = client.post("/simulate", json={"scenario_type": "equipment_down", "site_id": site_id, "duration_days": 5})
        captured.append({"group": "Recommendations & Simulation", "method": "POST", "path": "/simulate", "concrete": "/simulate", "status": r.status_code, "body": r.json()})

        # --- KPI ---
        r = client.get("/kpi/summary")
        captured.append({"group": "KPI", "method": "GET", "path": "/kpi/summary", "concrete": "/kpi/summary", "status": r.status_code, "body": r.json()})

        # --- Meta & Ops ---
        r = client.get("/health")
        captured.append({"group": "Meta & Ops", "method": "GET", "path": "/health", "concrete": "/health", "status": r.status_code, "body": r.json()})

        r = client.get("/admin/jobs")
        captured.append({"group": "Meta & Ops", "method": "GET", "path": "/admin/jobs", "concrete": "/admin/jobs", "status": r.status_code, "body": r.json()})

    # Clean up the write side effects so the seeded dev DB is untouched.
    cleanup_db = SessionLocal()
    try:
        cleanup_db.query(RiskEvent).filter(RiskEvent.id == created_risk_event_id).delete()
        cleanup_db.query(ProductionRecord).filter(ProductionRecord.id == created_production["id"]).delete()
        cleanup_db.commit()
        print(f"Cleaned up captured test rows (risk_event {created_risk_event_id}, production {created_production['id']})")
    finally:
        cleanup_db.close()

    _cleanup_linked_risk_event(linked_risk_event_id)
    print(f"Cleaned up Watcher-linked risk_event {linked_risk_event_id} (Postgres + Neo4j)")
    close_graph_driver()

    # --- Render markdown ---
    groups_order = ["Sites", "Equipment", "Production", "Risk & Graph", "Recommendations & Simulation", "KPI", "Meta & Ops"]
    lines: list[str] = []

    lines.append("# OreSight API Contract")
    lines.append("")
    lines.append(f"Generated by `scripts/export_contract.py` on {datetime.now(timezone.utc).isoformat()} "
                  "against the real seeded dev database. Every example response below is a genuine "
                  "captured API call, not hand-written.")
    lines.append("")
    lines.append(f"- **Base URL:** `{BASE_URL_NOTE}`")
    lines.append(f"- **CORS:** open for `{CORS_NOTE}`")
    lines.append("- **Interactive docs:** `/docs` (Swagger UI), `/redoc`")
    lines.append(f"- **Raw OpenAPI schema:** [`openapi.json`]({OPENAPI_PATH.name}) (exported alongside this file)")
    lines.append("")
    lines.append("## What's real vs stubbed today")
    lines.append("")
    lines.append("| Method | Path | Status |")
    lines.append("|---|---|---|")
    for method, path, status in STATUS_TABLE:
        lines.append(f"| {method} | `{path}` | {status} |")
    lines.append("")

    for group in groups_order:
        group_items = [c for c in captured if c["group"] == group]
        if not group_items:
            continue
        lines.append(f"## {group}")
        lines.append("")
        for item in group_items:
            operation = openapi_schema["paths"][item["path"]][item["method"].lower()]
            summary = operation.get("summary", "")
            params = _describe_params(operation)
            body_fields = _describe_request_body(operation, components)

            lines.append(f"### {item['method']} `{item['path']}`")
            lines.append("")
            lines.append(summary)
            lines.append("")
            lines.append("**Query/path params:**")
            lines.append("")
            lines.append(_format_params_md(params))
            lines.append("")
            lines.append("**Request body:**")
            lines.append("")
            lines.append(_format_body_md(body_fields))
            lines.append("")
            if item.get("note"):
                lines.append(f"> {item['note']}")
                lines.append("")
            lines.append(f"**Real example** - `{item['method']} {item['concrete']}` -> `{item['status']}`")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(item["body"], indent=2))
            lines.append("```")
            lines.append("")

    CONTRACT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {CONTRACT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
