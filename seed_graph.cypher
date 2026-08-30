// =====================================================================
// MOIL Reserve Intelligence (SIH26009) — Neo4j Schema + Seed Script
// =====================================================================
// Run against a fresh/empty database. This script is idempotent-safe
// only if the DB is empty first — see the cleanup line below.
//
// Node labels: MineSite, OreZone, Equipment, StructuralFeature,
//              WeatherEvent, BlastPlan, RiskEvent
//
// Relationships:
//   (Equipment)-[:DEPENDS_ON]->(BlastPlan)
//   (WeatherEvent)-[:DELAYS]->(BlastPlan)
//   (BlastPlan)-[:AFFECTS]->(OreZone)
//   (Equipment)-[:CAUSES]->(RiskEvent)
//   (WeatherEvent)-[:CORRELATES_WITH]->(RiskEvent)
//
// Note on LOCATED_IN: belt_name/state are modeled as properties on
// MineSite directly (no separate Belt/Region node) — simplest for a
// 5-day prototype and still fully queryable.
// =====================================================================

// ---------------------------------------------------------------------
// OPTIONAL CLEANUP — uncomment to wipe the DB before reseeding
// ---------------------------------------------------------------------
// MATCH (n) DETACH DELETE n;

// ---------------------------------------------------------------------
// CONSTRAINTS — one uniqueness constraint per label on `id`
// ---------------------------------------------------------------------
CREATE CONSTRAINT minesite_id IF NOT EXISTS FOR (n:MineSite) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT orezone_id IF NOT EXISTS FOR (n:OreZone) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT equipment_id IF NOT EXISTS FOR (n:Equipment) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT structuralfeature_id IF NOT EXISTS FOR (n:StructuralFeature) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT weatherevent_id IF NOT EXISTS FOR (n:WeatherEvent) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT blastplan_id IF NOT EXISTS FOR (n:BlastPlan) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT riskevent_id IF NOT EXISTS FOR (n:RiskEvent) REQUIRE n.id IS UNIQUE;

// =====================================================================
// MineSite (3)
// =====================================================================
CREATE (:MineSite {id: 'balaghat', name: 'Balaghat Mine', belt_name: 'Balaghat-Manganese Belt', state: 'Madhya Pradesh'});
CREATE (:MineSite {id: 'nagpur',   name: 'Nagpur Mine',   belt_name: 'Nagpur-Bhandara Manganese Belt', state: 'Maharashtra'});
CREATE (:MineSite {id: 'bhandara', name: 'Bhandara Mine', belt_name: 'Nagpur-Bhandara Manganese Belt', state: 'Maharashtra'});

// =====================================================================
// OreZone (2 per site = 6)
// =====================================================================
CREATE (:OreZone {id: 'oz_bal_01', site_id: 'balaghat', confidence_score: 0.82, grade_estimate: 38.5});
CREATE (:OreZone {id: 'oz_bal_02', site_id: 'balaghat', confidence_score: 0.61, grade_estimate: 24.0});
CREATE (:OreZone {id: 'oz_nag_01', site_id: 'nagpur',   confidence_score: 0.74, grade_estimate: 31.2});
CREATE (:OreZone {id: 'oz_nag_02', site_id: 'nagpur',   confidence_score: 0.55, grade_estimate: 19.8});
CREATE (:OreZone {id: 'oz_bhd_01', site_id: 'bhandara', confidence_score: 0.69, grade_estimate: 27.6});
CREATE (:OreZone {id: 'oz_bhd_02', site_id: 'bhandara', confidence_score: 0.48, grade_estimate: 16.4});

