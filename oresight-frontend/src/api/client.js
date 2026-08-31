// ─────────────────────────────────────────────────────────────────────
// OreSight API Client
// Single constant USE_MOCK toggles between simulated fake responses and
// real FastAPI calls at http://localhost:8000.
// ─────────────────────────────────────────────────────────────────────

export const USE_MOCK = true;

const BASE_URL = 'http://localhost:8000';

// Site ID mapping (supports numeric 1,2,3 or string 'balaghat','nagpur','bhandara')
export const SITE_MAP = {
  balaghat: 1,
  nagpur: 2,
  bhandara: 3,
  1: 1,
  2: 2,
  3: 3,
};

// Seeded mock data stores for offline simulation
let mockEquipment = [
  { id: 1, site_id: 1, site_name: 'Balaghat', name: 'Excavator EX-201', equipment_type: 'excavator', status: 'down', status_reason: 'Hydraulic pump failure' },
  { id: 2, site_id: 1, site_name: 'Balaghat', name: 'Rock Drill DR-101', equipment_type: 'drill', status: 'up', status_reason: null },
  { id: 3, site_id: 1, site_name: 'Balaghat', name: 'Haul Truck HT-301', equipment_type: 'haul_truck', status: 'up', status_reason: null },
  { id: 4, site_id: 1, site_name: 'Balaghat', name: 'Jaw Crusher CR-401', equipment_type: 'crusher', status: 'up', status_reason: null },
  { id: 5, site_id: 1, site_name: 'Balaghat', name: 'Wheel Loader LD-501', equipment_type: 'loader', status: 'up', status_reason: null },
  { id: 6, site_id: 2, site_name: 'Nagpur', name: 'Excavator EX-202', equipment_type: 'excavator', status: 'up', status_reason: null },
  { id: 7, site_id: 2, site_name: 'Nagpur', name: 'Rock Drill DR-102', equipment_type: 'drill', status: 'up', status_reason: null },
  { id: 8, site_id: 2, site_name: 'Nagpur', name: 'Haul Truck HT-302', equipment_type: 'haul_truck', status: 'down', status_reason: 'Engine overheating' },
  { id: 9, site_id: 2, site_name: 'Nagpur', name: 'Jaw Crusher CR-402', equipment_type: 'crusher', status: 'up', status_reason: null },
  { id: 10, site_id: 2, site_name: 'Nagpur', name: 'Wheel Loader LD-502', equipment_type: 'loader', status: 'up', status_reason: null },
  { id: 11, site_id: 3, site_name: 'Bhandara', name: 'Excavator EX-203', equipment_type: 'excavator', status: 'up', status_reason: null },
  { id: 12, site_id: 3, site_name: 'Bhandara', name: 'Rock Drill DR-103', equipment_type: 'drill', status: 'up', status_reason: null },
  { id: 13, site_id: 3, site_name: 'Bhandara', name: 'Haul Truck HT-303', equipment_type: 'haul_truck', status: 'up', status_reason: null },
  { id: 14, site_id: 3, site_name: 'Bhandara', name: 'Jaw Crusher CR-403', equipment_type: 'crusher', status: 'up', status_reason: null },
  { id: 15, site_id: 3, site_name: 'Bhandara', name: 'Wheel Loader LD-503', equipment_type: 'loader', status: 'up', status_reason: null },
];

function generateMockProduction(siteId, days = 30) {
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

const delay = (ms = 600) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * 1. POST Equipment Status
 * POST /equipment/{id}/status
 */
export async function postEquipmentStatus(id, { status, reason }) {
  if (USE_MOCK) {
    await delay(600);

    // Simulate failure if status is missing or invalid
    if (!status || !['up', 'down'].includes(status)) {
      const error = new Error("Invalid status: must be 'up' or 'down'");
      error.status = 422;
      throw error;
    }

    const numId = Number(id) || 1;
    const item = mockEquipment.find(e => e.id === numId);
    if (!item) {
      const error = new Error(`Equipment with ID ${id} not found`);
      error.status = 404;
      throw error;
    }

    item.status = status;
    item.status_reason = reason || null;
    item.last_status_change = new Date().toISOString();

    return {
      id: item.id,
      site_id: item.site_id,
      site_name: item.site_name,
      name: item.name,
      equipment_type: item.equipment_type,
      status: item.status,
      last_status_change: item.last_status_change,
      status_reason: item.status_reason,
    };
  }

  // Real backend call
  try {
    const res = await fetch(`${BASE_URL}/equipment/${id}/status`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ status, reason: reason || null }),
    });

    if (!res.ok) {
      let detail = `Server responded with ${res.status}`;
      try {
        const json = await res.json();
        if (json.detail) detail = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
      } catch { /* ignored */ }
      const err = new Error(detail);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(`Cannot connect to backend at ${BASE_URL}. Ensure FastAPI is running.`);
    }
    throw err;
  }
}

