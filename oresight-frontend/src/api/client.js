import { mockData, findSite } from './mockData';

// Live API is the default path; mock is the offline/venue-wifi fallback,
// opted into explicitly with VITE_USE_MOCK=true when the backend isn't reachable.
const useMock = String(import.meta.env.VITE_USE_MOCK ?? 'false') !== 'false';
const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const wait = (value, delay = 160) => new Promise((resolve) => setTimeout(() => resolve(value), delay));

function contractError(status, body) {
  // A 422's `detail` is a list of readable per-field strings (see the
  // backend's RequestValidationError handler) — join them into one message
  // rather than letting `new Error([...])` coerce the array to
  // "[object Object]"-style garbage.
  const rawDetail = body?.detail || body?.message || `Request failed (${status})`;
  const detail = Array.isArray(rawDetail) ? rawDetail.join('; ') : rawDetail;
  const error = new Error(detail);
  error.status = status;
  error.detail = detail;
  error.error_code = body?.error_code || `HTTP_${status}`;
  return error;
}

async function request(path, options = {}) {
  const response = await fetch(`${baseUrl}${path}`, { credentials: 'include', ...options });
  let body = null;
  try { body = await response.json(); } catch { /* empty error response */ }
  if (!response.ok) throw contractError(response.status, body);
  return body;
}

const query = (params) => {
  const values = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '');
  return values.length ? `?${new URLSearchParams(values).toString()}` : '';
};
const bySite = (records, siteId) => records.filter((record) => Number(record.site_id) === Number(siteId));
const delay = (value) => useMock ? wait(value) : value;

// Blast-event mock rows live here rather than in mockData.js so the mock
// fallback stays functional without editing the shared fixture module.
const mockBlastEvents = [
  { id: 9001, site_id: 1, reserve_zone_id: null, planned_date: '2026-09-04', actual_date: null, status: 'delayed', delay_reason: 'permit_pending', expected_yield_tonnes: 1800, actual_yield_tonnes: null, notes: 'District explosives permit still with the controller.', created_at: '2026-09-01T09:00:00Z', updated_at: '2026-09-04T11:00:00Z' },
  { id: 9002, site_id: 1, reserve_zone_id: null, planned_date: '2026-09-02', actual_date: '2026-09-02', status: 'completed', delay_reason: null, expected_yield_tonnes: 1500, actual_yield_tonnes: 1462, notes: null, created_at: '2026-08-30T09:00:00Z', updated_at: '2026-09-02T17:00:00Z' },
  { id: 9003, site_id: 2, reserve_zone_id: null, planned_date: '2026-08-29', actual_date: null, status: 'cancelled', delay_reason: 'weather_hold', expected_yield_tonnes: 1200, actual_yield_tonnes: null, notes: 'Monsoon cell over the bench all shift.', created_at: '2026-08-26T09:00:00Z', updated_at: '2026-08-29T08:00:00Z' },
];
const mockBlastSummary = [
  { delay_reason: 'permit_pending', event_count: 1, expected_yield_tonnes: 1800, actual_yield_tonnes: 0, tonnes_lost: 1800 },
  { delay_reason: 'weather_hold', event_count: 1, expected_yield_tonnes: 1200, actual_yield_tonnes: 0, tonnes_lost: 1200 },
];

// Equipment status-change history, mirroring backend `equipment_status_log`
// (Field Intake Hardening Phase 4). Lives here for the same reason as the
// blast-event mocks above — newest-first via unshift, never re-sorted.
const mockEquipmentStatusLog = [];
const EQUIPMENT_FLAP_WINDOW_HOURS = 24;
const EQUIPMENT_FLAP_THRESHOLD = 4;

// Shift-plan rows persist in-memory for the mock fallback, same as mockBlastEvents.
const mockShiftPlan = [];

const SEVERITY_RANK = { critical: 4, high: 3, medium: 2, low: 1 };

