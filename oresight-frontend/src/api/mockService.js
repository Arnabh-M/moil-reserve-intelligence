// ─────────────────────────────────────────────────────────────────────
// Mock Service — Simulates live FastAPI backend based on API_CONTRACT.md
// Handles simulated network delays, in-memory mutations, and conflict errors.
// ─────────────────────────────────────────────────────────────────────

import { equipment as initialEquipment, sites as initialSites, productionHistory } from '../data/mockData';

// Helper for site ID normalisation (supports numeric 1,2,3 or string 'balaghat','nagpur','bhandara')
export const SITE_ID_MAP = {
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

// In-memory mutable state initialized from seeded dataset
let mockEquipmentState = [
  { id: 1, site_id: 1, site_name: 'Balaghat', name: 'Excavator EX-201', equipment_type: 'excavator', status: 'down', last_status_change: '2026-08-30T08:20:04.312Z', status_reason: 'Hydraulic pump failure - spare part on order, ETA 3 days', code: 'eq_bal_01' },
  { id: 2, site_id: 1, site_name: 'Balaghat', name: 'Rock Drill DR-101', equipment_type: 'drill', status: 'up', last_status_change: '2026-08-31T08:49:20.570Z', status_reason: null, code: 'eq_bal_02' },
  { id: 3, site_id: 1, site_name: 'Balaghat', name: 'Haul Truck HT-301', equipment_type: 'haul_truck', status: 'up', last_status_change: '2026-07-12T08:20:04.312Z', status_reason: null, code: 'eq_bal_03' },
  { id: 4, site_id: 1, site_name: 'Balaghat', name: 'Jaw Crusher CR-401', equipment_type: 'crusher', status: 'up', last_status_change: '2026-06-30T08:20:04.312Z', status_reason: null, code: 'eq_bal_04' },
  { id: 5, site_id: 1, site_name: 'Balaghat', name: 'Wheel Loader LD-501', equipment_type: 'loader', status: 'up', last_status_change: '2026-06-02T08:20:04.312Z', status_reason: null, code: 'eq_bal_05' },

  { id: 6, site_id: 2, site_name: 'Nagpur', name: 'Excavator EX-202', equipment_type: 'excavator', status: 'up', last_status_change: '2026-08-31T09:12:20.512Z', status_reason: null, code: 'eq_nag_01' },
  { id: 7, site_id: 2, site_name: 'Nagpur', name: 'Rock Drill DR-102', equipment_type: 'drill', status: 'up', last_status_change: '2026-07-25T08:20:04.441Z', status_reason: null, code: 'eq_nag_02' },
  { id: 8, site_id: 2, site_name: 'Nagpur', name: 'Haul Truck HT-302', equipment_type: 'haul_truck', status: 'down', last_status_change: '2026-08-30T08:20:04.441Z', status_reason: 'Engine overheating - pulled for inspection', code: 'eq_nag_03' },
  { id: 9, site_id: 2, site_name: 'Nagpur', name: 'Jaw Crusher CR-402', equipment_type: 'crusher', status: 'up', last_status_change: '2026-06-22T08:20:04.441Z', status_reason: null, code: 'eq_nag_04' },
  { id: 10, site_id: 2, site_name: 'Nagpur', name: 'Wheel Loader LD-502', equipment_type: 'loader', status: 'up', last_status_change: '2026-06-18T08:20:04.441Z', status_reason: null, code: 'eq_nag_05' },

  { id: 11, site_id: 3, site_name: 'Bhandara', name: 'Excavator EX-203', equipment_type: 'excavator', status: 'up', last_status_change: '2026-06-26T08:20:04.553Z', status_reason: null, code: 'eq_bhd_01' },
  { id: 12, site_id: 3, site_name: 'Bhandara', name: 'Rock Drill DR-103', equipment_type: 'drill', status: 'up', last_status_change: '2026-06-13T08:20:04.553Z', status_reason: null, code: 'eq_bhd_02' },
  { id: 13, site_id: 3, site_name: 'Bhandara', name: 'Haul Truck HT-303', equipment_type: 'haul_truck', status: 'up', last_status_change: '2026-06-03T08:20:04.553Z', status_reason: null, code: 'eq_bhd_03' },
  { id: 14, site_id: 3, site_name: 'Bhandara', name: 'Jaw Crusher CR-403', equipment_type: 'crusher', status: 'up', last_status_change: '2026-06-02T08:20:04.553Z', status_reason: null, code: 'eq_bhd_04' },
  { id: 15, site_id: 3, site_name: 'Bhandara', name: 'Wheel Loader LD-503', equipment_type: 'loader', status: 'up', last_status_change: '2026-06-07T08:20:04.553Z', status_reason: null, code: 'eq_bhd_05' },
];

let nextProductionId = 200;
let mockProductionRecords = productionHistory.map((p, idx) => {
  const numericSiteId = SITE_ID_MAP[p.site_id] || 1;
  const variance = p.target_output ? Math.round(((p.actual_output - p.target_output) / p.target_output) * 10000) / 100 : 0;
  return {
    id: idx + 1,
    site_id: numericSiteId,
    date: p.date,
    actual_output: p.actual_output,
    target_output: p.target_output,
    variance_pct: variance,
  };
});

function delay(ms = 300) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Mock API Methods ───────────────────────────────────────────────────

export async function mockListEquipment(siteId = null) {
  await delay(200);
  if (siteId !== null && siteId !== undefined) {
    const numId = SITE_ID_MAP[siteId] || siteId;
    return mockEquipmentState.filter(e => e.site_id === numId);
  }
  return [...mockEquipmentState];
}

export async function mockUpdateEquipmentStatus(equipmentId, payload) {
  await delay(350);
  const { status, reason } = payload;
  if (!['up', 'down'].includes(status)) {
    const err = new Error("Status must be 'up' or 'down'");
    err.status = 422;
    throw err;
  }

  // Find by numeric ID or code
  const index = mockEquipmentState.findIndex(
    e => e.id === Number(equipmentId) || e.code === String(equipmentId)
  );

  if (index === -1) {
    const err = new Error(`Equipment with ID ${equipmentId} not found`);
    err.status = 404;
    throw err;
  }

  const updated = {
    ...mockEquipmentState[index],
    status,
    status_reason: reason || null,
    last_status_change: new Date().toISOString(),
  };

  mockEquipmentState[index] = updated;
  return { ...updated };
}

export async function mockListProductionRecords({ site_id = null, days = 30 } = {}) {
  await delay(250);
  let records = [...mockProductionRecords];

  if (site_id !== null && site_id !== undefined && site_id !== 'all') {
    const numId = SITE_ID_MAP[site_id] || Number(site_id);
    records = records.filter(r => r.site_id === numId);
  }

  // Filter trailing days
  if (days) {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - days);
    const cutoffStr = cutoff.toISOString().split('T')[0];
    records = records.filter(r => r.date >= cutoffStr);
  }

  return records.sort((a, b) => a.date.localeCompare(b.date));
}

