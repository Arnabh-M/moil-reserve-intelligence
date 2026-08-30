# MOIL Reserve Intelligence — SIH26009

Day 1 build: Neo4j graph foundation + synthetic datasets.

## Files

- `seed_graph.cypher` — Neo4j schema (constraints) + explicit seed data
  (3 mine sites, 15 equipment, ore zones, weather events, blast plans,
  risk events) + 3 verification queries.
- `generate_datasets.py` — generates `data/production_history.csv`,
  `data/equipment_downtime_log.csv`, `data/deposit_ground_truth.csv`.
- `requirements.txt` — Python environment.

## 1. Set up the Python environment

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

> Note: `pykrige`, `geopandas`, and `rasterio` have native/GDAL
> dependencies. If `pip install` fails on Windows for these, install
> via `conda`/`conda-forge` instead:
> `conda install -c conda-forge geopandas rasterio pykrige`

## 2. Run the dataset generator

```bash
python generate_datasets.py
```

This writes three CSVs into `./data/` and prints a summary (row
counts, date ranges, class balance) to the console for a quick sanity
check.

## 3. Load the graph into Neo4j

You need a running Neo4j instance (Neo4j Desktop, Docker, or Aura).

### Option A — `cypher-shell` (recommended, fully scriptable)

```bash
cypher-shell -a bolt://localhost:7687 -u neo4j -p <your-password> -f seed_graph.cypher
```

Or with Docker:

```bash
docker run --rm -it \
  -v "$(pwd)/seed_graph.cypher:/seed_graph.cypher" \
  --network host \
  neo4j:5 \
  cypher-shell -a bolt://localhost:7687 -u neo4j -p <your-password> -f /seed_graph.cypher
```

### Option B — Neo4j Browser (paste-in)

1. Open Neo4j Browser (usually `http://localhost:7474`).
2. Open `seed_graph.cypher` in a text editor, copy its contents.
3. Paste into the Neo4j Browser query bar and run. Neo4j Browser
   executes each `;`-terminated statement in sequence.
4. Run the three verification queries at the bottom of the file
   (also copy-pasteable individually) to confirm:
   - Node counts by label
   - The full Balaghat weather → blast delay → ore zone → risk chain
   - The idle-equipment redeploy candidate (Drill at Bhandara matching
     the down Drill at Nagpur)

### Reseeding

The script uses `CREATE`, not `MERGE` — re-running it against a
non-empty database will duplicate nodes. To reseed cleanly, uncomment
the `MATCH (n) DETACH DELETE n;` line near the top of
`seed_graph.cypher` first, or manually wipe the database.

## Connecting from Python (`neo4j` driver)

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "<your-password>"))
with driver.session() as session:
    result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count")
    for record in result:
        print(record["label"], record["count"])
driver.close()
```

## ID conventions (shared across the graph and CSVs)

- Site IDs: `balaghat`, `nagpur`, `bhandara` — used as `MineSite.id`
  and as `site_id` in every CSV.
- Equipment IDs: `eq_<site>_<01-05>` (e.g. `eq_bal_01`) — identical
  between `Equipment.id` in the graph and `equipment_id` in
  `equipment_downtime_log.csv`.
