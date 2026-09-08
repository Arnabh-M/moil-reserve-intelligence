// Frozen-contract fixtures. The UI adapts these API-shaped records without changing their wire types.
const sites = [
  { id: 1, name: 'Balaghat', belt_name: 'Balaghat Manganese Belt', district: 'Balaghat', state: 'Madhya Pradesh', centroid_lat: 21.81, centroid_lon: 80.18, active_risk_count: 3, avg_reserve_confidence: 0.82 },
  { id: 2, name: 'Nagpur', belt_name: 'Nagpur Manganese Belt', district: 'Nagpur', state: 'Maharashtra', centroid_lat: 21.15, centroid_lon: 79.09, active_risk_count: 2, avg_reserve_confidence: 0.74 },
  { id: 3, name: 'Bhandara', belt_name: 'Bhandara Manganese Belt', district: 'Bhandara', state: 'Maharashtra', centroid_lat: 21.17, centroid_lon: 79.65, active_risk_count: 1, avg_reserve_confidence: 0.88 },
];

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
  { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[80.12, 21.84], [80.22, 21.84], [80.22, 21.78], [80.12, 21.78], [80.12, 21.84]]] }, properties: { id: 501, site_id: 1, zone_name: 'Balaghat North Block', confidence_score: 0.91, estimated_grade_pct: 30.0, estimated_depth_m: 114 } },
  { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[80.22, 21.81], [80.29, 21.81], [80.29, 21.76], [80.22, 21.76], [80.22, 21.81]]] }, properties: { id: 502, site_id: 1, zone_name: 'Eastern ramp', confidence_score: 0.66, estimated_grade_pct: 1.41, estimated_depth_m: 88 } },
  { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[79.02, 21.19], [79.16, 21.19], [79.16, 21.11], [79.02, 21.11], [79.02, 21.19]]] }, properties: { id: 601, site_id: 2, zone_name: 'West pushback', confidence_score: 0.74, estimated_grade_pct: 3.1, estimated_depth_m: 132 } },
  { type: 'Feature', geometry: { type: 'Polygon', coordinates: [[[79.61, 21.20], [79.70, 21.20], [79.70, 21.14], [79.61, 21.14], [79.61, 21.20]]] }, properties: { id: 701, site_id: 3, zone_name: 'Southern extension', confidence_score: 0.88, estimated_grade_pct: 29.4, estimated_depth_m: 72 } },
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