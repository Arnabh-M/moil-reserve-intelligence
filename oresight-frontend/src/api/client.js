// ─────────────────────────────────────────────────────────────────────
// OreSight API Client
// Single constant USE_MOCK toggles between simulated responses and
// real FastAPI calls at http://localhost:8002.
// ─────────────────────────────────────────────────────────────────────

import { sites as mockSites } from '../data/mockData';

export let USE_MOCK = false; // Default: attempt live backend, fallback seamlessly if offline

const BASE_URL = 'http://localhost:8002';

// Global listeners for reactive UI mode toggling
const mockListeners = new Set();

export function setUseMock(val) {
  USE_MOCK = Boolean(val);
  mockListeners.forEach(cb => cb(USE_MOCK));
}

export function subscribeUseMock(cb) {
  mockListeners.add(cb);
  return () => mockListeners.delete(cb);
}

// Site ID mapping (supports numeric 1,2,3 or string 'balaghat','nagpur','bhandara')
export const SITE_MAP = {
  balaghat: 1,
  nagpur: 2,
  bhandara: 3,
  1: 1,
  2: 2,
  3: 3,
};

export const SITE_NAME_MAP = {
  1: 'Balaghat',
  2: 'Nagpur',
  3: 'Bhandara',
  balaghat: 'Balaghat',
  nagpur: 'Nagpur',
  bhandara: 'Bhandara',
};

// ── In-Memory Mock Store ───────────────────────────────────────────────

let mockEquipment = [
  { id: 1, site_id: 1, site_name: 'Balaghat', name: 'Excavator EX-201', equipment_type: 'excavator', status: 'down', status_reason: 'Hydraulic pump failure - spare part on order' },
  { id: 2, site_id: 1, site_name: 'Balaghat', name: 'Rock Drill DR-101', equipment_type: 'drill', status: 'up', status_reason: null },
  { id: 3, site_id: 1, site_name: 'Balaghat', name: 'Haul Truck HT-301', equipment_type: 'haul_truck', status: 'up', status_reason: null },
  { id: 4, site_id: 1, site_name: 'Balaghat', name: 'Jaw Crusher CR-401', equipment_type: 'crusher', status: 'up', status_reason: null },
  { id: 5, site_id: 1, site_name: 'Balaghat', name: 'Wheel Loader LD-501', equipment_type: 'loader', status: 'up', status_reason: null },
  { id: 6, site_id: 2, site_name: 'Nagpur', name: 'Excavator EX-202', equipment_type: 'excavator', status: 'up', status_reason: null },
  { id: 7, site_id: 2, site_name: 'Nagpur', name: 'Rock Drill DR-102', equipment_type: 'drill', status: 'up', status_reason: null },
  { id: 8, site_id: 2, site_name: 'Nagpur', name: 'Haul Truck HT-302', equipment_type: 'haul_truck', status: 'down', status_reason: 'Engine overheating - pulled for inspection' },
  { id: 9, site_id: 2, site_name: 'Nagpur', name: 'Jaw Crusher CR-402', equipment_type: 'crusher', status: 'up', status_reason: null },
  { id: 10, site_id: 2, site_name: 'Nagpur', name: 'Wheel Loader LD-502', equipment_type: 'loader', status: 'up', status_reason: null },
  { id: 11, site_id: 3, site_name: 'Bhandara', name: 'Excavator EX-203', equipment_type: 'excavator', status: 'up', status_reason: null },
  { id: 12, site_id: 3, site_name: 'Bhandara', name: 'Rock Drill DR-103', equipment_type: 'drill', status: 'up', status_reason: null },
  { id: 13, site_id: 3, site_name: 'Bhandara', name: 'Haul Truck HT-303', equipment_type: 'haul_truck', status: 'up', status_reason: null },
  { id: 14, site_id: 3, site_name: 'Bhandara', name: 'Jaw Crusher CR-403', equipment_type: 'crusher', status: 'up', status_reason: null },
  { id: 15, site_id: 3, site_name: 'Bhandara', name: 'Wheel Loader LD-503', equipment_type: 'loader', status: 'up', status_reason: null },
];