/**
 * 2. POST Daily Production
 * POST /production
 */
export async function postProduction({ site_id, date, actual_output, target_output }) {
  const numSiteId = SITE_MAP[site_id] || Number(site_id) || 1;
  const numActual = parseFloat(actual_output);
  const numTarget = parseFloat(target_output);

  if (USE_MOCK) {
    await delay(650);

    // Simulate failure test path: negative actual output throws error
    if (numActual < 0) {
      const error = new Error('Actual output cannot be negative');
      error.status = 422;
      throw error;
    }

    if (!date) {
      const error = new Error('Date is required');
      error.status = 422;
      throw error;
    }

    if (numTarget <= 0 || isNaN(numTarget)) {
      const error = new Error('Target output must be greater than 0');
      error.status = 422;
      throw error;
    }

    // Check duplicate date in mock store
    const siteRecords = mockProductionHistory[numSiteId] || [];
    const exists = siteRecords.find(r => r.date === date);
    if (exists) {
      const error = new Error(`A production record for site ${numSiteId} on ${date} already exists`);
      error.status = 409;
      error.error_code = 'CONFLICT';
      throw error;
    }

    const variance_pct = Math.round(((numActual - numTarget) / numTarget) * 10000) / 100;
    const newRecord = {
      id: Date.now(),
      site_id: numSiteId,
      date,
      actual_output: numActual,
      target_output: numTarget,
      variance_pct,
    };

    if (!mockProductionHistory[numSiteId]) mockProductionHistory[numSiteId] = [];
    mockProductionHistory[numSiteId].push(newRecord);
    return newRecord;
  }

  // Real backend call
  try {
    const res = await fetch(`${BASE_URL}/production`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        site_id: numSiteId,
        date,
        actual_output: numActual,
        target_output: numTarget,
      }),
    });

    if (!res.ok) {
      let detail = `Server responded with ${res.status}`;
      try {
        const json = await res.json();
        if (json.detail) detail = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
      } catch { /* ignored */ }
      const err = new Error(detail);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(`Cannot connect to backend at ${BASE_URL}. Ensure FastAPI is running.`);
    }
    throw err;
  }
}

/**
 * 3. GET Production History
 * GET /production?site_id={site_id}&days={days}
 */
export async function getProduction({ site_id, days = 30 } = {}) {
  const numSiteId = site_id ? (SITE_MAP[site_id] || Number(site_id)) : null;

  if (USE_MOCK) {
    await delay(500);

    if (numSiteId) {
      const records = mockProductionHistory[numSiteId] || [];
      return [...records]
        .sort((a, b) => a.date.localeCompare(b.date))
        .slice(-days);
    }

    // Combined all sites
    const all = Object.values(mockProductionHistory).flat();
    return all.sort((a, b) => a.date.localeCompare(b.date)).slice(-days);
  }

  // Real backend call
  try {
    const url = new URL(`${BASE_URL}/production`);
    if (numSiteId) url.searchParams.set('site_id', numSiteId);
    if (days) url.searchParams.set('days', days);

    const res = await fetch(url.toString(), {
      headers: { 'Accept': 'application/json' },
    });

    if (!res.ok) {
      let detail = `Server responded with ${res.status}`;
      try {
        const json = await res.json();
        if (json.detail) detail = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
      } catch { /* ignored */ }
      const err = new Error(detail);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(`Cannot connect to backend at ${BASE_URL}. Ensure FastAPI is running.`);
    }
    throw err;
  }
}

/**
 * Helper to fetch equipment list for dropdowns
 */
export async function getEquipment(site_id = null) {
  if (USE_MOCK) {
    await delay(200);
    const numId = site_id ? (SITE_MAP[site_id] || Number(site_id)) : null;
    if (numId) return mockEquipment.filter(e => e.site_id === numId);
    return [...mockEquipment];
  }

  try {
    const url = new URL(`${BASE_URL}/equipment`);
    if (site_id) {
      const numId = SITE_MAP[site_id] || Number(site_id);
      url.searchParams.set('site_id', numId);
    }
    const res = await fetch(url.toString(), {
      headers: { 'Accept': 'application/json' },
    });
    if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error(`Cannot connect to backend at ${BASE_URL}.`);
    }
    throw err;
  }
}