// Picking "the" risk event for a site used to just take risks[0] (API insertion
// order), which for Nagpur meant the Drill NAG-1 event (no Neo4j graph yet,
// renders as the flat postgres_fallback) instead of the Haul Truck HT-302 event
// that /demo/scenarios and the whole equipment-down demo path are built around.
// Prefer whichever risk the demo-scenarios endpoint names for this site; only
// fall back to the highest-severity unresolved event when no demo scenario
// applies (a real site with no scripted scenario, or the endpoint unavailable).
function pickPrimaryRisk(risks, demoScenarios, siteId) {
  if (!risks.length) return null;
  const scenarioMatch = demoScenarios.find((scenario) => scenario.available && Number(scenario.site_id) === Number(siteId) && risks.some((risk) => Number(risk.id) === Number(scenario.risk_event_id)));
  if (scenarioMatch) return risks.find((risk) => Number(risk.id) === Number(scenarioMatch.risk_event_id));
  return [...risks].sort((a, b) => (SEVERITY_RANK[b.severity] || 0) - (SEVERITY_RANK[a.severity] || 0) || (b.score || 0) - (a.score || 0))[0];
}

export const api = {
  isMock: useMock,
  async getKpiSummary() { return useMock ? delay(mockData.kpi) : request('/kpi/summary'); },
  async getSites() { return useMock ? delay(mockData.sites) : request('/sites'); },
  async getSite(id) { return useMock ? delay(findSite(id)) : request(`/sites/${Number(id)}`); },
  async getEquipment(siteId) { return useMock ? delay(bySite(mockData.equipment, siteId)) : request(`/equipment${query({ site_id: Number(siteId) })}`); },
  async getProduction(siteId, days = 30) { return useMock ? delay(bySite(mockData.production, siteId)) : request(`/production${query({ site_id: Number(siteId), days })}`); },
  async getRiskEvents(siteId, resolved) { return useMock ? delay(mockData.riskEvents.filter((risk) => (siteId === undefined || Number(risk.site_id) === Number(siteId)) && (resolved === undefined || risk.resolved === resolved))) : request(`/risk-events${query({ site_id: siteId === undefined ? undefined : Number(siteId), resolved })}`); },
  async getReserveZones(siteId) {
    if (useMock) return delay({ type: 'FeatureCollection', features: mockData.reserveZones.filter((zone) => siteId === undefined || zone.properties.site_id === Number(siteId)) });
    return request(`/reserve-zones${query({ site_id: siteId === undefined ? undefined : Number(siteId) })}`);
  },
  async getCausalGraph(riskId) { return useMock ? delay(mockData.graph) : request(`/risk-events/${Number(riskId)}/causal-graph`); },
  // Soft-fail to [] rather than reject: this only affects which risk event's
  // graph is shown "primary" for a site (see pickPrimaryRisk) -- the rest of
  // the site workspace shouldn't break if this endpoint is ever unavailable.
  async getDemoScenarios() { if (useMock) return delay([]); try { return await request('/demo/scenarios'); } catch { return []; } },
  // Single source of truth for "which risk event represents this site", so the
  // Site Intelligence graph tab (via getSiteWorkspace) and the Map zone panel
  // (ZoneDetailPanel) can't drift apart on which causal graph they show. Uses
  // pickPrimaryRisk over the site's unresolved events (demo-scripted event
  // first, else highest-severity), soft-failing to [] if /demo/scenarios is
  // down. If every event for the site is resolved, falls back to the most
  // recent one so a graph still renders instead of an empty panel.
  async getSitePrimaryRisk(siteId) {
    const id = Number(siteId);
    const [unresolved, demoScenarios] = await Promise.all([this.getRiskEvents(id, false), this.getDemoScenarios()]);
    const primary = pickPrimaryRisk(unresolved, demoScenarios, id);
    if (primary) return primary;
    const all = await this.getRiskEvents(id);
    return all[0] || null;
  },
  async getRecommendations(riskId) {
    if (riskId !== undefined && riskId !== null) return useMock ? delay(mockData.recommendations.filter((item) => Number(item.risk_event_id) === Number(riskId))) : request(`/recommendations${query({ risk_event_id: Number(riskId) })}`);
    const events = await this.getRiskEvents(undefined, false);
    const batches = [];
    for (let index = 0; index < events.length; index += 8) batches.push(events.slice(index, index + 8));
    const results = [];
    for (const batch of batches) results.push(...(await Promise.all(batch.map((event) => this.getRecommendations(event.id)))));
    return results.flat();
  },
  async addToShiftPlan(payload) {
    const body = {
      risk_event_id: Number(payload.risk_event_id),
      option_type: payload.option_type,
      description: payload.description,
      target_id: payload.target_id ?? null,
      projected_impact: Number(payload.projected_impact),
      confidence: Number(payload.confidence),
    };
    if (useMock) { const row = { id: Date.now(), site_id: null, created_at: new Date().toISOString(), ...body }; mockShiftPlan.unshift(row); return delay(row); }
    return request('/shift-plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  },
  async getShiftPlan(siteId) {
    if (useMock) return delay(mockShiftPlan.filter((row) => siteId === undefined || Number(row.site_id) === Number(siteId)));
    return request(`/shift-plan${query({ site_id: siteId === undefined ? undefined : Number(siteId) })}`);
  },
  async simulate({ scenario_type, site_id, duration_days, severity, conditions, site_context, current_reserve_confidence, recent_production_variance }) {
    const payload = {
      scenario_type,
      site_id: Number(site_id),
      duration_days: Number(duration_days),
      ...(severity != null ? { severity: Number(severity) } : {}),
      ...(conditions ? { conditions } : {}),
      ...(site_context ? { site_context } : {}),
      ...(current_reserve_confidence != null ? { current_reserve_confidence: Number(current_reserve_confidence) } : {}),
      ...(recent_production_variance != null ? { recent_production_variance: Number(recent_production_variance) } : {}),
    };
    if (useMock) {
      const ranges = {
        equipment_down: { severity_min_pct: 0, severity_max_pct: 5.3, duration_min_days: 0.1, duration_max_days: 1.9 },
        delay_blasting: { severity_min_pct: 0.4, severity_max_pct: 34.9, duration_min_days: 5, duration_max_days: 10 },
        rainfall_event: { severity_min_pct: 14.6, severity_max_pct: 100.0, duration_min_days: 1, duration_max_days: 30 },
      };
      const items = conditions && conditions.length > 0 ? conditions : [{ type: scenario_type, duration: duration_days, severity }];
      let anyOOD = false;
      const conditions_ood = items.map((c, idx) => {
        const r = ranges[c.type] || { severity_min_pct: 0, severity_max_pct: 100, duration_min_days: 1, duration_max_days: 30 };
        const sevOOD = c.severity != null && (c.severity < r.severity_min_pct || c.severity > r.severity_max_pct);
        const durOOD = c.duration != null && (c.duration < r.duration_min_days || c.duration > r.duration_max_days);
        const ood = Boolean(sevOOD || durOOD);
        if (ood) anyOOD = true;
        const warnings = [];
        if (sevOOD) warnings.push(`Severity ${c.severity}% is outside validated training range (${r.severity_min_pct}–${r.severity_max_pct}%).`);
        if (durOOD) warnings.push(`Duration ${c.duration}d is outside validated training range (${r.duration_min_days}–${r.duration_max_days} days).`);
        return {
          index: idx,
          scenario_type: c.type,
          out_of_distribution: ood,
          severity_out_of_distribution: Boolean(sevOOD),
          duration_out_of_distribution: Boolean(durOOD),
          severity_value: c.severity,
          duration_value: c.duration,
          severity_valid_range: [r.severity_min_pct, r.severity_max_pct],
          duration_valid_range: [r.duration_min_days, r.duration_max_days],
          warnings,
        };
      });
      const oodWarning = anyOOD
        ? 'One or more condition parameters exceed the range the model was validated on. Treat results with extra caution.'
        : null;

      return delay({
        ...mockData.simulation,
        scenario_type,
        site_id: Number(site_id),
        duration_days: Number(duration_days),
        out_of_distribution: anyOOD,
        conditions_ood,
        out_of_distribution_warning: oodWarning,
      });
    }
    return request('/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  },

  async uploadReport(file) {
    if (useMock) return delay({ ...mockData.upload, filename: file?.name || mockData.upload.filename });
    const form = new FormData();
    form.append('file', file);
    return request('/reports/upload', { method: 'POST', body: form });
  },
  // `q` is stripped by query() when empty, but GET /site-notes/search requires it (min_length=1).
  // The backend ranks by cosine distance with no relevance threshold, so any non-empty term
  // returns that site's `limit` most recent-ranked notes, which is what this call wants.
  async getSiteNotes(siteId) { return useMock ? delay(bySite(mockData.notes, siteId)) : request(`/site-notes/search${query({ q: 'site', site_id: Number(siteId), limit: 5 })}`); },
  async searchSiteNotes(search, siteId) { return useMock ? delay(bySite(mockData.notes, siteId).filter((note) => note.text.toLowerCase().includes(search.toLowerCase()))) : request(`/site-notes/search${query({ q: search, site_id: siteId === undefined ? undefined : Number(siteId) })}`); },
  async createSiteNote(payload) {
    if (useMock) { const note = { id: Date.now(), site_id: Number(payload.site_id), text: payload.text, created_at: '2026-09-05T15:20:00Z', relevance: 1 }; mockData.notes.unshift(note); return delay(note); }
    return request('/site-notes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ site_id: Number(payload.site_id), text: payload.text }) });
  },
  async updateEquipmentStatus(id, payload) {
    const source = payload.source || 'manual';
    if (useMock) {
      const item = mockData.equipment.find((equipment) => equipment.id === Number(id));
      const oldStatus = item?.status ?? null;
      const changedAt = new Date().toISOString();
      if (item) Object.assign(item, { status: payload.status, status_reason: payload.status_reason || item.status_reason, last_status_change: changedAt });
      mockEquipmentStatusLog.unshift({
        id: Date.now(),
        equipment_id: Number(id),
        site_id: item?.site_id ?? null,
        old_status: oldStatus,
        new_status: payload.status,
        reason: payload.status_reason || null,
        changed_by: 'system',
        changed_at: changedAt,
        source,
      });
      const windowStart = Date.now() - EQUIPMENT_FLAP_WINDOW_HOURS * 3600 * 1000;
      const recentCount = mockEquipmentStatusLog.filter((row) => row.equipment_id === Number(id) && new Date(row.changed_at).getTime() >= windowStart).length;
      const flapping = recentCount > EQUIPMENT_FLAP_THRESHOLD;
      if (item) item.flapping = flapping;
      return delay(item ? { ...item, flapping } : { flapping });
    }
    return request(`/equipment/${Number(id)}/status`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: payload.status, reason: payload.status_reason || null, source }) });
  },
  async getEquipmentHistory(id, { limit = 50, before } = {}) {
    if (useMock) {
      let rows = mockEquipmentStatusLog.filter((row) => row.equipment_id === Number(id));
      if (before) rows = rows.filter((row) => new Date(row.changed_at).getTime() < new Date(before).getTime());
      const page = rows.slice(0, limit);
      const nextCursor = page.length === limit ? page[page.length - 1].changed_at : null;
      return delay({ items: page, next_cursor: nextCursor });
    }
    return request(`/equipment/${Number(id)}/history${query({ limit, before })}`);
  },
  async getEquipmentSiteHistory({ site_id, since, limit = 100 } = {}) {
    if (useMock) {
      let rows = mockEquipmentStatusLog;
      if (site_id !== undefined) rows = rows.filter((row) => Number(row.site_id) === Number(site_id));
      if (since) rows = rows.filter((row) => new Date(row.changed_at).getTime() >= new Date(since).getTime());
      return delay(rows.slice(0, limit));
    }
    return request(`/equipment/history${query({ site_id, since, limit })}`);
  },
  async createProduction(payload) {
    const body = {
      site_id: Number(payload.site_id),
      date: payload.date,
      shift: payload.shift || 'general',
      actual_output: Number(payload.actual_output),
      target_output: Number(payload.target_output),
      operating_hours: payload.operating_hours === '' || payload.operating_hours === undefined ? null : Number(payload.operating_hours),
      downtime_hours: payload.downtime_hours === '' || payload.downtime_hours === undefined ? null : Number(payload.downtime_hours),
      material_processed: payload.material_processed === '' || payload.material_processed === undefined ? null : Number(payload.material_processed),
      quality_grade: payload.quality_grade === '' || payload.quality_grade === undefined ? null : Number(payload.quality_grade),
      shortfall_reasons: payload.shortfall_reasons || [],
      shortfall_other_note: payload.shortfall_other_note || null,
    };
    if (useMock) {
      if (body.actual_output < 0 || body.target_output <= 0) throw contractError(422, { detail: 'Output must be non-negative and target must be greater than zero.', error_code: 'VALIDATION_ERROR' });
      if (body.operating_hours !== null && body.downtime_hours !== null && body.operating_hours + body.downtime_hours > 24) throw contractError(422, { detail: 'operating_hours + downtime_hours must not exceed 24.', error_code: 'VALIDATION_ERROR' });
      const variancePct = Number((((body.actual_output - body.target_output) / body.target_output) * 100).toFixed(1));
      const varianceClass = variancePct >= -3 ? 'on_target' : variancePct >= -12 ? 'slightly_below' : 'significantly_below';
      if (varianceClass === 'significantly_below' && body.shortfall_reasons.length === 0) throw contractError(422, { detail: 'shortfall_reasons must include at least one reason when significantly below target.', error_code: 'VALIDATION_ERROR' });
      if (body.shortfall_reasons.includes('other') && !body.shortfall_other_note) throw contractError(422, { detail: "shortfall_other_note is required when shortfall_reasons includes 'other'.", error_code: 'VALIDATION_ERROR' });
      if (mockData.production.some((row) => row.site_id === body.site_id && row.date === body.date && (row.shift || 'general') === body.shift)) throw contractError(409, { detail: 'A production record already exists for this site, date, and shift.', error_code: 'CONFLICT' });
      const now = new Date().toISOString();
      const row = { id: Date.now(), ...body, variance_pct: variancePct, variance_class: varianceClass, created_at: now, updated_at: null, created_by: 'system', updated_by: null };
      mockData.production.unshift(row);
      return delay(row);
    }
    return request('/production', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  },
  async updateProduction(id, payload) {
    const body = {};
    for (const key of ['actual_output', 'target_output', 'operating_hours', 'downtime_hours', 'material_processed', 'quality_grade', 'shortfall_reasons', 'shortfall_other_note']) {
      if (payload[key] !== undefined) body[key] = payload[key] === '' ? null : (['shortfall_reasons', 'shortfall_other_note'].includes(key) ? payload[key] : Number(payload[key]));
    }
    if (useMock) {
      const row = mockData.production.find((item) => item.id === Number(id));
      if (!row) throw contractError(404, { detail: `Production record ${id} not found`, error_code: 'NOT_FOUND' });
      Object.assign(row, body, { updated_at: new Date().toISOString(), updated_by: 'system' });
      const variancePct = row.target_output ? Number((((row.actual_output - row.target_output) / row.target_output) * 100).toFixed(1)) : null;
      row.variance_pct = variancePct;
      row.variance_class = variancePct === null ? null : variancePct >= -3 ? 'on_target' : variancePct >= -12 ? 'slightly_below' : 'significantly_below';
      return delay(row);
    }
    return request(`/production/${Number(id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  },
  async getShortfallReasons() {
    if (useMock) return delay(mockData.shortfallReasons);
    return request('/production/shortfall-reasons');
  },
  async getProductionThresholds() {
    if (useMock) return delay(mockData.productionThresholds);
    return request('/production/thresholds');
  },
  async listBlastEvents({ site_id, status } = {}) {
    if (useMock) return delay(mockBlastEvents.filter((row) => (site_id === undefined || row.site_id === Number(site_id)) && (!status || row.status === status)));
    return request(`/blast-events${query({ site_id: site_id === undefined ? undefined : Number(site_id), status })}`);
  },
  async createBlastEvent(payload) {
    const body = { site_id: Number(payload.site_id), reserve_zone_id: payload.reserve_zone_id ? Number(payload.reserve_zone_id) : null, planned_date: payload.planned_date, expected_yield_tonnes: Number(payload.expected_yield_tonnes), notes: payload.notes || null };
    if (useMock) { const row = { id: Date.now(), ...body, actual_date: null, status: 'planned', delay_reason: null, actual_yield_tonnes: null, created_at: '2026-09-07T09:00:00Z', updated_at: '2026-09-07T09:00:00Z' }; mockBlastEvents.unshift(row); return delay(row); }
    return request('/blast-events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  },
  async updateBlastEvent(id, payload) {
    const body = { status: payload.status, actual_date: payload.actual_date || null, delay_reason: payload.delay_reason || null, actual_yield_tonnes: payload.actual_yield_tonnes === '' || payload.actual_yield_tonnes === undefined ? null : Number(payload.actual_yield_tonnes), notes: payload.notes ?? null };
    if (useMock) { const row = mockBlastEvents.find((item) => item.id === Number(id)); if (row) Object.assign(row, body, { updated_at: '2026-09-07T11:00:00Z' }); return delay(row); }
    return request(`/blast-events/${Number(id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  },
  async getBlastEventSummary({ site_id, from, to } = {}) {
    if (useMock) return delay(mockBlastSummary);
    return request(`/blast-events/summary${query({ site_id: site_id === undefined ? undefined : Number(site_id), from, to })}`);
  },
  async getUploadLimits() {
    if (useMock) return delay({ max_report_bytes: 10 * 1024 * 1024, allowed_mime: ['application/pdf'] });
    return request('/config/upload-limits');
  },
  async getHealth() { return useMock ? delay(mockData.health) : request('/health'); },
  async getAdminJobs() { return useMock ? delay(mockData.jobs) : request('/admin/jobs'); },
  async getTrainingRanges() { if (useMock) return delay(null); try { return await request('/simulate/training-ranges'); } catch { return null; } },
  async getDashboard() {
    const [kpi, sites, risks, recommendations] = await Promise.all([this.getKpiSummary(), this.getSites(), this.getRiskEvents(undefined, false), this.getRecommendations()]);
    const production = await Promise.all(sitesFor(this, sites));
    return { kpi, sites, risks, recommendations, production: production.flat() };
  },
  async getSiteWorkspace(id) {
    const siteId = Number(id);
    const [site, equipmentForSite, productionForSite, risks, zones, primaryRisk] = await Promise.all([
      this.getSite(siteId), this.getEquipment(siteId), this.getProduction(siteId, 30), this.getRiskEvents(siteId, false), this.getReserveZones(siteId), this.getSitePrimaryRisk(siteId),
    ]);
    // Scoped to this site's own (typically few) risk events, not
    // getRecommendations()'s system-wide fan-out across every open risk
    // event -- that used to tie one site's load time to the total
    // risk-event count across all sites, then filtered the result down to
    // this site's risks anyway.
    const recommendationsForSite = (await Promise.all(risks.map((risk) => this.getRecommendations(risk.id)))).flat();
    // Guard: with no open risk this became /risk-events/NaN/causal-graph -> 422 and failed the page.
    const graph = primaryRisk ? await this.getCausalGraph(primaryRisk.id) : { nodes: [], edges: [], graph_source: 'neo4j', note: null };
    return { site, equipment: equipmentForSite, production: productionForSite, risks, zones: zones.features || [], recommendations: recommendationsForSite, graph };
  },
  async getMapWorkspace() {
    const [sites, zones] = await Promise.all([this.getSites(), this.getReserveZones()]);
    return { sites, zones: zones.features || [] };
  },
  async getReportsWorkspace() { const [risks, recommendations] = await Promise.all([this.getRiskEvents(undefined, false), this.getRecommendations()]); return { risks, recommendations }; },
  async getFieldWorkspace() {
    if (useMock) return { equipment: await delay(mockData.equipment), production: await delay(mockData.production), notes: await this.getSiteNotes(1) };
    const sites = await this.getSites();
    const equipmentBySite = await Promise.all(sites.map((site) => this.getEquipment(site.id)));
    const productionBySite = await Promise.all(sites.map((site) => this.getProduction(site.id, 30)));
    const notesForSite = await this.getSiteNotes(1);
    return { equipment: equipmentBySite.flat(), production: productionBySite.flat(), notes: notesForSite };
  },
  async getSettingsWorkspace() { const [health, jobs] = await Promise.all([this.getHealth(), this.getAdminJobs()]); return { health, jobs }; },
};

function sitesFor(client, sites) {
  return sites.map((site) => client.getProduction(site.id, 30));
}