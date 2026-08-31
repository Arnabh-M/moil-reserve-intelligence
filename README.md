# MOIL Reserve Intelligence — SIH26009

Day 1 build: Neo4j graph foundation + synthetic datasets.
Day 2 build: Reserve Prospectivity model (structural features, classifier,
kriged confidence surface, GeoJSON export) + Shortfall Forecaster feature prep.

## Files

- `seed_graph.cypher` — Neo4j schema (constraints) + explicit seed data
  (3 mine sites, 15 equipment, ore zones, weather events, blast plans,
  risk events) + 3 verification queries.
- `generate_datasets.py` — generates `data/production_history.csv`,
  `data/equipment_downtime_log.csv`, `data/deposit_ground_truth.csv`.
- `geo_utils.py` — shared geospatial helpers (site bboxes, UTM
  projection, point-to-structure distance, spatially-correlated
  random fields). Imported by every Day 2 script below.
- `generate_features.py` — Day 2 Part 1: generates
  `data/structural_lines.csv` and `data/training_features.csv`;
  persists `models/ndvi_field.pkl` / `models/elevation_field.pkl`.
- `train_reserve_classifier.py` — Day 2 Part 2: trains
  RandomForest + XGBoost on `training_features.csv`, saves the
  better model to `models/reserve_classifier.pkl`.
- `build_confidence_surface.py` — Day 2 Part 3: predicts probability
  over a 50x50 grid, krige-smooths it (PyKrige), resamples to a
  100x100 grid → `data/confidence_surface.npz`.
- `export_reserve_zones.py` — Day 2 Part 4: converts the kriged
  surface into `data/reserve_zones.geojson` (cell polygons with
  `confidence_score` + `site_id`).
- `shortfall_features_wip.py` — Day 2 Part 5: engineers features for
  tomorrow's shortfall forecaster → `data/shortfall_features_wip.csv`
  (no model trained yet).
- `requirements.txt` — Python environment.

### Day 2 run order

Parts 1-4 have a hard dependency chain — run them in this order:

```bash
python generate_features.py          # Part 1
python train_reserve_classifier.py   # Part 2
python build_confidence_surface.py   # Part 3
python export_reserve_zones.py       # Part 4
python shortfall_features_wip.py     # Part 5 (independent, needs Day 1 CSVs only)
```

> `export_reserve_zones.py` assumes `site_id` in `reserve_zones.geojson`
> should be the same lowercase string (`balaghat`/`nagpur`/`bhandara`)
> used everywhere else in this project. That hasn't been checked
> against P1's actual `/reserve-zones` endpoint code — confirm the
> expected id format with whoever owns P1 before wiring it up.

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