// =====================================================================
// Equipment (5 per site = 15). Exactly 2 "down" total:
//   - eq_nag_02 (Drill, Nagpur)      -> feeds the equipment RiskEvent chain
//   - eq_bal_05 (Compressor, Balaghat)
// eq_bhd_02 (Drill, Bhandara) is deliberately idle/up and NOT wired to
// any BlastPlan via DEPENDS_ON — it is the redeploy candidate matching
// eq_nag_02's type (Drill).
// =====================================================================
CREATE (:Equipment {id: 'eq_bal_01', site_id: 'balaghat', name: 'Excavator BAL-1', type: 'Excavator', status: 'up',   last_status_change: datetime('2026-08-01T06:00:00')});
CREATE (:Equipment {id: 'eq_bal_02', site_id: 'balaghat', name: 'Drill BAL-1',     type: 'Drill',      status: 'up',   last_status_change: datetime('2026-08-03T09:30:00')});
CREATE (:Equipment {id: 'eq_bal_03', site_id: 'balaghat', name: 'Conveyor BAL-1',  type: 'Conveyor',   status: 'up',   last_status_change: datetime('2026-07-20T11:00:00')});
CREATE (:Equipment {id: 'eq_bal_04', site_id: 'balaghat', name: 'Loader BAL-1',    type: 'Loader',     status: 'up',   last_status_change: datetime('2026-08-10T08:15:00')});
CREATE (:Equipment {id: 'eq_bal_05', site_id: 'balaghat', name: 'Compressor BAL-1',type: 'Compressor', status: 'down', last_status_change: datetime('2026-08-27T14:20:00')});

CREATE (:Equipment {id: 'eq_nag_01', site_id: 'nagpur', name: 'Excavator NAG-1',  type: 'Excavator', status: 'up',   last_status_change: datetime('2026-08-05T07:45:00')});
CREATE (:Equipment {id: 'eq_nag_02', site_id: 'nagpur', name: 'Drill NAG-1',      type: 'Drill',      status: 'down', last_status_change: datetime('2026-08-28T10:05:00')});
CREATE (:Equipment {id: 'eq_nag_03', site_id: 'nagpur', name: 'Conveyor NAG-1',   type: 'Conveyor',   status: 'up',   last_status_change: datetime('2026-07-15T13:00:00')});
CREATE (:Equipment {id: 'eq_nag_04', site_id: 'nagpur', name: 'Loader NAG-1',     type: 'Loader',     status: 'up',   last_status_change: datetime('2026-08-12T09:00:00')});
CREATE (:Equipment {id: 'eq_nag_05', site_id: 'nagpur', name: 'Compressor NAG-1', type: 'Compressor', status: 'up',   last_status_change: datetime('2026-07-28T16:30:00')});

CREATE (:Equipment {id: 'eq_bhd_01', site_id: 'bhandara', name: 'Excavator BHD-1',  type: 'Excavator', status: 'up', last_status_change: datetime('2026-08-02T08:00:00')});
CREATE (:Equipment {id: 'eq_bhd_02', site_id: 'bhandara', name: 'Drill BHD-1',      type: 'Drill',      status: 'up', last_status_change: datetime('2026-08-06T09:00:00')});
CREATE (:Equipment {id: 'eq_bhd_03', site_id: 'bhandara', name: 'Conveyor BHD-1',   type: 'Conveyor',   status: 'up', last_status_change: datetime('2026-07-22T12:00:00')});
CREATE (:Equipment {id: 'eq_bhd_04', site_id: 'bhandara', name: 'Loader BHD-1',     type: 'Loader',     status: 'up', last_status_change: datetime('2026-08-09T10:30:00')});
CREATE (:Equipment {id: 'eq_bhd_05', site_id: 'bhandara', name: 'Compressor BHD-1', type: 'Compressor', status: 'up', last_status_change: datetime('2026-07-30T15:00:00')});

// =====================================================================
// StructuralFeature (1-2 per site, general geology context)
// =====================================================================
CREATE (:StructuralFeature {id: 'sf_bal_01', site_id: 'balaghat', feature_type: 'fold_axis',      density_score: 0.71});
CREATE (:StructuralFeature {id: 'sf_bal_02', site_id: 'balaghat', feature_type: 'fault_line',      density_score: 0.58});
CREATE (:StructuralFeature {id: 'sf_nag_01', site_id: 'nagpur',   feature_type: 'shear_zone',       density_score: 0.63});
CREATE (:StructuralFeature {id: 'sf_bhd_01', site_id: 'bhandara', feature_type: 'fault_line',      density_score: 0.49});