let mockRiskEvents = [
  {
    id: 1,
    site_id: 1,
    site_name: 'Balaghat',
    risk_type: 'equipment_failure',
    severity: 'high',
    score: 0.81,
    description: 'Excavator EX-201 hydraulic failure is stalling ore extraction at Balaghat.',
    resolved: false,
    detected_at: '2026-08-30T06:20:04.654Z',
  },
  {
    id: 2,
    site_id: 2,
    site_name: 'Nagpur',
    risk_type: 'weather_delay',
    severity: 'medium',
    score: 0.55,
    description: 'Heavy monsoon rainfall forecast to delay haul road access at Nagpur.',
    resolved: false,
    detected_at: '2026-08-28T07:20:04.654Z',
  },
  {
    id: 3,
    site_id: 3,
    site_name: 'Bhandara',
    risk_type: 'production_shortfall',
    severity: 'high',
    score: 0.70,
    description: 'Bhandara actual output fell sharply below daily target.',
    resolved: false,
    detected_at: '2026-08-26T07:20:04.654Z',
  },
  {
    id: 4,
    site_id: 1,
    site_name: 'Balaghat',
    risk_type: 'blast_delay',
    severity: 'low',
    score: 0.30,
    description: 'Scheduled blast at Balaghat postponed pending geotechnical clearance.',
    resolved: true,
    detected_at: '2026-08-24T06:20:04.654Z',
  },
];

function generateMockProduction(siteId, days = 60) {
  const records = [];
  const baseOutputs = { 1: 1210, 2: 1030, 3: 960 };
  const baseTargets = { 1: 1250, 2: 1050, 3: 980 };
  const base = baseOutputs[siteId] || 1000;
  const target = baseTargets[siteId] || 1000;

  const today = new Date('2026-08-31');
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().split('T')[0];
    const wave = Math.sin(i * 0.5) * 0.08 + Math.cos(i * 1.1) * 0.04;
    const actual = Math.round((base * (1 + wave)) * 10) / 10;
    const variance = Math.round(((actual - target) / target) * 10000) / 100;
    records.push({
      id: 100 + (days - i),
      site_id: siteId,
      date: dateStr,
      actual_output: actual,
      target_output: target,
      variance_pct: variance,
    });
  }
  return records;
}

let mockProductionHistory = {
  1: generateMockProduction(1, 60),
  2: generateMockProduction(2, 60),
  3: generateMockProduction(3, 60),
};

const delay = (ms = 500) => new Promise(resolve => setTimeout(resolve, ms));

// ── Generic Fetch Helper with Network Failure Handling ─────────────────

async function apiFetch(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Accept': 'application/json',
        ...(options.headers || {}),
      },
    });

    if (!res.ok) {
      let detail = `HTTP Error ${res.status}`;
      try {
        const json = await res.json();
        if (json.detail) detail = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
      } catch { /* not json */ }
      const err = new Error(detail);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } catch (err) {
    if (err.name === 'TypeError' && (err.message.includes('fetch') || err.message.includes('Failed to fetch') || err.message.includes('NetworkError'))) {
      const netErr = new Error(`Cannot connect to live API at ${BASE_URL}. Ensure FastAPI backend is running.`);
      netErr.isNetworkError = true;
      throw netErr;
    }
    throw err;
  }
}

// ───────────────────────────────────────────────────────────────────────
// 0. SITES (GET /sites)
// ───────────────────────────────────────────────────────────────────────

export async function getSites() {
  if (!USE_MOCK) {
    try {
      return await apiFetch('/sites');
    } catch (err) {
      console.warn('[API] getSites live failed, using mock:', err.message);
    }
  }

  await delay(200);
  return [...mockSites];
}

