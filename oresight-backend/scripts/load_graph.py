"""Load ../seed_graph.cypher into Neo4j.

Infra helper: splits the repo-root seed_graph.cypher into individual
statements and runs them over the Bolt driver, using the same
NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD from app/config.py that the app uses.
The `neo4j` Python driver executes one statement per `session.run`, so
this does the split itself (full-line `//` comments dropped, statements
delimited by `;`).

By default it refuses to run against a non-empty graph. Pass --reset to
`MATCH (n) DETACH DELETE n` first (the commented-out cleanup line at the
top of seed_graph.cypher), e.g. after a schema change:

    python -m scripts.load_graph --reset

Run from oresight-backend/ (after the stack is up):

    python -m scripts.load_graph
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from neo4j import GraphDatabase  # noqa: E402

from app.config import get_settings  # noqa: E402

CYPHER_PATH = REPO_ROOT / "seed_graph.cypher"


def _split_statements(cypher_text: str) -> list[str]:
    """Return executable statements: drop full-line `//` comments, then
    split what's left on `;`.
    """
    lines = [
        line
        for line in cypher_text.splitlines()
        if not line.strip().startswith("//")
    ]
    body = "\n".join(lines)
    return [stmt.strip() for stmt in body.split(";") if stmt.strip()]


def load_graph(reset: bool = False) -> dict:
    settings = get_settings()
    statements = _split_statements(CYPHER_PATH.read_text(encoding="utf-8"))

    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            existing = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            if existing and not reset:
                raise SystemExit(
                    f"Refusing to load: graph already has {existing} nodes. "
                    "Re-run with --reset to wipe and reseed."
                )
            if reset and existing:
                session.run("MATCH (n) DETACH DELETE n")
                print(f"--reset: deleted {existing} existing nodes")

            executed = 0
            for stmt in statements:
                session.run(stmt)
                executed += 1

            counts = {
                row["label"]: row["count"]
                for row in session.run(
                    "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count "
                    "ORDER BY label"
                )
            }
            rels = session.run(
                "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY t"
            ).data()
    finally:
        driver.close()

    return {"statements_executed": executed, "node_counts": counts, "rel_counts": rels}


if __name__ == "__main__":
    result = load_graph(reset="--reset" in sys.argv[1:])
    print(f"\nExecuted {result['statements_executed']} statements.")
    print("Nodes by label:")
    for label, count in result["node_counts"].items():
        print(f"  {label:<20} {count:>3}")
    print("Relationships by type:")
    for row in result["rel_counts"]:
        print(f"  {row['t']:<20} {row['c']:>3}")