export async function mockCreateProductionRecord(payload) {
  await delay(400);
  const { site_id, date, actual_output, target_output } = payload;

  const numSiteId = SITE_ID_MAP[site_id] || Number(site_id);
  if (!numSiteId || isNaN(numSiteId)) {
    const err = new Error('Invalid site_id');
    err.status = 422;
    throw err;
  }

  if (!date || isNaN(new Date(date).getTime())) {
    const err = new Error('Invalid date format');
    err.status = 422;
    throw err;
  }

  const numActual = parseFloat(actual_output);
  const numTarget = parseFloat(target_output);

  if (isNaN(numActual) || numActual < 0) {
    const err = new Error('Actual output must be a positive number');
    err.status = 422;
    throw err;
  }

  if (isNaN(numTarget) || numTarget <= 0) {
    const err = new Error('Target output must be a positive number greater than 0');
    err.status = 422;
    throw err;
  }

  // Check 409 Conflict (duplicate record for same site + date)
  const existing = mockProductionRecords.find(
    r => r.site_id === numSiteId && r.date === date
  );

  if (existing) {
    const err = new Error(`A production record for site ${numSiteId} on ${date} already exists`);
    err.status = 409;
    err.error_code = 'CONFLICT';
    throw err;
  }

  const variance_pct = Math.round(((numActual - numTarget) / numTarget) * 10000) / 100;

  const newRecord = {
    id: ++nextProductionId,
    site_id: numSiteId,
    date,
    actual_output: numActual,
    target_output: numTarget,
    variance_pct,
  };

  mockProductionRecords.push(newRecord);
  return { ...newRecord };
}

export async function mockListSites() {
  await delay(150);
  return [
    {
      id: 1,
      name: 'Balaghat',
      belt_name: 'Balaghat Manganese Belt',
      district: 'Balaghat',
      state: 'Madhya Pradesh',
      centroid_lat: 21.8,
      centroid_lon: 80.19,
      active_risk_count: 1,
      avg_reserve_confidence: 0.67,
    },
    {
      id: 2,
      name: 'Nagpur',
      belt_name: 'Nagpur-Bhandara Manganese Belt',
      district: 'Nagpur',
      state: 'Maharashtra',
      centroid_lat: 21.15,
      centroid_lon: 79.09,
      active_risk_count: 1,
      avg_reserve_confidence: 0.673,
    },
    {
      id: 3,
      name: 'Bhandara',
      belt_name: 'Nagpur-Bhandara Manganese Belt',
      district: 'Bhandara',
      state: 'Maharashtra',
      centroid_lat: 21.17,
      centroid_lon: 79.65,
      active_risk_count: 2,
      avg_reserve_confidence: 0.675,
    },
  ];
}
