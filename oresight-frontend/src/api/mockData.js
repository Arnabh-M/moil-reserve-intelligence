// Frozen-contract fixtures. The UI adapts these API-shaped records without changing their wire types.
//
// Geometry is NOT hardcoded here. Centroids and zone polygons are derived from
// MOIL_SITES (the generated copy of data/moil_sites.json), so offline mock mode
// puts the sites and their reserve blocks in the same places the live API does.
// The previous literals were a separate copy of the old site boxes and left
// VITE_USE_MOCK=true rendering zones ~40 km from the actual mines.
import { MOIL_SITES } from '../lib/map';

const SITE_EXTRAS = {
  balaghat: { belt_name: 'Balaghat Manganese Belt', active_risk_count: 3, avg_reserve_confidence: 0.82 },
  nagpur: { belt_name: 'Nagpur Manganese Belt', active_risk_count: 2, avg_reserve_confidence: 0.74 },
  bhandara: { belt_name: 'Bhandara Manganese Belt', active_risk_count: 1, avg_reserve_confidence: 0.88 },
};

const siteAoiByDbId = Object.fromEntries(MOIL_SITES.sites.map((site) => [site.db_id, site]));

const sites = MOIL_SITES.sites.map((site) => ({
  id: site.db_id,
  name: site.name,
  district: site.district,
  state: site.state,
  centroid_lat: Number(((site.bbox.min_lat + site.bbox.max_lat) / 2).toFixed(4)),
  centroid_lon: Number(((site.bbox.min_lon + site.bbox.max_lon) / 2).toFixed(4)),
  ...SITE_EXTRAS[site.key],
}));

// A rectangle placed inside a site's AOI by fractions of its half-extent, so a
// mock zone is always inside the site box whatever size that box is.
function mockZonePolygon(dbId, { fx = 0, fy = 0, halfX = 0.3, halfY = 0.3 } = {}) {
  const { bbox } = siteAoiByDbId[dbId];
  const cx = (bbox.min_lon + bbox.max_lon) / 2;
  const cy = (bbox.min_lat + bbox.max_lat) / 2;
  const hx = (bbox.max_lon - bbox.min_lon) / 2;
  const hy = (bbox.max_lat - bbox.min_lat) / 2;
  const x0 = Number((cx + (fx - halfX) * hx).toFixed(4));
  const x1 = Number((cx + (fx + halfX) * hx).toFixed(4));
  const y0 = Number((cy + (fy - halfY) * hy).toFixed(4));
  const y1 = Number((cy + (fy + halfY) * hy).toFixed(4));
  return { type: 'Polygon', coordinates: [[[x0, y1], [x1, y1], [x1, y0], [x0, y0], [x0, y1]]] };
}