// =====================================================================
// WeatherEvent (4 total). we_bal_01 is the primary demo event:
// severity 5 heavy_rain at Balaghat.
// =====================================================================
CREATE (:WeatherEvent {id: 'we_bal_01', site_id: 'balaghat', event_type: 'heavy_rain',   severity: 5, start_date: date('2026-08-24'), end_date: date('2026-08-29')});
CREATE (:WeatherEvent {id: 'we_bal_02', site_id: 'balaghat', event_type: 'dust_storm',   severity: 2, start_date: date('2026-07-10'), end_date: date('2026-07-11')});
CREATE (:WeatherEvent {id: 'we_nag_01', site_id: 'nagpur',   event_type: 'thunderstorm',severity: 2, start_date: date('2026-08-05'), end_date: date('2026-08-06')});
CREATE (:WeatherEvent {id: 'we_bhd_01', site_id: 'bhandara', event_type: 'heavy_rain',   severity: 3, start_date: date('2026-08-14'), end_date: date('2026-08-17')});

// =====================================================================
// BlastPlan (2-3 per site = 7 total)
// bp_bal_01 is DELAYED by we_bal_01 (the primary demo chain).
// =====================================================================
CREATE (:BlastPlan {id: 'bp_bal_01', site_id: 'balaghat', scheduled_date: date('2026-08-26'), status: 'delayed'});
CREATE (:BlastPlan {id: 'bp_bal_02', site_id: 'balaghat', scheduled_date: date('2026-09-05'), status: 'planned'});
CREATE (:BlastPlan {id: 'bp_bal_03', site_id: 'balaghat', scheduled_date: date('2026-08-10'), status: 'completed'});

CREATE (:BlastPlan {id: 'bp_nag_01', site_id: 'nagpur', scheduled_date: date('2026-09-02'), status: 'planned'});
CREATE (:BlastPlan {id: 'bp_nag_02', site_id: 'nagpur', scheduled_date: date('2026-08-08'), status: 'completed'});

CREATE (:BlastPlan {id: 'bp_bhd_01', site_id: 'bhandara', scheduled_date: date('2026-09-03'), status: 'planned'});
CREATE (:BlastPlan {id: 'bp_bhd_02', site_id: 'bhandara', scheduled_date: date('2026-08-12'), status: 'completed'});

// =====================================================================
// RiskEvent (2 total — one per demo chain)
// =====================================================================
CREATE (:RiskEvent {id: 're_bal_01', site_id: 'balaghat', risk_type: 'weather_delay', score: 0.78, description: 'Heavy rain (severity 5) at Balaghat delayed BlastPlan bp_bal_01, threatening OreZone oz_bal_01 extraction schedule.', detected_at: datetime('2026-08-25T07:00:00')});
CREATE (:RiskEvent {id: 're_nag_01', site_id: 'nagpur',   risk_type: 'equipment_failure', score: 0.68, description: 'Drill eq_nag_02 at Nagpur went down, blocking BlastPlan bp_nag_01 readiness.', detected_at: datetime('2026-08-28T10:15:00')});

// =====================================================================
// Relationships
// =====================================================================