export async function getReserveZones(siteId) {
  const query = siteId != null ? `?site_id=${encodeURIComponent(siteId)}` : '';

  if (!USE_MOCK) {
    try {
      return await apiFetch(`/reserve-zones${query}`);
    } catch (err) {
      console.warn('[API] getReserveZones live call failed, using fallback:', err.message);
    }
  }

  await delay(300);
  try {
    const res = await fetch('/reserve_zones.geojson');
    if (res.ok) {
      const geojson = await res.json();
      if (siteId != null && geojson.features) {
        const targetSiteId = String(siteId).toLowerCase();
        const siteNameTarget = SITE_NAME_MAP[siteId] ? SITE_NAME_MAP[siteId].toLowerCase() : targetSiteId;
        const filteredFeatures = geojson.features.filter(f => {
          const fSite = String(f.properties?.site_id || '').toLowerCase();
          return fSite === targetSiteId || fSite === siteNameTarget;
        });
        return { ...geojson, features: filteredFeatures };
      }
      return geojson;
    }
  } catch (err) {
    console.warn('[API] Fallback fetch for reserve_zones.geojson failed:', err);
  }

  return { type: 'FeatureCollection', features: [] };
}

// ───────────────────────────────────────────────────────────────────────
// 1. WHAT-IF SIMULATION (POST /simulate)
// ───────────────────────────────────────────────────────────────────────

/**
 * Runs a what-if scenario simulation
 * POST /simulate
 * @param {Object} payload { scenario_type: 'equipment_down'|'delay_blasting'|'rainfall_event', site_id: number, duration_days: number }
 */
export async function postSimulate({ scenario_type, site_id, duration_days }) {
  const numSiteId = SITE_MAP[site_id] || Number(site_id) || 1;
  const numDuration = parseInt(duration_days, 10) || 3;

  if (!USE_MOCK) {
    try {
      return await apiFetch('/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_type,
          site_id: numSiteId,
          duration_days: numDuration,
        }),
      });
    } catch (err) {
      console.warn('[API] /simulate live call failed, falling back to mock:', err.message);
      if (!err.isNetworkError && err.status !== 404 && err.status !== 500) throw err;
    }
  }

  // Mock Fallback Simulation (strictly follows backend math in simulate.py)
  await delay(600);

  const rates = {
    equipment_down: { production: 0.045, risk: 0.05, confidence: 0.002 },
    delay_blasting: { production: 0.03, risk: 0.035, confidence: 0.015 },
    rainfall_event: { production: 0.05, risk: 0.04, confidence: 0.003 },
  }[scenario_type] || { production: 0.04, risk: 0.04, confidence: 0.005 };

  const siteBaselines = {
    1: { confidence: 0.67, production: 1210.0, risk: 0.42, name: 'Balaghat' },
    2: { confidence: 0.673, production: 1030.0, risk: 0.55, name: 'Nagpur' },
    3: { confidence: 0.675, production: 960.0, risk: 0.70, name: 'Bhandara' },
  }[numSiteId] || { confidence: 0.67, production: 1100.0, risk: 0.45, name: 'Balaghat' };

  const production_drop = Math.min(rates.production * numDuration, 0.6);
  const risk_increase = Math.min(rates.risk * numDuration, 0.65);
  const confidence_drop = Math.min(rates.confidence * numDuration, 0.25);

  const before = {
    reserve_confidence: siteBaselines.confidence,
    production_forecast_tonnes: siteBaselines.production,
    risk_score: siteBaselines.risk,
  };

  const after = {
    reserve_confidence: parseFloat(Math.max(before.reserve_confidence * (1 - confidence_drop), 0.05).toFixed(3)),
    production_forecast_tonnes: parseFloat((before.production_forecast_tonnes * (1 - production_drop)).toFixed(1)),
    risk_score: parseFloat(Math.min(before.risk_score + risk_increase, 0.97).toFixed(3)),
  };

  const scenarioLabels = {
    equipment_down: 'Equipment Down',
    delay_blasting: 'Blast Plan Delay',
    rainfall_event: 'Rainfall Event',
  };
  const label = scenarioLabels[scenario_type] || 'Disruption Event';

  const trigger_node_id = `sim_${scenario_type}`;
  const production_node_id = 'production_forecast';
  const risk_node_id = 'risk_event_sim';

  const nodes = [
    {
      id: trigger_node_id,
      label: `Simulated: ${label} at ${siteBaselines.name}`,
      type: 'SimulatedEvent',
    },
  ];
  const edges = [];
  const affected_path = [trigger_node_id];

  if (scenario_type === 'equipment_down') {
    const eqRow = mockEquipment.find(e => e.site_id === numSiteId) || mockEquipment[0];
    const eq_node_id = `equipment_${eqRow.id}`;
    nodes.push({ id: eq_node_id, label: eqRow.name, type: 'Equipment' });
    edges.push({ source: trigger_node_id, target: eq_node_id, relationship: 'TRIGGERS' });
    edges.push({ source: eq_node_id, target: production_node_id, relationship: 'REDUCES' });
    affected_path.push(eq_node_id);
  } else {
    edges.push({ source: trigger_node_id, target: production_node_id, relationship: 'REDUCES' });
  }

  nodes.push({ id: production_node_id, label: 'Production Forecast', type: 'ProductionForecast' });
  nodes.push({ id: risk_node_id, label: `Simulated ${label} Risk`, type: 'RiskEvent' });
  edges.push({ source: production_node_id, target: risk_node_id, relationship: 'TRIGGERS' });
  affected_path.push(production_node_id, risk_node_id);

  return {
    before,
    after,
    affected_graph_path: affected_path,
    updated_graph: { nodes, edges },
  };
}

