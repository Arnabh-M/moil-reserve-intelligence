import { mockData, findSite } from './mockData';

const useMock = String(import.meta.env.VITE_USE_MOCK ?? 'true') !== 'false';
const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
const wait = (value, delay = 160) => new Promise((resolve) => setTimeout(() => resolve(value), delay));

function contractError(status, body) {
  const detail = body?.detail || body?.message || `Request failed (${status})`;
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
  async getRecommendations(riskId) {
    if (riskId !== undefined && riskId !== null) return useMock ? delay(mockData.recommendations.filter((item) => Number(item.risk_event_id) === Number(riskId))) : request(`/recommendations${query({ risk_event_id: Number(riskId) })}`);
    const events = await this.getRiskEvents(undefined, false);
    const batches = [];
    for (let index = 0; index < events.length; index += 8) batches.push(events.slice(index, index + 8));
    const results = [];
    for (const batch of batches) results.push(...(await Promise.all(batch.map((event) => this.getRecommendations(event.id)))));
    return results.flat();
  },
  async simulate({ scenario_type, site_id, duration_days }) {
    const payload = { scenario_type, site_id: Number(site_id), duration_days: Number(duration_days) };
    return useMock ? delay({ ...mockData.simulation, scenario_type, site_id: Number(site_id), duration_days: Number(duration_days) }) : request('/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
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
    if (useMock) { const item = mockData.equipment.find((equipment) => equipment.id === Number(id)); if (item) Object.assign(item, { status: payload.status, status_reason: payload.status_reason || item.status_reason, last_status_change: '2026-09-05T15:20:00Z' }); return delay(item); }
    return request(`/equipment/${Number(id)}/status`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: payload.status, reason: payload.status_reason || null }) });
  },
  async createProduction(payload) {
    const body = { site_id: Number(payload.site_id), date: payload.date, actual_output: Number(payload.actual_output), target_output: Number(payload.target_output) };
    if (useMock) { if (body.actual_output < 0 || body.target_output <= 0) throw contractError(422, { detail: 'Output must be non-negative and target must be greater than zero.', error_code: 'VALIDATION_ERROR' }); if (mockData.production.some((row) => row.site_id === body.site_id && row.date === body.date)) throw contractError(409, { detail: 'A production record already exists for this site and date.', error_code: 'PRODUCTION_CONFLICT' }); const row = { id: Date.now(), ...body, variance_pct: Number((((body.actual_output - body.target_output) / body.target_output) * 100).toFixed(1)) }; mockData.production.unshift(row); return delay(row); }
    return request('/production', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  },
  async getHealth() { return useMock ? delay(mockData.health) : request('/health'); },
  async getAdminJobs() { return useMock ? delay(mockData.jobs) : request('/admin/jobs'); },
  async getDashboard() {
    const [kpi, sites, risks, recommendations] = await Promise.all([this.getKpiSummary(), this.getSites(), this.getRiskEvents(undefined, false), this.getRecommendations()]);
    const production = await Promise.all(sitesFor(this, sites));
    return { kpi, sites, risks, recommendations, production: production.flat() };
  },
  async getSiteWorkspace(id) {
    const siteId = Number(id);
    const [site, equipmentForSite, productionForSite, risks, zones, recommendationsForSite] = await Promise.all([
      this.getSite(siteId), this.getEquipment(siteId), this.getProduction(siteId, 30), this.getRiskEvents(siteId, false), this.getReserveZones(siteId), this.getRecommendations(),
    ]);
    // Guard: with no open risk this became /risk-events/NaN/causal-graph -> 422 and failed the page.
    const graph = risks[0] ? await this.getCausalGraph(risks[0].id) : { nodes: [], edges: [], graph_source: 'neo4j', note: null };
    return { site, equipment: equipmentForSite, production: productionForSite, risks, zones: zones.features || [], recommendations: recommendationsForSite.filter((item) => risks.some((risk) => Number(risk.id) === Number(item.risk_event_id))), graph };
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