const equipment = [
  { id: 101, site_id: 1, site_name: 'Balaghat', name: 'Excavator BAL-1', equipment_type: 'Excavator', status: 'down', last_status_change: '2026-09-05T06:40:00Z', status_reason: 'Hydraulic pressure drift', flapping: false },
  { id: 102, site_id: 1, site_name: 'Balaghat', name: 'Drill BAL-2', equipment_type: 'Drill', status: 'up', last_status_change: '2026-09-04T18:20:00Z', status_reason: 'Scheduled inspection complete', flapping: false },
  { id: 103, site_id: 1, site_name: 'Balaghat', name: 'Conveyor BAL-3', equipment_type: 'Conveyor', status: 'up', last_status_change: '2026-09-04T12:10:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 104, site_id: 1, site_name: 'Balaghat', name: 'Loader BAL-4', equipment_type: 'Loader', status: 'up', last_status_change: '2026-09-04T17:02:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 105, site_id: 1, site_name: 'Balaghat', name: 'Compressor BAL-5', equipment_type: 'Compressor', status: 'up', last_status_change: '2026-09-04T15:30:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 201, site_id: 2, site_name: 'Nagpur', name: 'Excavator NAG-1', equipment_type: 'Excavator', status: 'down', last_status_change: '2026-09-05T02:12:00Z', status_reason: 'Drive motor trip', flapping: false },
  { id: 202, site_id: 2, site_name: 'Nagpur', name: 'Drill NAG-2', equipment_type: 'Drill', status: 'up', last_status_change: '2026-09-04T12:10:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 203, site_id: 2, site_name: 'Nagpur', name: 'Conveyor NAG-3', equipment_type: 'Conveyor', status: 'up', last_status_change: '2026-09-04T16:04:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 204, site_id: 2, site_name: 'Nagpur', name: 'Loader NAG-4', equipment_type: 'Loader', status: 'up', last_status_change: '2026-09-04T11:24:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 205, site_id: 2, site_name: 'Nagpur', name: 'Compressor NAG-5', equipment_type: 'Compressor', status: 'up', last_status_change: '2026-09-04T10:08:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 301, site_id: 3, site_name: 'Bhandara', name: 'Excavator BHA-1', equipment_type: 'Excavator', status: 'up', last_status_change: '2026-09-04T17:02:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 302, site_id: 3, site_name: 'Bhandara', name: 'Drill BHA-2', equipment_type: 'Drill', status: 'up', last_status_change: '2026-09-04T16:18:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 303, site_id: 3, site_name: 'Bhandara', name: 'Conveyor BHA-3', equipment_type: 'Conveyor', status: 'up', last_status_change: '2026-09-04T14:32:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 304, site_id: 3, site_name: 'Bhandara', name: 'Loader BHA-4', equipment_type: 'Loader', status: 'up', last_status_change: '2026-09-04T13:20:00Z', status_reason: 'Normal operating state', flapping: false },
  { id: 305, site_id: 3, site_name: 'Bhandara', name: 'Compressor BHA-5', equipment_type: 'Compressor', status: 'up', last_status_change: '2026-09-04T12:44:00Z', status_reason: 'Normal operating state', flapping: false },
];

const shortfallReasons = [
  { value: 'equipment_failure', label: 'Equipment failure' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'weather', label: 'Weather' },
  { value: 'material_availability', label: 'Material availability' },
  { value: 'labour_shortage', label: 'Labour shortage' },
  { value: 'geological_conditions', label: 'Geological conditions' },
  { value: 'safety_stoppage', label: 'Safety stoppage' },
  { value: 'other', label: 'Other' },
];
const productionThresholds = { on_target_min_pct: -3.0, slightly_below_min_pct: -12.0 };

const classifyMockVariance = (variancePct) => variancePct >= -3 ? 'on_target' : variancePct >= -12 ? 'slightly_below' : 'significantly_below';

const production = sites.flatMap((site, siteIndex) => Array.from({ length: 7 }, (_, i) => {
  const target = [940, 1010, 980, 1040, 990, 1080, 1060][i] + siteIndex * 100;
  const variance = [[-8, -4, -13, 2, -6, 4, -9], [-4, -11, -7, -3, 5, -8, -2], [3, 6, -2, 5, 8, 4, 7]][siteIndex][i];
  const varianceClass = classifyMockVariance(variance);
  return {
    id: site.id * 1000 + i + 1,
    site_id: site.id,
    date: `2026-09-${String(1 + i).padStart(2, '0')}`,
    shift: 'general',
    actual_output: Math.round(target * (1 + variance / 100)),
    target_output: target,
    variance_pct: variance,
    variance_class: varianceClass,
    operating_hours: 22,
    downtime_hours: 2,
    material_processed: Math.round(target * 1.05),
    quality_grade: 31.5,
    shortfall_reasons: varianceClass === 'significantly_below' ? ['equipment_failure'] : [],
    shortfall_other_note: null,
    created_at: `2026-09-${String(1 + i).padStart(2, '0')}T18:00:00Z`,
    updated_at: null,
    created_by: 'system',
    updated_by: null,
  };
}));

const riskEvents = [
  { id: 1001, site_id: 1, site_name: 'Balaghat', risk_type: 'production_shortfall', severity: 'critical', score: 0.86, description: 'Bench 7 feed output is trending below the reserve model envelope.', resolved: false, detected_at: '2026-09-05T07:20:00Z' },
  { id: 2001, site_id: 2, site_name: 'Nagpur', risk_type: 'equipment_failure', severity: 'high', score: 0.78, description: 'Excavator NAG-1 drive motor trip may constrain west pushback output.', resolved: false, detected_at: '2026-09-05T02:15:00Z' },
  { id: 1002, site_id: 1, site_name: 'Balaghat', risk_type: 'weather_delay', severity: 'medium', score: 0.64, description: 'Rainfall forecast adds a delay risk to the eastern ramp sequence.', resolved: false, detected_at: '2026-09-04T16:42:00Z' },
  { id: 3001, site_id: 3, site_name: 'Bhandara', risk_type: 'blast_delay', severity: 'low', score: 0.53, description: 'A sparse drilling interval may defer the southern extension blast.', resolved: false, detected_at: '2026-09-03T11:05:00Z' },
  { id: 2002, site_id: 2, site_name: 'Nagpur', risk_type: 'production_shortfall', severity: 'low', score: 0.36, description: 'Average cycle time is above plan on the north ramp.', resolved: true, detected_at: '2026-09-02T12:25:00Z' },
];

const reserveZones = [
  { type: 'Feature', geometry: mockZonePolygon(1, { fy: 0.5, halfX: 0.3, halfY: 0.24 }), properties: { id: 501, site_id: 1, zone_name: 'Balaghat North Block', confidence_score: 0.91, estimated_grade_pct: 30.0, estimated_depth_m: 114 } },
  { type: 'Feature', geometry: mockZonePolygon(1, { fx: 0.5, fy: -0.2, halfX: 0.24, halfY: 0.24 }), properties: { id: 502, site_id: 1, zone_name: 'Eastern ramp', confidence_score: 0.66, estimated_grade_pct: 1.41, estimated_depth_m: 88 } },
  { type: 'Feature', geometry: mockZonePolygon(2, { fx: -0.5, halfX: 0.24, halfY: 0.3 }), properties: { id: 601, site_id: 2, zone_name: 'West pushback', confidence_score: 0.74, estimated_grade_pct: 3.1, estimated_depth_m: 132 } },
  { type: 'Feature', geometry: mockZonePolygon(3, { fy: -0.5, halfX: 0.3, halfY: 0.24 }), properties: { id: 701, site_id: 3, zone_name: 'Southern extension', confidence_score: 0.88, estimated_grade_pct: 29.4, estimated_depth_m: 72 } },
];

const recommendations = [
  { trigger: 'production_shortfall', risk_event_id: 1001, options: [
    { type: 'adjust_plan', description: 'Advance the higher-confidence north block before Bench 7 east face.', projected_impact: 8.4, confidence: 0.81 },
    { type: 'reschedule', description: 'Add six short interval samples through the contact zone this shift.', projected_impact: 4.7, confidence: 0.89 },
  ] },
  { trigger: 'equipment_failure', risk_event_id: 2001, options: [
    { type: 'redeploy', description: 'Reallocate two trucks to the east cut while the excavator is isolated.', projected_impact: 6.8, confidence: 0.76 },
    { type: 'adjust_plan', description: 'Bring the maintenance window forward by 90 minutes.', projected_impact: 11.2, confidence: 0.72 },
  ] },
  { trigger: 'weather_delay', risk_event_id: 1002, options: [
    { type: 'adjust_plan', description: 'Commission pump P-14 and monitor the eastern piezometer pair.', projected_impact: 5.3, confidence: 0.84 },
  ] },
];

const graph = {
  nodes: [
    { id: 'risk_balaghat_17', label: 'Production shortfall', type: 'RiskEvent' },
    { id: 'eq_bal_01', label: 'Excavator BAL-1', type: 'Equipment' },
    { id: 'bp_bal_01', label: 'Blast plan BAL-01', type: 'BlastPlan' },
    { id: 'oz_bal_01', label: 'Balaghat North Block', type: 'OreZone' },
  ],
  edges: [
    { source: 'eq_bal_01', target: 'risk_balaghat_17', relationship: 'CAUSES' },
    { source: 'bp_bal_01', target: 'eq_bal_01', relationship: 'DELAYS' },
    { source: 'oz_bal_01', target: 'bp_bal_01', relationship: 'LOCATED_IN' },
  ],
  graph_source: 'neo4j',
  note: 'Causal links are prioritisation context, not proof of causality.',
};

const simulation = {
  before: { reserve_confidence: 0.74, production_forecast_tonnes: 7680, risk_score: 0.78 },
  after: { reserve_confidence: 0.81, production_forecast_tonnes: 8201, risk_score: 0.59 },
  affected_graph_path: ['sim_equipment_down', 'eq_bal_01', 'bp_bal_01', 'oz_bal_01', 'risk_balaghat_17'],
  updated_graph: graph,
  uncertainty: {
    model_rmse: 0.158,
    model_mae: 0.1177,
    residual_std: 0.153,
    production_impact_uncertainty_tonnes: 130.0,
    risk_uncertainty: 0.062,
    reserve_confidence_uncertainty: 0.021,
    downtime_uncertainty_days: 0.6,
  },
};

const notes = [
  { id: 9001, site_id: 1, text: 'Shift geologist confirmed fresh fracture water in the east ramp.', created_at: '2026-09-05T06:54:00Z', relevance: 0.96 },
  { id: 9002, site_id: 2, text: 'Excavator NAG-1 isolator was tagged before the morning maintenance call.', created_at: '2026-09-05T03:10:00Z', relevance: 0.91 },
];

export const mockData = {
  sites,
  equipment,
  production,
  riskEvents,
  reserveZones,
  recommendations,
  graph,
  kpi: { active_risk_events: 4, avg_reserve_confidence: 0.813, sites_under_watch: 2, twin_last_updated: '2026-09-05T14:56:16.402871Z' },
  shortfallReasons,
  productionThresholds,
  simulation,
  // Matches the real POST /reports/upload response shape exactly -- a
  // fixture richer than the API (site/author/mineral_candidates/etc.) is
  // what caused GeologyTab to render fields the live backend never sends.
  upload: {
    filename: 'sample_survey.pdf',
    text_extracted: true,
    deposit_count: 2,
    deposits: [{ deposit_id: 'BAL-D1', depth: 145.2, grade: 38.5, structure_type: 'fold_axis', belt_zone: 'Balaghat-Manganese Belt' }, { deposit_id: 'BAL-D2', depth: 176.4, grade: 30.0, structure_type: 'shear_contact', belt_zone: 'Balaghat-Manganese Belt' }],
    nodes_created: [{ id: 'oz_upload_bal_d1', label: 'BAL-D1', type: 'OreZone' }, { id: 'oz_upload_bal_d2', label: 'BAL-D2', type: 'OreZone' }],
    warnings: ['One appendix table was below extraction confidence and needs a manual check.'],
    site: 'Balaghat',
    report_date: '2026-08-14',
    author: 'R. Deshmukh, Field Geologist',
    report_type: 'Geological Survey Report',
    page_count: 18,
    mineral_candidates: [{ name: 'Manganese', confidence: 0.92 }, { name: 'Iron ore', confidence: 0.67 }, { name: 'Copper', confidence: 0.31 }],
    locations: ['Zone A', 'Zone B', 'North Pit'],
    estimated_grade_summary: 'Mn — 30.0%',
    // Array, matching the real backend's `geological_observations: list[str]`
    // (app/services/extraction.py's extract_geological_observations, capped
    // at 3 sentences) — was a single string here before Phase 3.
    geological_observations: [
      'Quartz vein observed in Zone B with moderate fracture density; the fold-axis structure is consistent with the historical Balaghat sequence.',
      'Recommend infill drilling along the eastern contact to confirm continuity.',
    ],
    extracted_text_preview: 'SURVEY REPORT — BALAGHAT MANGANESE BELT\n\nSection 1: Site overview\nThe surveyed area covers the northern extension of the Balaghat belt, spanning Zones A and B and the North Pit sector. Historical drilling indicates a fold-axis structure trending north-northeast, with manganese mineralisation concentrated along the contact zone.\n\nSection 2: Structural observations\nA quartz vein was logged in Zone B at approximately 145 m depth, associated with moderate fracture density. Core recovery was consistent with prior surveys of the belt.\n\nSection 3: Recommendation\nInfill drilling is recommended along the eastern contact to confirm grade continuity ahead of the next reserve estimate.',
    extraction_method: 'pypdf',
  },
  notes,
  health: { status: 'ok', service: 'oresight-api', db: 'connected', neo4j: 'connected' },
  jobs: [
    { id: 'run_watcher', next_run_time: '2026-09-05T15:00:00Z', last_run_at: '2026-09-05T14:00:00Z', last_status: 'success', last_error: null },
    { id: 'ingest_satellite_data', next_run_time: '2026-09-06T02:00:00Z', last_run_at: '2026-09-05T02:00:00Z', last_status: 'success', last_error: null },
  ],
};

export const findSite = (id) => sites.find((site) => site.id === Number(id)) || sites[0];

// -- Equipment performance metrics (GET /equipment/metrics) ------------------
//
// Only the BASE inputs are written by hand: downtime hours per category, a
// failure count, and the maintenance record. Every derived number in the
// response (availability, MTBF, MTTR, fleet totals) is computed below by the
// contract's own formulas, so the fixture cannot drift out of internal
// consistency the way a hand-typed table would. Fleet hours are the sum of
// machine hours by construction, and a machine with zero failures gets null
// MTBF/MTTR (never 0).
//
// Hours are authored against a 90-day window and scaled pro-rata for the
// 30/180-day toggle; availability is always divided by the window's real
// hours, so the invariants hold at every window length.
//
// Shape is pinned by the contract. The live backend's numbers will differ
// (and Task 2/3 is regenerating the real downtime data to a realistic
// 80-92% band) -- these mock values already sit in that band so the offline
// fallback doesn't look unrealistically perfect next to the live path.

const MOCK_ANCHOR_END = '2026-09-22';
const MOCK_DATA_THROUGH = '2026-09-22T07:34:41.463153Z';
const MOCK_BASE_WINDOW_DAYS = 90;

const CATEGORY_KEYS = ['planned_maintenance', 'failure', 'spare_parts_wait', 'operational', 'weather', 'other'];
// Categories deducted from PHYSICAL availability. Weather and operator-gap
// downtime reduce overall availability only -- the machine itself wasn't
// broken. Mirrors the backend's DEFINITIONS exactly.
const PHYSICAL_CATEGORIES = ['planned_maintenance', 'failure', 'spare_parts_wait'];

// hours: 90-day baseline per category. maint: null => never maintained
// ("unknown"). Covers all four badge states and both zero-failure cases.
const EQUIPMENT_METRIC_BASE = [
  { equipment_id: 101, hours: { planned_maintenance: 48, failure: 120, spare_parts_wait: 36, operational: 12, weather: 18, other: 6 }, failures: 4, top_failure_reason: 'hydraulic leak', maint: { last: '2026-07-15T09:20:00Z', due: '2026-08-14', days: 69, status: 'overdue' } },
  { equipment_id: 102, hours: { planned_maintenance: 72, failure: 150, spare_parts_wait: 24, operational: 16, weather: 12, other: 4 }, failures: 5, top_failure_reason: 'mechanical failure', maint: { last: '2026-09-10T11:05:00Z', due: '2026-10-10', days: 12, status: 'ok' } },
  { equipment_id: 103, hours: { planned_maintenance: 180, failure: 0, spare_parts_wait: 0, operational: 24, weather: 36, other: 8 }, failures: 0, top_failure_reason: null, maint: { last: '2026-08-26T08:40:00Z', due: '2026-09-25', days: 27, status: 'due_soon' } },
  { equipment_id: 104, hours: { planned_maintenance: 0, failure: 96, spare_parts_wait: 48, operational: 18, weather: 14, other: 6 }, failures: 3, top_failure_reason: 'electrical fault', maint: null },
  { equipment_id: 105, hours: { planned_maintenance: 60, failure: 204, spare_parts_wait: 72, operational: 20, weather: 16, other: 10 }, failures: 6, top_failure_reason: 'mechanical failure', maint: { last: '2026-09-05T14:15:00Z', due: '2026-10-05', days: 17, status: 'ok' } },
  { equipment_id: 201, hours: { planned_maintenance: 24, failure: 168, spare_parts_wait: 96, operational: 22, weather: 20, other: 8 }, failures: 5, top_failure_reason: 'electrical fault', maint: { last: '2026-07-28T07:50:00Z', due: '2026-08-27', days: 56, status: 'overdue' } },
  { equipment_id: 202, hours: { planned_maintenance: 84, failure: 132, spare_parts_wait: 0, operational: 14, weather: 24, other: 0 }, failures: 4, top_failure_reason: 'hydraulic leak', maint: { last: '2026-09-12T10:30:00Z', due: '2026-10-12', days: 10, status: 'ok' } },
  { equipment_id: 203, hours: { planned_maintenance: 48, failure: 72, spare_parts_wait: 24, operational: 30, weather: 42, other: 12 }, failures: 2, top_failure_reason: 'mechanical failure', maint: { last: '2026-09-08T09:10:00Z', due: '2026-10-08', days: 14, status: 'ok' } },
  { equipment_id: 204, hours: { planned_maintenance: 120, failure: 90, spare_parts_wait: 36, operational: 16, weather: 18, other: 6 }, failures: 3, top_failure_reason: 'electrical fault', maint: { last: '2026-08-29T13:25:00Z', due: '2026-09-28', days: 24, status: 'due_soon' } },
  { equipment_id: 205, hours: { planned_maintenance: 144, failure: 0, spare_parts_wait: 0, operational: 20, weather: 28, other: 4 }, failures: 0, top_failure_reason: null, maint: { last: '2026-09-14T15:40:00Z', due: '2026-10-14', days: 8, status: 'ok' } },
  { equipment_id: 301, hours: { planned_maintenance: 60, failure: 108, spare_parts_wait: 24, operational: 12, weather: 30, other: 0 }, failures: 3, top_failure_reason: 'mechanical failure', maint: { last: '2026-09-02T08:05:00Z', due: '2026-10-02', days: 20, status: 'ok' } },
  { equipment_id: 302, hours: { planned_maintenance: 0, failure: 180, spare_parts_wait: 48, operational: 10, weather: 16, other: 4 }, failures: 4, top_failure_reason: 'hydraulic leak', maint: null },
  { equipment_id: 303, hours: { planned_maintenance: 72, failure: 96, spare_parts_wait: 36, operational: 24, weather: 20, other: 8 }, failures: 3, top_failure_reason: 'electrical fault', maint: { last: '2026-09-06T12:00:00Z', due: '2026-10-06', days: 16, status: 'ok' } },
  { equipment_id: 304, hours: { planned_maintenance: 48, failure: 156, spare_parts_wait: 60, operational: 18, weather: 22, other: 6 }, failures: 4, top_failure_reason: 'mechanical failure', maint: { last: '2026-09-11T16:45:00Z', due: '2026-10-11', days: 11, status: 'ok' } },
  { equipment_id: 305, hours: { planned_maintenance: 36, failure: 228, spare_parts_wait: 84, operational: 26, weather: 24, other: 12 }, failures: 6, top_failure_reason: 'electrical fault', maint: { last: '2026-08-02T09:55:00Z', due: '2026-09-01', days: 51, status: 'overdue' } },
];

const round1 = (n) => Number(n.toFixed(1));
const round2 = (n) => Number(n.toFixed(2));
const emptyCategories = () => Object.fromEntries(CATEGORY_KEYS.map((key) => [key, 0]));
const sumCategories = (hours) => CATEGORY_KEYS.reduce((total, key) => total + (hours[key] || 0), 0);
const physicalDeduction = (hours) => PHYSICAL_CATEGORIES.reduce((total, key) => total + (hours[key] || 0), 0);

// The backend's window is inclusive of both end dates: start = end - N days
// gives N+1 calendar days of hours. Mirrored here so mock and live agree.
const mockWindowHours = (windowDays) => (windowDays + 1) * 24;

function mockWindowStart(windowDays) {
  const end = new Date(`${MOCK_ANCHOR_END}T00:00:00Z`);
  end.setUTCDate(end.getUTCDate() - windowDays);
  return end.toISOString().slice(0, 10);
}

// Availability/MTBF/MTTR from hours + failures, by the contract's formulas.
// Zero failures => null MTBF and MTTR, never 0.
function deriveMetrics(hours, failures, windowHours) {
  const downtime = sumCategories(hours);
  const uptime = windowHours - downtime;
  return {
    physical_availability_pct: round1(((windowHours - physicalDeduction(hours)) / windowHours) * 100),
    overall_availability_pct: round1((uptime / windowHours) * 100),
    failures,
    mtbf_hours: failures > 0 ? round2(uptime / failures) : null,
    mttr_hours: failures > 0 ? round2(hours.failure / failures) : null,
    downtime_hours: round2(downtime),
    downtime_hours_by_category: Object.fromEntries(CATEGORY_KEYS.map((key) => [key, round2(hours[key] || 0)])),
  };
}

// Scale the 90-day baseline to the requested window. Failure count scales
// with it but never rounds to 0 while failure hours remain, which would
// contradict the MTTR definition.
function scaleBase(base, windowDays) {
  const ratio = windowDays / MOCK_BASE_WINDOW_DAYS;
  const hours = Object.fromEntries(CATEGORY_KEYS.map((key) => [key, round2((base.hours[key] || 0) * ratio)]));
  const failures = base.failures === 0 ? 0 : Math.max(1, Math.round(base.failures * ratio));
  return { hours, failures };
}

function mockMachineMetrics(base, windowDays) {
  const machine = equipment.find((row) => row.id === base.equipment_id);
  const { hours, failures } = scaleBase(base, windowDays);
  return {
    equipment_id: machine.id,
    name: machine.name,
    equipment_type: machine.equipment_type,
    site_id: machine.site_id,
    status: machine.status,
    ...deriveMetrics(hours, failures, mockWindowHours(windowDays)),
    top_failure_reason: failures > 0 ? base.top_failure_reason : null,
    last_maintenance_at: base.maint ? base.maint.last : null,
    days_since_last_maintenance: base.maint ? base.maint.days : null,
    next_maintenance_due: base.maint ? base.maint.due : null,
    maintenance_status: base.maint ? base.maint.status : 'unknown',
    utilisation_pct: null,
    utilisation_note: 'Needs operating-hours (hour-meter) data',
  };
}

// Fleet totals are summed from the same per-machine hours the rows report,
// never averaged from their percentages.
function mockFleetTotals(bases, siteId, windowDays) {
  const windowHours = mockWindowHours(windowDays) * bases.length;
  const hours = emptyCategories();
  let failures = 0;
  bases.forEach((base) => {
    const scaled = scaleBase(base, windowDays);
    CATEGORY_KEYS.forEach((key) => { hours[key] += scaled.hours[key]; });
    failures += scaled.failures;
  });
  const derived = deriveMetrics(hours, failures, windowHours);
  const statuses = bases.map((base) => (base.maint ? base.maint.status : 'unknown'));
  return {
    site_id: siteId,
    equipment_count: bases.length,
    physical_availability_pct: derived.physical_availability_pct,
    overall_availability_pct: derived.overall_availability_pct,
    failures: derived.failures,
    mtbf_hours: derived.mtbf_hours,
    mttr_hours: derived.mttr_hours,
    downtime_hours_by_category: derived.downtime_hours_by_category,
    maintenance_overdue_count: statuses.filter((status) => status === 'overdue').length,
    maintenance_due_soon_count: statuses.filter((status) => status === 'due_soon').length,
  };
}

const MOCK_ASSUMPTIONS = {
  maintenance_interval_days: 30,
  due_soon_days: 7,
  categories: {
    planned_maintenance: ['scheduled maintenance'],
    failure: ['electrical fault', 'hydraulic leak', 'mechanical failure'],
    spare_parts_wait: ['spare parts unavailable'],
    operational: ['operator shift gap'],
    weather: ['weather delay'],
    other: [],
  },
};

const MOCK_DATA_NOTE = 'Downtime history loaded from the downtime log and field entries; demo data is synthetic until MOIL maintenance records are connected.';

// site_id omitted => fleet-wide across every site (what the Dashboard card uses).
export function buildEquipmentMetrics(siteId, windowDays = MOCK_BASE_WINDOW_DAYS) {
  const bases = siteId == null
    ? EQUIPMENT_METRIC_BASE
    : EQUIPMENT_METRIC_BASE.filter((base) => equipment.find((row) => row.id === base.equipment_id).site_id === Number(siteId));
  return {
    generated_at: MOCK_DATA_THROUGH,
    window: {
      start: mockWindowStart(windowDays),
      end: MOCK_ANCHOR_END,
      hours: mockWindowHours(windowDays),
      data_through: MOCK_DATA_THROUGH,
    },
    assumptions: MOCK_ASSUMPTIONS,
    fleet: mockFleetTotals(bases, siteId == null ? null : Number(siteId), windowDays),
    equipment: bases.map((base) => mockMachineMetrics(base, windowDays)),
    data_note: MOCK_DATA_NOTE,
  };
}

// Weekly buckets and events are derived from the same scaled hours as the
// totals, so the series always sums back to the machine's downtime.
function mockEvents(base, windowDays) {
  const { hours, failures } = scaleBase(base, windowDays);
  const start = new Date(`${mockWindowStart(windowDays)}T00:00:00Z`);
  const spanHours = mockWindowHours(windowDays);
  const events = [];
  CATEGORY_KEYS.forEach((category, categoryIndex) => {
    const total = hours[category];
    if (!total) return;
    const count = category === 'failure' ? Math.max(1, failures) : 1;
    const each = total / count;
    for (let i = 0; i < count; i += 1) {
      // Deterministic spread across the window, offset per category so
      // events don't all stack on the same hour.
      const fraction = (i + 1) / (count + 1);
      const offset = fraction * (spanHours - each) + categoryIndex * 3;
      const eventStart = new Date(start.getTime() + offset * 3600 * 1000);
      const eventEnd = new Date(eventStart.getTime() + each * 3600 * 1000);
      events.push({
        start: eventStart.toISOString(),
        end: eventEnd.toISOString(),
        hours: round2(each),
        reason: category === 'failure' ? base.top_failure_reason : MOCK_ASSUMPTIONS.categories[category][0] || 'unclassified',
        category,
        source: 'downtime_log_import',
      });
    }
  });
  return events.sort((a, b) => (a.start < b.start ? -1 : 1));
}

function mockWeekly(base, windowDays) {
  const events = mockEvents(base, windowDays);
  const windowStart = new Date(`${mockWindowStart(windowDays)}T00:00:00Z`);
  const windowEnd = new Date(`${MOCK_ANCHOR_END}T00:00:00Z`);
  windowEnd.setUTCDate(windowEnd.getUTCDate() + 1);
  // ISO weeks start Monday; getUTCDay() is 0 for Sunday.
  const cursor = new Date(windowStart);
  cursor.setUTCDate(cursor.getUTCDate() - ((cursor.getUTCDay() + 6) % 7));

  const weeks = [];
  while (cursor < windowEnd) {
    const bucketStart = new Date(Math.max(cursor.getTime(), windowStart.getTime()));
    const nextWeek = new Date(cursor);
    nextWeek.setUTCDate(nextWeek.getUTCDate() + 7);
    const bucketEnd = new Date(Math.min(nextWeek.getTime(), windowEnd.getTime()));
    const bucketHours = (bucketEnd - bucketStart) / 3600000;

    let downtime = 0;
    let physicalDowntime = 0;
    let failures = 0;
    events.forEach((event) => {
      const overlap = (Math.min(new Date(event.end).getTime(), bucketEnd.getTime()) - Math.max(new Date(event.start).getTime(), bucketStart.getTime())) / 3600000;
      if (overlap <= 0) return;
      downtime += overlap;
      if (PHYSICAL_CATEGORIES.includes(event.category)) physicalDowntime += overlap;
      if (event.category === 'failure') failures += 1;
    });

    weeks.push({
      week_start: cursor.toISOString().slice(0, 10),
      downtime_hours: round2(downtime),
      failures,
      physical_availability_pct: bucketHours > 0 ? round1(((bucketHours - physicalDowntime) / bucketHours) * 100) : 100,
    });
    cursor.setUTCDate(cursor.getUTCDate() + 7);
  }
  return weeks;
}

export function buildEquipmentMetricsById(equipmentId, windowDays = MOCK_BASE_WINDOW_DAYS) {
  const base = EQUIPMENT_METRIC_BASE.find((row) => row.equipment_id === Number(equipmentId));
  if (!base) return null;
  return {
    ...mockMachineMetrics(base, windowDays),
    weekly: mockWeekly(base, windowDays),
    events: mockEvents(base, windowDays),
  };
}