export const simulateScenario = postSimulate;

// ───────────────────────────────────────────────────────────────────────
// 2. RECOMMENDATIONS (GET /recommendations?risk_event_id=...)
// ───────────────────────────────────────────────────────────────────────

/**
 * Get mitigation recommendations for a specific risk event
 * GET /recommendations?risk_event_id={risk_event_id}
 */
export async function getRecommendations({ risk_event_id }) {
  if (!USE_MOCK) {
    try {
      return await apiFetch(`/recommendations?risk_event_id=${risk_event_id}`);
    } catch (err) {
      console.warn(`[API] /recommendations?risk_event_id=${risk_event_id} failed:`, err.message);
      if (!err.isNetworkError && err.status !== 404 && err.status !== 500) throw err;
    }
  }

  // Mock Fallback
  await delay(450);
  const event = mockRiskEvents.find(r => r.id === Number(risk_event_id)) || mockRiskEvents[0];
  const siteName = event.site_name || 'Balaghat';

  return [
    {
      trigger: event.description || `Active ${event.risk_type} risk detected at ${siteName}`,
      risk_event_id: event.id,
      options: [
        {
          type: 'reschedule',
          description: `Delay the next blast at ${siteName} by 2 days to let primary extraction equipment return to service.`,
          projected_impact: 62.5,
          confidence: 0.78,
        },
        {
          type: 'redeploy',
          description: `Redeploy auxiliary equipment to cover primary workload at ${siteName} for the duration of the outage.`,
          projected_impact: 71.0,
          confidence: 0.82,
        },
        {
          type: 'adjust_plan',
          description: `Lower ${siteName}'s daily target output by 15% until repairs are completed.`,
          projected_impact: 45.0,
          confidence: 0.90,
        },
      ],
    },
    {
      trigger: `Elevated ${event.risk_type} frequency across ${siteName} zone`,
      risk_event_id: event.id,
      options: [
        {
          type: 'reschedule',
          description: `Shift ${siteName}'s next 2 haul cycles to morning shifts to minimize environmental exposure.`,
          projected_impact: 54.0,
          confidence: 0.66,
        },
        {
          type: 'redeploy',
          description: `Temporarily reassign a wheel loader from a neighbouring pit to ${siteName}.`,
          projected_impact: 68.5,
          confidence: 0.71,
        },
        {
          type: 'adjust_plan',
          description: `Revise ${siteName}'s weekly production baseline downward by 10% for this cycle.`,
          projected_impact: 40.0,
          confidence: 0.85,
        },
      ],
    },
  ];
}

/**
 * Fetches recommendations across all active risk events
 */