// --- Equipment DEPENDS_ON BlastPlan ---
MATCH (e:Equipment {id: 'eq_bal_01'}), (b:BlastPlan {id: 'bp_bal_01'}) CREATE (e)-[:DEPENDS_ON]->(b);
MATCH (e:Equipment {id: 'eq_bal_02'}), (b:BlastPlan {id: 'bp_bal_01'}) CREATE (e)-[:DEPENDS_ON]->(b);
MATCH (e:Equipment {id: 'eq_bal_05'}), (b:BlastPlan {id: 'bp_bal_02'}) CREATE (e)-[:DEPENDS_ON]->(b);
MATCH (e:Equipment {id: 'eq_nag_01'}), (b:BlastPlan {id: 'bp_nag_01'}) CREATE (e)-[:DEPENDS_ON]->(b);
MATCH (e:Equipment {id: 'eq_nag_02'}), (b:BlastPlan {id: 'bp_nag_01'}) CREATE (e)-[:DEPENDS_ON]->(b);
MATCH (e:Equipment {id: 'eq_bhd_01'}), (b:BlastPlan {id: 'bp_bhd_01'}) CREATE (e)-[:DEPENDS_ON]->(b);
MATCH (e:Equipment {id: 'eq_bhd_03'}), (b:BlastPlan {id: 'bp_bhd_01'}) CREATE (e)-[:DEPENDS_ON]->(b);
// NOTE: eq_bhd_02 (Drill, up) intentionally has NO DEPENDS_ON edge — it is idle.

// --- WeatherEvent DELAYS BlastPlan ---
MATCH (w:WeatherEvent {id: 'we_bal_01'}), (b:BlastPlan {id: 'bp_bal_01'}) CREATE (w)-[:DELAYS]->(b);

// --- BlastPlan AFFECTS OreZone ---
MATCH (b:BlastPlan {id: 'bp_bal_01'}), (z:OreZone {id: 'oz_bal_01'}) CREATE (b)-[:AFFECTS]->(z);
MATCH (b:BlastPlan {id: 'bp_bal_02'}), (z:OreZone {id: 'oz_bal_02'}) CREATE (b)-[:AFFECTS]->(z);
MATCH (b:BlastPlan {id: 'bp_nag_01'}), (z:OreZone {id: 'oz_nag_01'}) CREATE (b)-[:AFFECTS]->(z);
MATCH (b:BlastPlan {id: 'bp_bhd_01'}), (z:OreZone {id: 'oz_bhd_01'}) CREATE (b)-[:AFFECTS]->(z);

// --- Equipment CAUSES RiskEvent (status = 'down') ---
MATCH (e:Equipment {id: 'eq_nag_02'}), (r:RiskEvent {id: 're_nag_01'}) CREATE (e)-[:CAUSES]->(r);
MATCH (e:Equipment {id: 'eq_bal_05'}), (r:RiskEvent {id: 're_bal_01'}) CREATE (e)-[:CAUSES]->(r);

// --- WeatherEvent CORRELATES_WITH RiskEvent ---
MATCH (w:WeatherEvent {id: 'we_bal_01'}), (r:RiskEvent {id: 're_bal_01'}) CREATE (w)-[:CORRELATES_WITH]->(r);

// =====================================================================
// VERIFICATION QUERIES — run these after loading to confirm the graph
// =====================================================================

// 1. Node counts by label
MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY label;

// 2. The primary Balaghat causal chain, end to end:
//    WeatherEvent -DELAYS-> BlastPlan -AFFECTS-> OreZone, plus the
//    correlated RiskEvent.
MATCH (w:WeatherEvent {id: 'we_bal_01'})-[:DELAYS]->(bp:BlastPlan)-[:AFFECTS]->(oz:OreZone)
MATCH (w)-[:CORRELATES_WITH]->(re:RiskEvent)
RETURN w.event_type AS weather, w.severity AS severity,
       bp.id AS blast_plan, bp.status AS blast_status,
       oz.id AS ore_zone, oz.grade_estimate AS grade,
       re.id AS risk_event, re.score AS risk_score, re.description AS description;

// 3. Idle-equipment redeploy candidate: find equipment that is "down"
//    and, at a different site, idle "up" equipment of the SAME type
//    that is not tied to any BlastPlan.
MATCH (down:Equipment {status: 'down'})
MATCH (idle:Equipment {status: 'up', type: down.type})
WHERE idle.site_id <> down.site_id
  AND NOT (idle)-[:DEPENDS_ON]->(:BlastPlan)
RETURN down.id AS down_equipment, down.site_id AS down_site,
       idle.id AS redeploy_candidate, idle.site_id AS candidate_site, idle.type AS type;