export async function getAllRecommendations() {
  if (!USE_MOCK) {
    try {
      // 1. Fetch active risk events
      const riskEvents = await apiFetch('/risk-events');
      if (riskEvents && riskEvents.length > 0) {
        // Fetch recommendations for the first 3 events
        const recPromises = riskEvents.slice(0, 3).map(ev =>
          apiFetch(`/recommendations?risk_event_id=${ev.id}`).catch(() => [])
        );
        const results = await Promise.all(recPromises);
        const flattened = results.flat();
        if (flattened.length > 0) return flattened;
      }
    } catch (err) {
      console.warn('[API] getAllRecommendations failed, using fallback:', err.message);
    }
  }

  // Mock Fallback
  await delay(500);
  return [
    {
      trigger: 'Excavator EX-201 hydraulic failure stalling ore extraction at Balaghat.',
      risk_event_id: 1,
      options: [
        {
          type: 'reschedule',
          description: 'Delay BlastPlan bp_bal_01 by 2 days until hydraulic seals are replaced at Balaghat.',
          projected_impact: 62.5,
          confidence: 0.78,
        },
        {
          type: 'redeploy',
          description: 'Redeploy Rock Drill DR-101 and Wheel Loader LD-501 to cover EX-201 workload at Balaghat.',
          projected_impact: 71.0,
          confidence: 0.82,
        },
        {
          type: 'adjust_plan',
          description: "Lower Balaghat's daily target output by 15% (to 1,062 t/day) until EX-201 returns to service.",
          projected_impact: 45.0,
          confidence: 0.90,
        },
      ],
    },
    {
      trigger: 'Heavy monsoon rainfall forecast at Nagpur — haul road access compromised.',
      risk_event_id: 2,
      options: [
        {
          type: 'reschedule',
          description: 'Postpone Nagpur haulage cycles to morning clear-weather windows.',
          projected_impact: 58.0,
          confidence: 0.72,
        },
        {
          type: 'redeploy',
          description: 'Transfer high-clearance Haul Truck HT-303 from Bhandara to Nagpur for pit drainage transport.',
          projected_impact: 74.5,
          confidence: 0.85,
        },
        {
          type: 'adjust_plan',
          description: 'Adjust blasting charge geometry to reduce water accumulation in pit benches.',
          projected_impact: 49.0,
          confidence: 0.88,
        },
      ],
    },
    {
      trigger: 'Bhandara production shortfall — actual output 720 t vs 960 t target (25% below).',
      risk_event_id: 3,
      options: [
        {
          type: 'reschedule',
          description: 'Schedule conveyor overhaul for weekend off-peak hours to recover full throughput.',
          projected_impact: 55.0,
          confidence: 0.68,
        },
        {
          type: 'redeploy',
          description: 'Route Bhandara extraction through secondary loader feeder bypass path.',
          projected_impact: 85.0,
          confidence: 0.80,
        },
        {
          type: 'adjust_plan',
          description: 'Offset shortfall by increasing Balaghat daily quota by 120 t/day.',
          projected_impact: 64.0,
          confidence: 0.91,
        },
      ],
    },
  ];
}

// ───────────────────────────────────────────────────────────────────────
// 3. CAUSAL GRAPH (GET /risk-events/{id}/causal-graph)
// ───────────────────────────────────────────────────────────────────────

export async function getCausalGraph(risk_event_id = 1) {
  if (!USE_MOCK) {
    try {
      return await apiFetch(`/risk-events/${risk_event_id}/causal-graph`);
    } catch (err) {
      console.warn(`[API] getCausalGraph(${risk_event_id}) failed:`, err.message);
    }
  }

  await delay(300);
  return {
    nodes: [
      { id: 'weather_2026_03_14', label: 'Heavy Rainfall Event', type: 'WeatherEvent' },
      { id: 'blast_plan_b204', label: 'Blast Plan BP-BAL-01', type: 'BlastPlan' },
      { id: 'zone_b2', label: 'OreZone North Block', type: 'OreZone' },
      { id: 'equipment_ex201', label: 'Excavator EX-201', type: 'Equipment' },
      { id: 'risk_event_shortfall', label: 'Production Shortfall Risk', type: 'RiskEvent' },
    ],
    edges: [
      { source: 'weather_2026_03_14', target: 'blast_plan_b204', relationship: 'DELAYS' },
      { source: 'blast_plan_b204', target: 'zone_b2', relationship: 'AFFECTS' },
      { source: 'equipment_ex201', target: 'zone_b2', relationship: 'OPERATES_IN' },
      { source: 'zone_b2', target: 'risk_event_shortfall', relationship: 'CAUSES' },
    ],
  };
}

// ───────────────────────────────────────────────────────────────────────
// 4. DAY 2 APIs: Equipment & Production
// ───────────────────────────────────────────────────────────────────────

export async function postEquipmentStatus(id, { status, reason }) {
  const numId = Number(id) || 1;

  if (!USE_MOCK) {
    try {
      return await apiFetch(`/equipment/${numId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status, reason: reason || null }),
      });
    } catch (err) {
      console.warn('[API] postEquipmentStatus live failed:', err.message);
      if (!err.isNetworkError) throw err;
    }
  }

  await delay(500);
  const item = mockEquipment.find(e => e.id === numId);
  if (!item) throw new Error(`Equipment with ID ${id} not found`);

  item.status = status;
  item.status_reason = reason || null;
  return { ...item };
}

export async function postProduction({ site_id, date, actual_output, target_output }) {
  const numSiteId = SITE_MAP[site_id] || Number(site_id) || 1;
  const numActual = parseFloat(actual_output);
  const numTarget = parseFloat(target_output);

  if (!USE_MOCK) {
    try {
      return await apiFetch('/production', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          site_id: numSiteId,
          date,
          actual_output: numActual,
          target_output: numTarget,
        }),
      });
    } catch (err) {
      console.warn('[API] postProduction live failed:', err.message);
      if (!err.isNetworkError) throw err;
    }
  }

  await delay(550);
  if (numActual < 0) throw new Error('Actual output cannot be negative');

  const variance_pct = Math.round(((numActual - numTarget) / numTarget) * 10000) / 100;
  const newRec = {
    id: Date.now(),
    site_id: numSiteId,
    date,
    actual_output: numActual,
    target_output: numTarget,
    variance_pct,
  };
  if (!mockProductionHistory[numSiteId]) mockProductionHistory[numSiteId] = [];
  mockProductionHistory[numSiteId].push(newRec);
  return newRec;
}

export async function getProduction({ site_id, days = 30 } = {}) {
  const numSiteId = site_id ? (SITE_MAP[site_id] || Number(site_id)) : null;

  if (!USE_MOCK) {
    try {
      const q = new URLSearchParams();
      if (numSiteId) q.set('site_id', numSiteId);
      if (days) q.set('days', days);
      return await apiFetch(`/production?${q.toString()}`);
    } catch (err) {
      console.warn('[API] getProduction live failed, using mock:', err.message);
    }
  }

  await delay(400);
  if (numSiteId) {
    const recs = mockProductionHistory[numSiteId] || [];
    return [...recs].sort((a, b) => a.date.localeCompare(b.date)).slice(-days);
  }
  const all = Object.values(mockProductionHistory).flat();
  return all.sort((a, b) => a.date.localeCompare(b.date)).slice(-days);
}

export async function getEquipment(site_id = null) {
  const numId = site_id ? (SITE_MAP[site_id] || Number(site_id)) : null;

  if (!USE_MOCK) {
    try {
      const q = numId ? `?site_id=${numId}` : '';
      return await apiFetch(`/equipment${q}`);
    } catch (err) {
      console.warn('[API] getEquipment live failed:', err.message);
    }
  }

  await delay(200);
  if (numId) return mockEquipment.filter(e => e.site_id === numId);
  return [...mockEquipment];
}

export async function getRiskEvents({ site_id = null, resolved = null } = {}) {
  if (!USE_MOCK) {
    try {
      const q = new URLSearchParams();
      if (site_id) q.set('site_id', SITE_MAP[site_id] || site_id);
      if (resolved !== null) q.set('resolved', resolved);
      const res = await apiFetch(`/risk-events?${q.toString()}`);
      if (res && res.length > 0) return res;
    } catch (err) {
      console.warn('[API] getRiskEvents live failed:', err.message);
    }
  }

  await delay(300);
  let res = [...mockRiskEvents];
  if (site_id) {
    const numId = SITE_MAP[site_id] || Number(site_id);
    res = res.filter(r => r.site_id === numId);
  }
  if (resolved !== null) {
    res = res.filter(r => r.resolved === resolved);
  }
  return res;
}
