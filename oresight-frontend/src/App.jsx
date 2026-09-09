import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Activity, AlertCircle, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3, Bell, Check, ChevronRight, CircleHelp, ClipboardList, Database, Download, FileText, Gauge, GitBranch, Home, Info, Layers3, MapPin, Loader2, Map as MapIcon, Menu, Moon, Plus, RefreshCw, RotateCcw, Search, Settings as SettingsIcon, ShieldCheck, SlidersHorizontal, Sun, Trash2, Truck, X, Zap } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, AreaChart, Area, BarChart, Bar, CartesianGrid } from 'recharts';
import { api } from './api/client';
import { previewNotice, localPreferences } from './api/placeholders';
import { ErrorBoundary } from './components/error-boundary';
import { SAMPLE_SITES, DEFAULT_RASTER_OPACITY, MAP_CENTER, MAP_ZOOM, REGIONAL_BOUNDS, prospectivityUrl, prospectivityBandsUrl } from './lib/map';
import LayerToggle from './components/map/LayerToggle';
import MineMap from './components/map/MineMap';
import ZoneDetailPanel from './components/map/ZoneDetailPanel';
import CrossSectionDrawer from './components/map/CrossSectionDrawer';
import ProspectivityCellPanel from './components/map/ProspectivityCellPanel';
import CausalGraph from './components/CausalGraph';
import { useSites } from './hooks/useSites';
// Lazy-loaded: a missing/broken dependency in one Field Intake tab (see
// react-window, which shipped in package.json without a matching install)
// should only break that tab, not the whole router — every route used to
// 500 because these were eager top-level imports in App.jsx.
const EquipmentTab = lazy(() => import('./components/field-intake/EquipmentTab'));
const ProductionTab = lazy(() => import('./components/field-intake/ProductionTab'));
const GeologyTab = lazy(() => import('./components/field-intake/GeologyTab'));
const BlastLogTab = lazy(() => import('./components/field-intake/BlastLogTab'));

const navGroups = [
  { label: 'Command', links: [{ to: '/', label: 'Dashboard', icon: Home }, { to: '/map', label: 'Reserve map', icon: MapIcon }, { to: '/reports', label: 'Reports & insights', icon: BarChart3 }] },
  { label: 'Planning', links: [{ to: '/simulator', label: 'Scenario simulator', icon: GitBranch }, { to: '/field-intake', label: 'Field intake', icon: ClipboardList }] },
  { label: 'System', links: [{ to: '/settings', label: 'Settings', icon: SettingsIcon }] },
];
const severityClass = (severity) => severity === 'critical' || severity === 'high' ? 'critical' : severity === 'medium' ? 'warn' : 'good';
const severityLabel = (severity) => severity[0].toUpperCase() + severity.slice(1);
const riskTypeLabel = (type) => ({ equipment_failure: 'Equipment failure', production_shortfall: 'Production shortfall', weather_delay: 'Weather delay', blast_delay: 'Blast delay' }[type] || type);
const percent = (value, digits = 0) => `${(Number(value) * 100).toFixed(digits)}%`;
const recommendationTypeLabel = (type) => ({ reschedule: 'Reschedule plan', redeploy: 'Redeploy equipment', adjust_plan: 'Adjust plan' }[type] || type);
// Must match POST /simulate's scenario_type enum exactly (confirmed live
// against GET /openapi.json) -- the old option list (equipment_failure/
// production_shortfall/weather_delay/blast_delay) matched none of it, so
// every manual simulation run 422'd.
const SCENARIO_TYPE_OPTIONS = [
  { value: 'equipment_down', label: 'Equipment down' },
  { value: 'delay_blasting', label: 'Blast delay' },
  { value: 'rainfall_event', label: 'Rainfall event' },
];
const isValidScenarioType = (value) => SCENARIO_TYPE_OPTIONS.some((option) => option.value === value);
// The backend doesn't expose a direct risk_type -> scenario_type mapping, so
// this is a best-effort heuristic based on what each demoed scenario is
// actually caused by (e.g. Balaghat's only production_shortfall event today
// is rainfall-driven) -- good enough to prefill the Simulator sensibly from
// a recommendation, not a guaranteed-correct contract.
const RISK_TYPE_TO_SCENARIO_TYPE = { equipment_failure: 'equipment_down', blast_delay: 'delay_blasting', weather_delay: 'rainfall_event', production_shortfall: 'rainfall_event' };
function simulatorPathForRisk(risk, durationDays = 7) {
  if (!risk) return '/simulator';
  const scenarioType = RISK_TYPE_TO_SCENARIO_TYPE[risk.risk_type] || 'equipment_down';
  return `/simulator?scenario_type=${scenarioType}&site_id=${risk.site_id}&duration_days=${durationDays}`;
}
const dateLabel = (date) => new Date(date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
const timeLabel = (date) => new Date(date).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

function useAsync(load, deps = []) {
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const run = () => {
    setState((current) => ({ ...current, loading: true, error: null }));
    load().then((data) => setState({ loading: false, error: null, data })).catch((error) => setState({ loading: false, error, data: null }));
  };
  useEffect(() => { let active = true; setState({ loading: true, error: null, data: null }); load().then((data) => active && setState({ loading: false, error: null, data })).catch((error) => active && setState({ loading: false, error, data: null })); return () => { active = false; }; }, deps);
  return { ...state, retry: run };
}

function LoadingCard({ lines = 4 }) { return <div className="card section-card" aria-label="Loading"><div className="skeleton" style={{ width: '38%', marginBottom: 16 }} />{Array.from({ length: lines }).map((_, i) => <div className="skeleton" key={i} style={{ width: `${78 - i * 8}%`, marginBottom: 11 }} />)}</div>; }
function ErrorState({ retry }) { return <div className="error-box"><strong>Could not load this view</strong><p className="subhead">The intelligence service did not return a usable response. Try again or keep working from the last known plan.</p><button className="btn small" onClick={retry} data-testid="button-retry"><RefreshCw size={13} /> Retry</button></div>; }
function FieldIntakeTabFallback({ error, resetError }) { return <div className="error-box"><strong>This tab could not load</strong><p className="subhead">{error?.message || 'Something went wrong loading this Field Intake tab.'} The rest of the app is unaffected — try another tab or retry this one.</p><button className="btn small" onClick={resetError} data-testid="button-retry-field-intake-tab"><RefreshCw size={13} /> Retry</button></div>; }
function EmptyState({ icon: Icon = ClipboardList, title = 'Nothing to show', children = 'No records match the current filters.' }) { return <div className="empty"><Icon size={25} /><strong>{title}</strong><div className="subhead">{children}</div></div>; }

// No sidebar entry points at /site/:id directly (site pages are reached by
// drilling into a Dashboard site card), so treat it as belonging under
// Dashboard for nav highlighting, and resolve the real site name for the
// breadcrumb independently -- Shell renders outside SitePage's own data
// fetch, so it needs its own light-weight lookup rather than reading
// SitePage's state.
function useSiteBreadcrumbName(siteId) {
  const [state, setState] = useState({ status: 'idle', name: null });
  useEffect(() => {
    if (!siteId) { setState({ status: 'idle', name: null }); return; }
    let active = true;
    setState({ status: 'loading', name: null });
    api.getSite(siteId).then((site) => { if (active) setState({ status: 'ready', name: site?.name || null }); }).catch(() => { if (active) setState({ status: 'error', name: null }); });
    return () => { active = false; };
  }, [siteId]);
  return state;
}

function Shell({ children }) {
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem('oresight-theme') === 'dark');
  const location = useLocation();
  const siteMatch = location.pathname.match(/^\/site\/([^/]+)$/);
  const siteId = siteMatch ? siteMatch[1] : null;
  const siteBreadcrumb = useSiteBreadcrumbName(siteId);
  const current = navGroups.flatMap((g) => g.links).find((link) => link.to === location.pathname || (link.to !== '/' && location.pathname.startsWith(link.to)));
  const breadcrumbLabel = siteId ? (siteBreadcrumb.status === 'ready' && siteBreadcrumb.name ? siteBreadcrumb.name : siteBreadcrumb.status === 'loading' ? 'Loading site…' : 'Site intelligence') : (current?.label || 'Workspace');
  useEffect(() => { document.documentElement.classList.toggle('dark', dark); localStorage.setItem('oresight-theme', dark ? 'dark' : 'light'); }, [dark]);
  return <div className="app-shell">
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="brand"><div className="brand-mark">O</div><div><div className="brand-word">OreSight</div><span className="brand-sub">mine intelligence</span></div></div>
      {navGroups.map((group) => <div className="nav-group" key={group.label}><div className="nav-label">{group.label}</div>{group.links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive || (to !== '/' && location.pathname.startsWith(to)) || (to === '/' && Boolean(siteId)) ? 'active' : ''}`} data-testid={`link-${label.toLowerCase().replaceAll(' ', '-')}`}><Icon size={15} strokeWidth={1.8} /><span>{label}</span>{label === 'Dashboard' && <span style={{ marginLeft: 'auto', font: '9px var(--app-font-mono)', color: 'hsl(var(--primary))' }}>04</span>}</NavLink>)}</div>)}
      <div className="sidebar-footer"><div className="user-chip"><div className="avatar">AK</div><div><div className="user-name">Anika Kulkarni</div><div className="user-role">Planning lead · IN-WEST</div></div></div></div>
    </aside>
    <div className="main-col">
      <header className="topbar"><div className="breadcrumb"><button className="btn ghost mobile-toggle" onClick={() => setOpen(!open)} aria-label="Open navigation" data-testid="button-open-navigation"><Menu size={17} /></button><span>OreSight</span><ChevronRight size={13} /><strong>{breadcrumbLabel}</strong></div><div className="top-actions"><button className="btn ghost small" title="Toggle theme" onClick={() => setDark(!dark)} data-testid="button-toggle-theme">{dark ? <Sun size={15} /> : <Moon size={15} />}</button><button className="btn ghost small" title="Notifications" data-testid="button-notifications"><Bell size={15} /></button></div></header>
      {children}
    </div>
  </div>;
}

function StatCard({ label, value, foot, trend, icon: Icon }) { return <div className="card stat-card" data-testid={`stat-${label.toLowerCase().replaceAll(' ', '-')}`}><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-foot">{Icon && <Icon size={13} />}{trend && <span className={trend > 0 ? 'trend-up' : 'trend-down'}>{trend > 0 ? '+' : ''}{trend}%</span>}<span>{foot}</span></div></div>; }
function Sparkline({ data, color = 'hsl(31 82% 47%)' }) { return <svg className="sparkline" viewBox="0 0 160 34" preserveAspectRatio="none"><polyline points={data.map((v, i) => `${i * 26},${32 - v}`).join(' ')} fill="none" stroke={color} strokeWidth="2" /></svg>; }
function SiteCard({ site }) {
  const siteProduction = [1, 2, 3, 4, 5, 6, 7].map((_, i) => 25 + ((Number(site.id) * 9 + i * 11) % 20));
  return <Link to={`/site/${site.id}`} className="card site-card" data-testid={`card-site-${site.id}`}><div className="site-top"><div><div className="site-name">{site.name}</div><div className="site-place">{site.district} · {site.state}</div></div><span className={`pill ${site.active_risk_count > 2 ? 'critical' : 'warn'}`}>{site.active_risk_count} risks</span></div><div className="site-metrics"><div><div className="metric-label">Reserve confidence</div><div className="metric-value">{percent(site.avg_reserve_confidence)}</div></div><div><div className="metric-label">Operating state</div><div className="metric-value" style={{ fontSize: 14, color: 'hsl(var(--accent))' }}>{site.active_risk_count > 2 ? 'Watch' : 'Stable'}</div></div></div><Sparkline data={siteProduction} /><div className="risk-line"><span className={`dot ${site.active_risk_count > 2 ? 'risk-high' : 'risk-med'}`} />{site.belt_name}<ChevronRight size={13} style={{ marginLeft: 'auto' }} /></div></Link>;
}
function RiskItem({ risk, compact = false }) { return <div className="risk-item" data-testid={`risk-${risk.id}`}><div className={`risk-marker ${risk.severity === 'medium' ? 'medium' : ''}`} /><div className="risk-item-main"><div className="risk-title">{riskTypeLabel(risk.risk_type)}</div><div className="risk-meta">{risk.site_name} · {dateLabel(risk.detected_at)} {timeLabel(risk.detected_at)}</div>{!compact && <div className="subhead">{risk.description}</div>}</div><div><div className="risk-score">{percent(risk.score)}</div><span className={`pill ${severityClass(risk.severity)}`}>{severityLabel(risk.severity)}</span></div></div>; }
// Persists one recommendation option to GET/POST /shift-plan. Owns its own
// idle -> saving -> added state so each button in a list is independent.
function ShiftPlanButton({ riskEventId, option, showToast, testId }) {
  const [status, setStatus] = useState('idle');
  const add = async () => {
    setStatus('saving');
    try {
      await api.addToShiftPlan({
        risk_event_id: riskEventId,
        option_type: option.type,
        description: option.description,
        target_id: option.target_id,
        projected_impact: option.projected_impact,
        confidence: option.confidence,
      });
      setStatus('added');
      showToast?.('Added to shift plan');
    } catch (error) {
      setStatus('idle');
      showToast?.(error.detail || 'Could not add to shift plan');
    }
  };
  return <button className="btn small" onClick={add} disabled={status !== 'idle'} data-testid={testId}><Check size={12} /> {status === 'added' ? 'Added' : status === 'saving' ? 'Adding…' : 'Add to shift plan'}</button>;
}
function Recommendation({ recommendation, showToast }) { const option = recommendation.options[0]; if (!option) return <EmptyState title="No graph-sourced alternatives found for this event" />; return <div className="card recommend-card"><div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><div><span className="eyebrow">Response to {riskTypeLabel(recommendation.trigger)}</span><h3 style={{ marginTop: 5 }}>{recommendationTypeLabel(option.type)}</h3></div><Zap size={15} color="hsl(var(--primary))" /></div><p>{option.description}</p><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}><span className="recommend-impact">+{option.projected_impact}% projected impact</span><div style={{ display: 'flex', gap: 8 }}><ShiftPlanButton riskEventId={recommendation.risk_event_id} option={option} showToast={showToast} testId={`button-apply-dashboard-${recommendation.risk_event_id}`} /><button className="btn small" data-testid={`button-review-${recommendation.risk_event_id}`}>Review <ChevronRight size={12} /></button></div></div></div>; }

function Dashboard() {
  const { data, loading, error, retry } = useAsync(() => api.getDashboard(), []);
  const [riskFilter, setRiskFilter] = useState('all');
  const [toast, setToast] = useState('');
  const showToast = (message) => { setToast(message); setTimeout(() => setToast(''), 2200); };
  if (loading) return <main className="page"><div className="page-head"><div><div className="skeleton" style={{ width: 130, marginBottom: 11 }} /><div className="skeleton" style={{ width: 290, height: 28 }} /></div></div><LoadingCard lines={7} /></main>;
  if (error) return <main className="page"><ErrorState retry={retry} /></main>;
  const { kpi, sites, risks, recommendations, production } = data;
  const chartData = Array.from({ length: 7 }, (_, i) => ({ day: dateLabel(production[i].date), actual: production[i].actual_output, target: production[i].target_output }));
  const filteredRisks = riskFilter === 'all' ? risks : risks.filter((risk) => risk.severity === riskFilter);
  return <main className="page">
    <div className="page-head"><div><div className="eyebrow">05 September 2026 · shift briefing</div><h1>Morning control room</h1><p className="subhead">A triage view across the Central Indian operating plan. Start with what can move output today.</p></div><div className="filter-row"><button className="btn" onClick={() => window.print()} data-testid="button-print-dashboard"><Download size={14} /> Briefing print</button><Link className="btn primary" to="/simulator?scenario_type=equipment_down&site_id=1&duration_days=7" data-testid="link-open-simulator"><GitBranch size={14} /> Run a scenario</Link></div></div>
    <div className="alert-strip" style={{ marginBottom: 15 }}><AlertTriangle size={15} color="hsl(var(--primary))" /><span><strong>Priority:</strong> Balaghat production shortfall is the highest-confidence intervention opportunity. The current plan is 8.6% below target at Bench 7.</span><Link to="/site/1?tab=recommendations" style={{ marginLeft: 'auto', color: 'hsl(var(--primary))', fontWeight: 700 }}>Open signal <ChevronRight size={13} style={{ verticalAlign: 'middle' }} /></Link></div>
    <div className="stat-grid"><StatCard label="Active risk events" value={kpi.active_risk_events} foot="2 high severity" trend={-8.4} icon={AlertTriangle} /><StatCard label="Avg reserve confidence" value={percent(kpi.avg_reserve_confidence, 1)} foot="across active zones" trend={2.8} icon={ShieldCheck} /><StatCard label="Sites under watch" value={kpi.sites_under_watch} foot="of 3 operating sites" icon={Activity} /><StatCard label="Twin last updated" value="08:05" foot="14 Feb · 6 min ago" icon={RefreshCw} /></div>
    <div className="dashboard-grid"><section className="card section-card"><div className="card-head"><div><div className="card-title">Site status</div><div className="card-kicker">current operating posture · click through for intelligence</div></div><Link to="/map" className="btn small">Open reserve map <MapIcon size={12} /></Link></div><div className="site-grid">{sites.map((site) => <SiteCard site={site} key={site.id} />)}</div></section><section className="card section-card"><div className="card-head"><div><div className="card-title">Recent risk events</div><div className="card-kicker">ranked by model score · unresolved first</div></div><select className="select" value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} aria-label="Filter risk severity" data-testid="select-risk-filter"><option value="all">All severity</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></div><div className="risk-list">{filteredRisks.length ? filteredRisks.slice(0, 4).map((risk) => <RiskItem risk={risk} compact key={risk.id} />) : <EmptyState icon={ShieldCheck} title="No matching risks" />}</div></section></div>
    <div className="dashboard-grid equal"><section className="card section-card"><div className="card-head"><div><div className="card-title">Production pulse</div><div className="card-kicker">all sites · tonnes per day</div></div><div className="legend"><span><i />Actual</span><span><i className="target" />Target</span></div></div><div style={{ height: 220 }}><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData}><CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="day" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={35} /><Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', fontSize: 11 }} /><Area type="monotone" dataKey="target" stroke="hsl(var(--accent) / .38)" fill="hsl(var(--accent) / .07)" strokeWidth={2} /><Area type="monotone" dataKey="actual" stroke="hsl(var(--primary))" fill="hsl(var(--primary) / .12)" strokeWidth={2} /></AreaChart></ResponsiveContainer></div></section><section className="card section-card"><div className="card-head"><div><div className="card-title">Recommended actions</div><div className="card-kicker">model-ranked options · choose before shift change</div></div><Link to="/reports" className="btn small">All insights</Link></div>{recommendations.slice(0, 2).map((item) => <Recommendation recommendation={item} showToast={showToast} key={item.risk_event_id} />)}</section></div>
    <div className="footer-note"><CircleHelp size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} /> {previewNotice} Twin state last refreshed at {timeLabel(kpi.twin_last_updated)} IST.</div>
    {toast && <div className="toast">{toast}</div>}
  </main>;
}

function SitePage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || 'overview';
  const { data, loading, error, retry } = useAsync(() => api.getSiteWorkspace(id), [id]);
  const [toast, setToast] = useState('');
  const tabs = ['overview', 'production', 'reserve', 'recommendations', 'graph'];
  if (loading) return <main className="page"><LoadingCard lines={9} /></main>;
  if (error || !data) return <main className="page"><ErrorState retry={retry} /></main>;
  const { site, risks, equipment, production, zones, recommendations, graph } = data;
  const setTab = (next) => setSearchParams({ tab: next });
  const showToast = (message) => { setToast(message); setTimeout(() => setToast(''), 2200); };
  return <main className="page"><div className="site-banner"><div><div className="eyebrow">Site intelligence · {site.id}</div><h1>{site.name}</h1><div className="site-place">{site.belt_name} · {site.district}, {site.state} · updated 08:05 IST</div></div><div className="filter-row"><span className={`pill ${site.active_risk_count > 2 ? 'critical' : 'warn'}`}>{site.active_risk_count} active risks</span><Link className="btn small" to="/map">View on map <MapIcon size={12} /></Link></div></div><div className="tabs">{tabs.map((item) => <button className={`tab ${tab === item ? 'active' : ''}`} onClick={() => setTab(item)} key={item} data-testid={`tab-site-${item}`}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div>
    {tab === 'overview' && <SiteOverview site={site} risks={risks} equipment={equipment} zones={zones} production={production} />}
    {tab === 'production' && <ProductionView production={production} site={site} />}
    {tab === 'reserve' && <ReserveView zones={zones} site={site} />}
    {tab === 'recommendations' && <RecommendationsView recommendations={recommendations} risks={risks} showToast={showToast} />}
    {tab === 'graph' && <GraphView graph={graph} />}
    {toast && <div className="toast">{toast}</div>}
  </main>;
}
function SiteOverview({ site, risks, equipment, zones, production }) { return <><div className="stat-grid"><StatCard label="Reserve confidence" value={percent(site.avg_reserve_confidence)} foot="weighted active zones" trend={2.1} icon={ShieldCheck} /><StatCard label="Output variance" value={`${production.reduce((a, b) => a + b.variance_pct, 0) / production.length > 0 ? '+' : ''}${(production.reduce((a, b) => a + b.variance_pct, 0) / production.length).toFixed(1)}%`} foot="7-day average" icon={BarChart3} /><StatCard label="Equipment online" value={`${equipment.filter((e) => e.status === 'up').length}/${equipment.length}`} foot="current shift" icon={Truck} /><StatCard label="Zones inventoried" value={zones.length} foot="confidence screened" icon={Layers3} /></div><div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Risk register</div><div className="card-kicker">open events linked to site signals</div></div><Link to="/reports" className="btn small">View reports</Link></div>{risks.length ? risks.map((risk) => <RiskItem risk={risk} key={risk.id} />) : <EmptyState title="No open risk events" />}</section><section className="card section-card"><div className="card-head"><div><div className="card-title">Equipment posture</div><div className="card-kicker">reported by field operations</div></div><Truck size={16} color="hsl(var(--muted-foreground))" /></div>{equipment.map((item) => <div className="mini-stat" key={item.id}><span><b>{item.name}</b><br /><small className="muted">{item.equipment_type}</small></span><span className={`pill ${item.status === 'up' ? 'good' : 'critical'}`}>{item.status}</span></div>)}</section></div></>; }
function ProductionView({ production, site }) { return <div className="section-stack"><section className="card section-card"><div className="card-head"><div><div className="card-title">Production variance · {site.name}</div><div className="card-kicker">actual vs target output · tonnes per day</div></div><span className="pill warn">7 day window</span></div><div style={{ height: 300 }}><ResponsiveContainer width="100%" height="100%"><BarChart data={production}><CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickFormatter={(v) => v.slice(5)} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', fontSize: 11 }} /><Bar dataKey="target_output" fill="hsl(var(--accent) / .3)" name="Target" radius={[3, 3, 0, 0]} /><Bar dataKey="actual_output" fill="hsl(var(--primary))" name="Actual" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div></section><section className="card section-card"><div className="card-head"><div className="card-title">Shift ledger</div><div className="card-kicker">7-day actual vs target · live</div></div><div className="table-wrap"><table><thead><tr><th>Date</th><th>Actual</th><th>Target</th><th>Variance</th><th>Plan read</th></tr></thead><tbody>{production.map((item) => <tr key={item.id}><td className="mono">{item.date}</td><td>{item.actual_output.toLocaleString()} t</td><td>{item.target_output.toLocaleString()} t</td><td className={item.variance_pct < 0 ? 'risk-high' : 'trend-up'}>{item.variance_pct > 0 ? '+' : ''}{item.variance_pct}%</td><td><div className="progress" style={{ width: 120 }}><span style={{ width: `${Math.min(100, 100 + item.variance_pct)}%` }} /></div></td></tr>)}</tbody></table></div></section></div>; }
function ReserveView({ zones, site }) { const rows = zones.map((zone) => zone.properties); return <div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Grade distribution</div><div className="card-kicker">confidence-weighted zone estimate · {site.name}</div></div></div><div style={{ height: 270 }}><ResponsiveContainer width="100%" height="100%"><BarChart data={rows}><CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="zone_name" tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', fontSize: 11 }} /><Bar dataKey="estimated_grade_pct" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></section><section className="card section-card"><div className="card-head"><div><div className="card-title">Zone inventory</div><div className="card-kicker">prospectivity signal, not a reserve statement</div></div><Layers3 size={16} /></div>{rows.length ? rows.map((zone) => <div className="mini-stat" key={zone.id}><span><b>{zone.zone_name}</b><br /><small className="muted">{zone.estimated_grade_pct}% estimated grade · {zone.estimated_depth_m} m</small></span><span><b>{percent(zone.confidence_score)}</b><br /><small className="muted">confidence</small></span></div>) : <EmptyState title="No zone inventory" />}</section></div>; }
function RecommendationsView({ recommendations, risks, showToast }) { return <div className="two-col"><section className="section-stack">{recommendations.map((item) => { const risk = risks.find((r) => r.id === item.risk_event_id); return <div key={item.risk_event_id}><div className="eyebrow" style={{ margin: '5px 0 7px' }}>{riskTypeLabel(risk?.risk_type || item.trigger)}</div>{item.options.length ? item.options.map((option) => <div className="card recommend-card" key={option.type}><div className="card-head" style={{ marginBottom: 7 }}><h3>{recommendationTypeLabel(option.type)}</h3><span className="pill good">{percent(option.confidence)} confidence</span></div><p>{option.description}</p><div className="recommend-impact">+{option.projected_impact}% projected impact</div><div style={{ display: 'flex', gap: 8, marginTop: 12 }}><ShiftPlanButton riskEventId={item.risk_event_id} option={option} showToast={showToast} testId={`button-apply-${option.type.toLowerCase().replaceAll('_', '-')}`} /><Link className="btn small" to={simulatorPathForRisk(risk)} data-testid={`link-simulate-${item.risk_event_id}`}><Zap size={12} /> Simulate</Link></div></div>) : <EmptyState title="No graph-sourced alternatives found for this event" />}</div>; })}</section><section className="card section-card"><div className="card-title">How to read recommendations</div><p className="subhead">Each option combines the active risk trigger with site state and graph context. Projected impact is already expressed as a percentage; it is not a probability.</p><div className="alert-strip" style={{ marginTop: 18 }}><CircleHelp size={15} /><span>{previewNotice}</span></div></section></div>; }
function GraphView({ graph }) { return <div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Causal graph</div><div className="card-kicker">{graph.graph_source} · relationship edges</div></div></div><CausalGraph graph={graph} height={420} /></section><section className="card section-card"><div className="card-title">Relationships</div>{graph.edges.map((edge) => <div className="mini-stat" key={`${edge.source}-${edge.target}`}><span>{graph.nodes.find((n) => n.id === edge.source)?.label}<br /><small className="muted">{edge.relationship}</small></span><ChevronRight size={14} /><span>{graph.nodes.find((n) => n.id === edge.target)?.label}</span></div>)}<div className="footer-note">{graph.note}</div></section></div>; }

function MapPage() {
  // Ported from the pre-Replit oresight-frontend (git 230f49a) — real MapLibre
  // layers (prospectivity heatmap, spectral alteration, NDVI
  // time-series, structural lineaments) instead of the Replit import's
  // schematic placeholder map. See components/map/* and lib/map.js.
  const [prospectivityVisible, setProspectivityVisible] = useState(false);
  const [spectralVisible, setSpectralVisible] = useState(false);
  const [ndviVisible, setNdviVisible] = useState(false);
  const [lineamentVisible, setLineamentVisible] = useState(false);
  const [rasterOpacity, setRasterOpacity] = useState(DEFAULT_RASTER_OPACITY);

  const [prospectivitySiteId, setProspectivitySiteId] = useState(null);
  const [prospectivityData, setProspectivityData] = useState(null);
  const [prospectivityBands, setProspectivityBands] = useState(null);
  const [prospectivityStatus, setProspectivityStatus] = useState('idle');
  const [selectedCell, setSelectedCell] = useState(null);

  const [selectedWeek, setSelectedWeek] = useState(4);
  const [selectedZone, setSelectedZone] = useState(null);
  const [sites, setSites] = useState([]);

  const [flyToTarget, setFlyToTarget] = useState(null);
  const [selectedSiteIdForFlyTo, setSelectedSiteIdForFlyTo] = useState('');

  const [crossSectionActive, setCrossSectionActive] = useState(false);
  const [crossSectionPoint, setCrossSectionPoint] = useState(null);
  const [crossSectionDrawerOpen, setCrossSectionDrawerOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getSites().then((data) => { if (!cancelled) setSites(data); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const siteNameById = useMemo(() => Object.fromEntries(sites.map((site) => [site.id, site.name])), [sites]);

  const selectedSiteName = useMemo(() => {
    if (!selectedZone) return null;
    const siteId = selectedZone.site_id;
    if (siteNameById[siteId]) return siteNameById[siteId];
    if (siteId === 1) return 'Balaghat Mine';
    if (siteId === 2) return 'Nagpur Mine';
    if (siteId === 3) return 'Bhandara Mine';
    return siteId ? String(siteId) : null;
  }, [selectedZone, siteNameById]);

  // On site selection: fly to the site, then load only that site's prospectivity surface.
  useEffect(() => {
    if (!prospectivitySiteId) {
      setProspectivityData(null);
      setProspectivityBands(null);
      setProspectivityStatus('idle');
      return;
    }
    let cancelled = false;
    setProspectivityStatus('loading');
    setSelectedCell(null);

    async function loadProspectivity() {
      try {
        const res = await fetch(prospectivityUrl(prospectivitySiteId));
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!data || data.type !== 'FeatureCollection' || !Array.isArray(data.features)) throw new Error('Malformed GeoJSON payload');
        if (cancelled) return;
        setProspectivityData(data);
        setProspectivityStatus('ready');
        try {
          const bandsRes = await fetch(prospectivityBandsUrl(prospectivitySiteId));
          if (bandsRes.ok && !cancelled) setProspectivityBands(await bandsRes.json());
        } catch { if (!cancelled) setProspectivityBands(null); }
      } catch (err) {
        console.warn('[MapPage] prospectivity load failed:', err);
        if (!cancelled) { setProspectivityData(null); setProspectivityBands(null); setProspectivityStatus('error'); }
      }
    }
    // Let the 1.2s flyTo settle before painting ~3k polygons.
    const timer = setTimeout(loadProspectivity, 1200);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [prospectivitySiteId]);

  function handleSiteSelect(rawSiteId) {
    // rawSiteId arrives as a string from the dropdown's e.target.value, or
    // already numeric from a map marker click (SITES_GEOJSON's properties.id).
    setSelectedSiteIdForFlyTo(rawSiteId ? Number(rawSiteId) : '');
    if (!rawSiteId) {
      setProspectivitySiteId(null);
      setSelectedZone(null);
      setSelectedCell(null);
      setFlyToTarget({
        id: null,
        bounds: REGIONAL_BOUNDS,
        longitude: MAP_CENTER.longitude,
        latitude: MAP_CENTER.latitude,
        zoom: MAP_ZOOM,
      });
      return;
    }
    const site = SAMPLE_SITES.find((s) => s.id === Number(rawSiteId));
    if (site) {
      setFlyToTarget({
        id: site.id,
        name: site.name,
        latitude: site.latitude,
        longitude: site.longitude,
        bounds: site.bounds,
        zoom: 11,
      });
      setProspectivitySiteId(site.slug);
    }
  }

  function handleSelectCrossSectionPoint(point) {
    setCrossSectionPoint(point);
    setCrossSectionDrawerOpen(true);
  }

  function handleInspectZoneCrossSection() {
    if (!selectedZone) return;
    const lat = selectedZone.latitude ?? (selectedZone.site_id === 1 ? 21.8 : selectedZone.site_id === 2 ? 21.1 : 21.2);
    const lng = selectedZone.longitude ?? (selectedZone.site_id === 1 ? 80.2 : selectedZone.site_id === 2 ? 79.1 : 79.6);
    setCrossSectionPoint({ lat, lng, zoneName: selectedZone.zone_name, site_id: selectedZone.site_id, siteName: selectedSiteName });
    setCrossSectionDrawerOpen(true);
  }

  return <main className="page" style={{ padding: 0, maxWidth: 'none' }}>
    <div style={{ display: 'flex', height: 'calc(100dvh - 67px)', overflow: 'hidden', position: 'relative' }}>
      <LayerToggle
        prospectivityVisible={prospectivityVisible}
        onProspectivityChange={setProspectivityVisible}
        spectralVisible={spectralVisible}
        onSpectralChange={setSpectralVisible}
        lineamentVisible={lineamentVisible}
        onLineamentChange={setLineamentVisible}
        ndviVisible={ndviVisible}
        onNdviChange={setNdviVisible}
        rasterOpacity={rasterOpacity}
        onRasterOpacityChange={setRasterOpacity}
        selectedSiteId={selectedSiteIdForFlyTo}
      />
      <div style={{ position: 'relative', minWidth: 0, flex: 1, height: '100%' }}>
        <div className="card" style={{ position: 'absolute', top: 16, right: 16, zIndex: 20, display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px' }}>
          <MapPin size={14} color="hsl(var(--primary))" />
          <select
            aria-label="Jump to Mine Site"
            value={selectedSiteIdForFlyTo}
            onChange={(e) => handleSiteSelect(e.target.value)}
            className="select"
            style={{ background: 'transparent', border: 'none', fontSize: 12, fontWeight: 600 }}
          >
            <option value="">Jump to Mine Site…</option>
            {SAMPLE_SITES.map((site) => <option key={site.id} value={site.id}>{site.name} Mine ({site.latitude.toFixed(1)}°N, {site.longitude.toFixed(1)}°E)</option>)}
          </select>
        </div>

        <MineMap
          prospectivityVisible={prospectivityVisible}
          spectralVisible={spectralVisible}
          ndviVisible={ndviVisible}
          lineamentVisible={lineamentVisible}
          selectedWeek={selectedWeek}
          onWeekChange={setSelectedWeek}
          onZoneSelect={setSelectedZone}
          onSiteSelect={handleSiteSelect}
          flyToTarget={flyToTarget}
          selectedSiteId={selectedSiteIdForFlyTo}
          crossSectionActive={crossSectionActive}
          onToggleCrossSection={() => setCrossSectionActive(!crossSectionActive)}
          onSelectCrossSectionPoint={handleSelectCrossSectionPoint}
          crossSectionPoint={crossSectionPoint}
          rasterOpacity={rasterOpacity}
          prospectivityData={prospectivityData}
          prospectivityBands={prospectivityBands}
          onProspectivityCellSelect={setSelectedCell}
        />

        {prospectivityStatus === 'loading' && <div className="card" style={{ position: 'absolute', left: '50%', top: 16, transform: 'translateX(-50%)', zIndex: 20, display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', fontSize: 12 }}><Loader2 size={14} className="spin" color="hsl(var(--primary))" /> Loading reserve surface…</div>}

        {prospectivityStatus === 'error' && <div className="card" style={{ position: 'absolute', left: '50%', top: 16, transform: 'translateX(-50%)', zIndex: 20, display: 'flex', alignItems: 'flex-start', gap: 8, padding: '9px 12px' }}><AlertCircle size={14} color="hsl(var(--destructive))" style={{ marginTop: 2 }} /><div><p style={{ fontSize: 12, fontWeight: 600, color: 'hsl(var(--destructive))' }}>Reserve data unavailable for this site</p><button type="button" onClick={() => setProspectivitySiteId((id) => (id ? `${id}` : id))} style={{ marginTop: 2, fontSize: 10, color: 'hsl(var(--muted-foreground))', textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer' }}>Select another site to retry</button></div></div>}

        <ProspectivityCellPanel
          cell={selectedCell}
          siteName={selectedCell ? siteNameById[selectedCell.site_id] || selectedCell.site_id : null}
          isPlaceholder={prospectivityData?.provenance?.status === 'PLACEHOLDER_SCORES'}
          onClose={() => setSelectedCell(null)}
        />

        <ZoneDetailPanel
          zone={selectedZone}
          siteName={selectedSiteName}
          onClose={() => setSelectedZone(null)}
          onInspectCrossSection={handleInspectZoneCrossSection}
        />

        <CrossSectionDrawer
          isOpen={crossSectionDrawerOpen}
          onClose={() => { setCrossSectionDrawerOpen(false); setCrossSectionPoint(null); setCrossSectionActive(false); }}
          point={crossSectionPoint}
        />
      </div>
    </div>
  </main>;
}

function ReportsPage() {
  const { data, loading, error, retry } = useAsync(() => api.getReportsWorkspace(), []);
  const [severity, setSeverity] = useState('all');
  const [toast, setToast] = useState('');
  if (loading) return <main className="page"><LoadingCard lines={10} /></main>;
  if (error) return <main className="page"><ErrorState retry={retry} /></main>;
  const risks = severity === 'all' ? data.risks : data.risks.filter((risk) => risk.severity === severity);
  // Corrective actions used to always list every recommendation regardless
  // of the severity filter, so the two panels could visibly disagree once
  // filtered -- scope it to the same filtered risk set as the timeline.
  const recommendations = data.recommendations.filter((rec) => risks.some((risk) => risk.id === rec.risk_event_id));
  const exportCsv = () => { const csv = ['site,risk,severity,score,detected_at', ...risks.map((r) => `${r.site_name},${r.risk_type},${r.severity},${r.score},${r.detected_at}`)].join('\n'); const blob = new Blob([csv], { type: 'text/csv' }); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'oresight-risk-register.csv'; anchor.click(); URL.revokeObjectURL(url); setToast('CSV report generated'); setTimeout(() => setToast(''), 2200); };
  return <main className="page"><div className="page-head"><div><div className="eyebrow">Reports & insights · decision trail</div><h1>Make the risk legible</h1><p className="subhead">A concise record of model signals, chosen responses, and the operational story behind the numbers.</p></div><button className="btn primary" onClick={exportCsv} data-testid="button-export-csv"><Download size={14} /> Export CSV</button></div><div className="card section-card" style={{ marginBottom: 14 }}><div className="filter-row"><SlidersHorizontal size={15} color="hsl(var(--muted-foreground))" /><select className="select" value={severity} onChange={(e) => setSeverity(e.target.value)} data-testid="select-report-severity"><option value="all">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select><span className="muted" style={{ fontSize: 10 }}>{risks.length} events in preview</span></div></div><div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Risk timeline</div><div className="card-kicker">detected events across the current planning window</div></div><span className="pill good"><Activity size={11} /> Live preview</span></div><div className="timeline">{risks.map((risk) => <div className="timeline-item" key={risk.id}><div className="timeline-date">{dateLabel(risk.detected_at)} · {timeLabel(risk.detected_at)} IST · {risk.site_name}</div><div className="timeline-text"><b>{riskTypeLabel(risk.risk_type)}</b> — {risk.description}</div><span className={`pill ${severityClass(risk.severity)}`} style={{ marginTop: 7 }}>{severityLabel(risk.severity)} · {percent(risk.score)}</span></div>)}</div></section><section className="section-stack"><div className="card section-card"><div className="card-head"><div><div className="card-title">Corrective actions</div><div className="card-kicker">response coverage</div></div><Check size={16} color="hsl(var(--accent))" /></div>{recommendations.length ? recommendations.map((rec) => { const risk = data.risks.find((r) => r.id === rec.risk_event_id); return <div className="mini-stat" key={rec.risk_event_id}><span><b>{riskTypeLabel(rec.trigger)}</b><br /><small className="muted">{rec.options.length} model-ranked options</small></span><div style={{ display: 'flex', gap: 6 }}><Link to={`/site/${risk?.site_id || 1}?tab=recommendations`} className="btn small">Review</Link><Link to={simulatorPathForRisk(risk)} className="btn small" data-testid={`link-simulate-report-${rec.risk_event_id}`}><Zap size={11} /> Simulate</Link></div></div>; }) : <EmptyState title="No corrective actions at this severity">Widen the severity filter above to see more.</EmptyState>}</div><div className="card section-card"><div className="card-title">Report preview</div><p className="subhead">The export contains the filtered risk register, current severity, model score, site, and detection timestamp. Narrative and graph evidence remain in site intelligence.</p><button className="btn" onClick={exportCsv} data-testid="button-download-report"><FileText size={13} /> Download report packet</button></div></section></div>{toast && <div className="toast"><Check size={14} style={{ verticalAlign: 'middle', marginRight: 7 }} />{toast}</div>}</main>;
}

const CONDITION_TYPES = [
  { value: 'equipment_down', label: 'Equipment down', icon: Truck },
  { value: 'delay_blasting', label: 'Blast delay', icon: Zap },
  { value: 'rainfall_event', label: 'Rainfall event', icon: AlertTriangle },
];
const EQUIPMENT_AREAS = [
  { value: 'dragline_1', label: 'Dragline #1' },
  { value: 'shovel_2', label: 'Shovel #2' },
  { value: 'conveyor_belt_a', label: 'Conveyor Belt A' },
  { value: 'haul_truck_fleet', label: 'Haul Truck Fleet' },
  { value: 'crusher_primary', label: 'Primary Crusher' },
  { value: 'bench_7', label: 'Bench 7 (open-cast)' },
  { value: 'processing_plant', label: 'Processing Plant' },
  { value: 'dewatering_system', label: 'Dewatering System' },
];
const DEFAULT_SEVERITY_LEVELS = {
  equipment_down: [
    { key: 'low', label: 'Low', percentile: '25th', value: 0.8 },
    { key: 'medium', label: 'Medium', percentile: '50th', value: 1.4 },
    { key: 'high', label: 'High', percentile: '75th', value: 2.5 },
    { key: 'severe', label: 'Severe', percentile: '95th', value: 4.7 },
  ],
  delay_blasting: [
    { key: 'low', label: 'Low', percentile: '25th', value: 0.4 },
    { key: 'medium', label: 'Medium', percentile: '50th', value: 6.2 },
    { key: 'high', label: 'High', percentile: '75th', value: 12.3 },
    { key: 'severe', label: 'Severe', percentile: '95th', value: 34.9 },
  ],
  rainfall_event: [
    { key: 'low', label: 'Low', percentile: '25th', value: 49.1 },
    { key: 'medium', label: 'Medium', percentile: '50th', value: 84.8 },
    { key: 'high', label: 'High', percentile: '75th', value: 96.4 },
    { key: 'severe', label: 'Severe', percentile: '95th', value: 99.9 },
  ],
};

function getSeverityLevels(trainingRanges, conditionType) {
  const defaults = DEFAULT_SEVERITY_LEVELS[conditionType] || DEFAULT_SEVERITY_LEVELS.equipment_down;
  const r = trainingRanges?.[conditionType];
  if (!r) return defaults;

  const lowVal = r.severity_levels?.low ?? r.severity_p25_pct ?? defaults[0].value;
  const medVal = r.severity_levels?.medium ?? r.severity_p50_pct ?? defaults[1].value;
  const highVal = r.severity_levels?.high ?? r.severity_p75_pct ?? defaults[2].value;
  const sevVal = r.severity_levels?.severe ?? r.severity_p95_pct ?? defaults[3].value;

  return [
    { key: 'low', label: 'Low', percentile: '25th', value: Number(lowVal) },
    { key: 'medium', label: 'Medium', percentile: '50th', value: Number(medVal) },
    { key: 'high', label: 'High', percentile: '75th', value: Number(highVal) },
    { key: 'severe', label: 'Severe', percentile: '95th', value: Number(sevVal) },
  ];
}

function getActiveSeverityLevel(levels, severityValue) {
  if (severityValue == null) return levels[1]; // default medium
  let closest = levels[0];
  let minDiff = Math.abs(levels[0].value - severityValue);
  for (const lvl of levels) {
    const diff = Math.abs(lvl.value - severityValue);
    if (diff < minDiff) {
      minDiff = diff;
      closest = lvl;
    }
  }
  return closest;
}

function makeCondition(overrides = {}) {
  const type = overrides.type || 'equipment_down';
  const defaultSeverity = DEFAULT_SEVERITY_LEVELS[type]?.[1]?.value ?? 1.4;
  const defaultDuration = type === 'rainfall_event' ? 14 : type === 'delay_blasting' ? 7 : 1;
  return { id: Date.now() + Math.random(), type, equipment: 'dragline_1', severity: defaultSeverity, duration: defaultDuration, ...overrides };
}

function formatRangeHint(ranges, conditionType) {
  if (!ranges) return null;
  const r = ranges[conditionType];
  if (!r) return null;

  let severityHint;
  if (r.severity_p25_pct != null && r.severity_p75_pct != null) {
    severityHint = `Typical: ${r.severity_p25_pct}–${r.severity_p75_pct}% (full range: ${r.severity_min_pct}–${r.severity_max_pct}%)`;
  } else {
    severityHint = `${r.severity_min_pct}–${r.severity_max_pct}%`;
  }

  let durationHint;
  if (r.duration_p25_days != null && r.duration_p75_days != null) {
    durationHint = `Typical: ${r.duration_p25_days}–${r.duration_p75_days}d (full range: ${r.duration_min_days}–${r.duration_max_days}d)`;
  } else if (r.duration_min_days != null && r.duration_max_days != null) {
    durationHint = `${r.duration_min_days}–${r.duration_max_days} days`;
  }
  if (conditionType === 'rainfall_event' && r.monsoon_months) {
    durationHint = `${durationHint} (peak: ${r.monsoon_months})`;
  }

  const events = r.event_count != null ? ` · ${r.event_count} events` : '';
  return { rawRange: r, severityHint, durationHint, events, isSynthetic: ranges.data_source === 'synthetic' };
}

function ConditionCard({ condition, index, onChange, onRemove, canRemove, trainingRanges, oodStatus }) {
  const typeInfo = CONDITION_TYPES.find((t) => t.value === condition.type) || CONDITION_TYPES[0];
  const TypeIcon = typeInfo.icon;
  const hint = formatRangeHint(trainingRanges, condition.type);
  const r = hint?.rawRange;

  const levels = getSeverityLevels(trainingRanges, condition.type);
  const activeLevel = getActiveSeverityLevel(levels, condition.severity);

  // State A: Outside full min/max observed in training data (strong warning)
  const isSeverityOutOfRange = r && condition.severity != null && (condition.severity < r.severity_min_pct || condition.severity > r.severity_max_pct);
  const isDurationOutOfRange = r && condition.duration != null && (condition.duration < r.duration_min_days || condition.duration > r.duration_max_days);
  const isConditionOutOfRange = isSeverityOutOfRange || isDurationOutOfRange || Boolean(oodStatus?.out_of_distribution);

  // State B: Inside full range but outside IQR (atypical / uncommon - neutral info)
  const isSeverityUncommon = r && condition.severity != null && !isSeverityOutOfRange && (
    (r.severity_p25_pct != null && condition.severity < r.severity_p25_pct) ||
    (r.severity_p75_pct != null && condition.severity > r.severity_p75_pct)
  );
  const severityUncommonDirection = (r?.severity_p25_pct != null && condition.severity < r.severity_p25_pct) ? 'below' : 'above';

  const isDurationUncommon = r && condition.duration != null && !isDurationOutOfRange && (
    (r.duration_p25_days != null && condition.duration < r.duration_p25_days) ||
    (r.duration_p75_days != null && condition.duration > r.duration_p75_days)
  );
  const durationUncommonDirection = (r?.duration_p25_days != null && condition.duration < r.duration_p25_days) ? 'below' : 'above';

  const isConditionUncommon = !isConditionOutOfRange && (isSeverityUncommon || isDurationUncommon);

  const handleTypeChange = (newType) => {
    const currentLevels = getSeverityLevels(trainingRanges, condition.type);
    const currentActive = getActiveSeverityLevel(currentLevels, condition.severity);
    const newLevels = getSeverityLevels(trainingRanges, newType);
    const targetLevel = newLevels.find((l) => l.key === currentActive.key) || newLevels[1];

    let newDuration = condition.duration;
    const newR = trainingRanges?.[newType];
    if (newR) {
      if (newDuration < newR.duration_min_days) {
        newDuration = Math.round(newR.duration_p50_days || newR.duration_min_days);
      } else if (newDuration > newR.duration_max_days) {
        newDuration = Math.round(newR.duration_p75_days || newR.duration_max_days);
      }
    }
    onChange({
      ...condition,
      type: newType,
      severity: targetLevel.value,
      duration: newDuration,
    });
  };

  return (
    <div className={`condition-card ${isConditionOutOfRange ? 'condition-card-ood' : isConditionUncommon ? 'condition-card-uncommon' : ''}`} data-testid={`condition-card-${index}`}>
      <div className="condition-header">
        <div className="condition-number">
          <TypeIcon size={13} />
          <span>Condition {index + 1}</span>
          {isConditionOutOfRange && (
            <span className="pill warn small" style={{ fontSize: 9, padding: '2px 6px', display: 'inline-flex', alignItems: 'center', gap: 4 }} title="Parameters exceed validated training distribution" data-testid={`pill-ood-${index}`}>
              <AlertTriangle size={10} /> Out of bounds
            </span>
          )}
          {isConditionUncommon && (
            <span className="pill neutral small" style={{ fontSize: 9, padding: '2px 6px', display: 'inline-flex', alignItems: 'center', gap: 4 }} title="Parameters are within full dataset range but outside typical IQR" data-testid={`pill-uncommon-${index}`}>
              <Info size={10} /> Atypical input
            </span>
          )}
        </div>
        {canRemove && (
          <button className="btn ghost small condition-remove" onClick={onRemove} title="Remove condition" data-testid={`button-remove-condition-${index}`}>
            <Trash2 size={13} />
          </button>
        )}
      </div>
      <div className="condition-body">
        <div className="form-grid">
          <div className="field">
            <label>Condition type</label>
            <select className="select" value={condition.type} onChange={(e) => handleTypeChange(e.target.value)} data-testid={`select-condition-type-${index}`}>
              {CONDITION_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Affected equipment / area</label>
            <select className="select" value={condition.equipment} onChange={(e) => onChange({ ...condition, equipment: e.target.value })} data-testid={`select-condition-equipment-${index}`}>
              {EQUIPMENT_AREAS.map((eq) => <option key={eq.value} value={eq.value}>{eq.label}</option>)}
            </select>
          </div>
          <div className="field severity-field">
            <div className="severity-control-wrap">
              <div className="severity-header-row">
                <label>Severity / magnitude</label>
                <span className="severity-current-badge" data-testid={`severity-badge-${index}`}>
                  <strong>{activeLevel.label}</strong> · {condition.severity != null ? `${condition.severity}%` : `${activeLevel.value}%`}
                </span>
              </div>
              <div className="severity-segmented-group" role="group" aria-label="Severity level" data-testid={`segmented-severity-${index}`}>
                {levels.map((lvl) => {
                  const isSelected = activeLevel.key === lvl.key;
                  return (
                    <button
                      key={lvl.key}
                      type="button"
                      className={`severity-seg-btn ${isSelected ? 'active' : ''}`}
                      onClick={() => onChange({ ...condition, severity: lvl.value })}
                      data-testid={`btn-severity-${lvl.key}-${index}`}
                      aria-pressed={isSelected}
                    >
                      <span className="seg-label">{lvl.label}</span>
                      <span className="seg-pct">{lvl.value}%</span>
                    </button>
                  );
                })}
              </div>
            </div>
            {hint?.severityHint && (
              <div className="condition-range-hint" data-testid={`hint-severity-${index}`}>
                {hint.isSynthetic ? 'Training data bounds: ' : 'Historical range: '}{hint.severityHint}{hint.events}
              </div>
            )}
            {isSeverityOutOfRange && (
              <div className="condition-ood-warning" data-testid={`warning-severity-${index}`}>
                <AlertTriangle size={11} />
                <span>This severity is outside the range the model was validated on ({r.severity_min_pct}–{r.severity_max_pct}%) — treat results with extra caution.</span>
              </div>
            )}
            {isSeverityUncommon && (
              <div className="condition-uncommon-info" data-testid={`info-severity-${index}`}>
                <Info size={11} />
                <span>Less common in training data ({severityUncommonDirection} typical range {r.severity_p25_pct}–{r.severity_p75_pct}%) — prediction may be less precise.</span>
              </div>
            )}
          </div>
          <div className="field">
            <label>Duration</label>
            <div className="slider-row">
              <input type="range" min="1" max="30" value={condition.duration} onChange={(e) => onChange({ ...condition, duration: Number(e.target.value) })} className="sim-slider" data-testid={`slider-duration-${index}`} />
              <span className="slider-value">{condition.duration}d</span>
            </div>
            {hint?.durationHint && (
              <div className="condition-range-hint" data-testid={`hint-duration-${index}`}>
                {hint.isSynthetic ? 'Training data bounds: ' : 'Historical range: '}{hint.durationHint}
              </div>
            )}
            {isDurationOutOfRange && (
              <div className="condition-ood-warning" data-testid={`warning-duration-${index}`}>
                <AlertTriangle size={11} />
                <span>This duration is outside the range the model was validated on ({r.duration_min_days}–{r.duration_max_days} days) — treat results with extra caution.</span>
              </div>
            )}
            {isDurationUncommon && (
              <div className="condition-uncommon-info" data-testid={`info-duration-${index}`}>
                <Info size={11} />
                <span>Less common in training data ({durationUncommonDirection} typical range {r.duration_p25_days}–{r.duration_p75_days} days) — prediction may be less precise.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


// ── Simulator: safe display & derived data helpers ──
const safeNum = (v) => (v != null && !isNaN(Number(v))) ? Number(v) : null;
const safeDisplay = (v, fmt) => { const n = safeNum(v); return n != null ? (fmt ? fmt(n) : String(n)) : '—'; };
const safeDelta = (a, b) => { const na = safeNum(a), nb = safeNum(b); return (na != null && nb != null) ? na - nb : null; };
const SITE_NAMES = { 1: 'Balaghat', 2: 'Nagpur', 3: 'Bhandara' };
const SIM_HISTORY_KEY = 'oresight-sim-history';
const MAX_SIM_HISTORY = 20;

function loadSimHistory() {
  try { return JSON.parse(localStorage.getItem(SIM_HISTORY_KEY)) || []; }
  catch { return []; }
}
function saveSimHistory(runs) {
  try { localStorage.setItem(SIM_HISTORY_KEY, JSON.stringify(runs.slice(0, MAX_SIM_HISTORY))); }
  catch { /* quota exceeded */ }
}

function generateHorizonChart(before, after, horizon, uncertainty) {
  const bDaily = safeNum(before?.production_forecast_tonnes);
  const aDaily = safeNum(after?.production_forecast_tonnes);
  if (bDaily == null || aDaily == null || horizon < 1) return [];
  const prodUnc = safeNum(uncertainty?.production_impact_uncertainty_tonnes);
  const dailyUncertainty = prodUnc != null ? prodUnc : null;

  return Array.from({ length: Math.min(horizon, 30) }, (_, i) => {
    const bVal = Math.round(bDaily + Math.sin(i * 0.7) * bDaily * 0.04);
    const aVal = Math.round(aDaily + Math.sin(i * 0.9 + 1) * aDaily * 0.05);
    const uVal = dailyUncertainty != null ? Math.round(dailyUncertainty) : Math.round(aDaily * 0.05);
    const lower = Math.max(0, aVal - uVal);
    const upper = aVal + uVal;
    return {
      day: `Day ${i + 1}`,
      baseline: bVal,
      scenario: aVal,
      scenarioUpper: upper,
      scenarioLower: lower,
      scenarioBand: [lower, upper],
    };
  });
}

function buildCausalSteps(result) {
  const path = result?.affected_graph_path;
  if (!path?.length) return null;
  const nodeMap = {};
  (result.updated_graph?.nodes || []).forEach((n) => { nodeMap[n.id] = n; });
  return path.map((id) => {
    const node = nodeMap[id];
    return {
      id,
      label: node?.label || id.replace(/^sim_/, '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      type: node?.type || 'Scenario',
    };
  });
}

function deriveKPIs(result, conditions, horizon) {
  if (!result) return [];
  const prodBefore = safeNum(result.before?.production_forecast_tonnes);
  const prodAfter = safeNum(result.after?.production_forecast_tonnes);
  const riskBefore = safeNum(result.before?.risk_score);
  const riskAfter = safeNum(result.after?.risk_score);
  const confBefore = safeNum(result.before?.reserve_confidence);
  const confAfter = safeNum(result.after?.reserve_confidence);
  const prodDelta = safeDelta(prodAfter, prodBefore);
  const totalDowntime = conditions.reduce((sum, c) => sum + (c.duration || 0), 0);

  const unc = result.uncertainty || null;
  const prodUnc = unc ? safeNum(unc.production_impact_uncertainty_tonnes) : null;
  const riskUnc = unc ? safeNum(unc.risk_uncertainty) : null;
  const confUnc = unc ? safeNum(unc.reserve_confidence_uncertainty) : null;
  const downtimeUnc = unc ? safeNum(unc.downtime_uncertainty_days) : null;

  const isOOD = Boolean(result.out_of_distribution);

  const prodUncFormatted = prodUnc != null
    ? (prodUnc < 10 ? prodUnc.toFixed(1) : Math.round(prodUnc).toLocaleString())
    : null;

  const prodValStr = prodDelta != null
    ? `${prodDelta > 0 ? '+' : ''}${prodDelta.toLocaleString()} t${prodUncFormatted != null ? ` (±${prodUncFormatted} t)` : ''}`
    : '—';

  const riskValStr = riskAfter != null
    ? `${percent(riskAfter)}${riskUnc != null ? ` (±${(riskUnc * 100).toFixed(1)}%)` : ''}`
    : '—';

  const confValStr = confAfter != null
    ? `${percent(confAfter, 1)}${confUnc != null ? ` (±${(confUnc * 100).toFixed(1)}%)` : ''}`
    : '—';

  const downtimeValStr = `${totalDowntime}d${downtimeUnc != null ? ` (±${downtimeUnc}d)` : ''}`;

  return [
    { label: 'Production impact', value: prodValStr, sub: prodBefore != null ? `${prodBefore.toLocaleString()} → ${safeDisplay(prodAfter, (v) => v.toLocaleString())} t` : null, trend: prodDelta, icon: BarChart3, isOOD },
    { label: 'Operational risk', value: riskValStr, sub: riskBefore != null ? `was ${percent(riskBefore)}` : null, trend: safeDelta(riskBefore, riskAfter), icon: ShieldCheck, isOOD },
    { label: 'Reserve confidence', value: confValStr, sub: confBefore != null ? `was ${percent(confBefore, 1)}` : null, trend: safeDelta(confAfter, confBefore), icon: Gauge, isOOD },
    { label: 'Est. downtime', value: downtimeValStr, sub: `${conditions.length} condition${conditions.length !== 1 ? 's' : ''} · ${horizon}d horizon`, trend: null, icon: AlertCircle, isOOD },
  ];
}

function deriveKeyImpacts(result) {
  if (!result) return [];
  const impacts = [];
  const prodDelta = safeDelta(safeNum(result.after?.production_forecast_tonnes), safeNum(result.before?.production_forecast_tonnes));
  const riskDelta = safeDelta(safeNum(result.after?.risk_score), safeNum(result.before?.risk_score));
  const confDelta = safeDelta(safeNum(result.after?.reserve_confidence), safeNum(result.before?.reserve_confidence));
  if (prodDelta != null) {
    const base = safeNum(result.before?.production_forecast_tonnes);
    const pct = base ? ((prodDelta / base) * 100).toFixed(1) : null;
    impacts.push({ label: 'Production forecast', description: `${prodDelta >= 0 ? 'Increases' : 'Decreases'} by ${Math.abs(prodDelta).toLocaleString()} tonnes${pct != null ? ` (${prodDelta > 0 ? '+' : ''}${pct}%)` : ''}`, positive: prodDelta >= 0, magnitude: Math.abs(prodDelta) });
  }
  if (riskDelta != null) impacts.push({ label: 'Risk exposure', description: `${riskDelta <= 0 ? 'Decreases' : 'Increases'} from ${percent(result.before.risk_score)} to ${percent(result.after.risk_score)}`, positive: riskDelta <= 0, magnitude: Math.abs(riskDelta) * 1000 });
  if (confDelta != null) impacts.push({ label: 'Reserve confidence', description: `${confDelta >= 0 ? 'Improves' : 'Declines'} from ${percent(result.before.reserve_confidence, 1)} to ${percent(result.after.reserve_confidence, 1)}`, positive: confDelta >= 0, magnitude: Math.abs(confDelta) * 1000 });
  return impacts.sort((a, b) => b.magnitude - a.magnitude);
}

function buildInterpretation(result, conditions, siteName, horizon) {
  if (!result) return null;
  const parts = [];
  const prodDelta = safeDelta(safeNum(result.after?.production_forecast_tonnes), safeNum(result.before?.production_forecast_tonnes));
  const riskBefore = safeNum(result.before?.risk_score);
  const riskAfter = safeNum(result.after?.risk_score);
  const confAfter = safeNum(result.after?.reserve_confidence);
  if (prodDelta != null) parts.push(`Under this ${conditions.length}-condition scenario at ${siteName}, production is projected to ${prodDelta >= 0 ? 'increase' : 'decrease'} by ${Math.abs(prodDelta).toLocaleString()} tonnes over a ${horizon}-day horizon.`);
  if (riskBefore != null && riskAfter != null) parts.push(`Operational risk ${riskAfter < riskBefore ? 'decreases' : 'increases'} from ${percent(riskBefore)} to ${percent(riskAfter)}.`);
  if (confAfter != null) parts.push(`Reserve confidence under this scenario is ${percent(confAfter, 1)}.`);
  if (result.out_of_distribution) {
    parts.push('⚠️ Model validation warning: At least one scenario condition has severity or duration exceeding the training distribution. The model is extrapolating beyond historical bounds; predictions carry elevated uncertainty.');
  } else {
    parts.push('Results are directional estimates and should be validated against field conditions before committing to a plan change.');
  }
  return parts.join(' ');
}


function SimulatorPage() {
  const sites = useSites();
  const [params] = useSearchParams();
  const [site, setSite] = useState(Number(params.get('site_id')) || 1);
  const [horizon, setHorizon] = useState(Number(params.get('duration_days')) || 7);
  const initialType = isValidScenarioType(params.get('scenario_type')) ? params.get('scenario_type') : 'equipment_down';
  const [conditions, setConditions] = useState([makeCondition({ type: initialType })]);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);
  const [history, setHistory] = useState(() => loadSimHistory());
  const [historyOpen, setHistoryOpen] = useState(false);
  const [compareIds, setCompareIds] = useState([]);
  const [trainingRanges, setTrainingRanges] = useState(null);
  const [siteProdVariance, setSiteProdVariance] = useState(null);
  useEffect(() => { api.getTrainingRanges().then(setTrainingRanges); }, []);

  useEffect(() => {
    let active = true;
    api.getProduction(site, 14).then((recs) => {
      if (!active) return;
      const variances = recs?.map((r) => r.variance_pct).filter((v) => v != null) || [];
      const avgVar = variances.length ? variances.reduce((a, b) => a + b, 0) / variances.length : 0;
      setSiteProdVariance(Math.round(avgVar * 10) / 10);
    }).catch(() => {});
    return () => { active = false; };
  }, [site]);

  const addCondition = () => setConditions((prev) => [...prev, makeCondition()]);
  const removeCondition = (id) => setConditions((prev) => prev.filter((c) => c.id !== id));
  const updateCondition = (id, updated) => setConditions((prev) => prev.map((c) => c.id === id ? updated : c));
  const resetScenario = () => { setConditions([makeCondition()]); setResult(null); setRunError(null); };
  const siteName = SITE_NAMES[site] || `Site ${site}`;

  const runSimulation = async () => {
    setRunning(true);
    setRunError(null);
    try {
      const condsPayload = conditions.map((c) => ({
        type: c.type,
        equipment: c.equipment,
        severity: Number(c.severity),
        duration: Number(c.duration),
      }));
      const currentSiteObj = sites.find((s) => s.id === site);
      const currentConfidence = currentSiteObj?.avg_reserve_confidence ?? null;
      const siteContext = {
        reserve_confidence: currentConfidence,
        production_variance: siteProdVariance,
        active_conditions_count: conditions.length,
      };
      const value = await api.simulate({
        scenario_type: conditions[0]?.type || 'equipment_down',
        site_id: site,
        duration_days: horizon,
        severity: conditions[0]?.severity,
        conditions: condsPayload,
        site_context: siteContext,
        current_reserve_confidence: currentConfidence,
        recent_production_variance: siteProdVariance,
      });
      setResult(value);

      const run = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        site,
        siteName,
        conditions: condsPayload,
        horizon,
        result: {
          before: value.before,
          after: value.after,
          affected_graph_path: value.affected_graph_path,
          out_of_distribution: value.out_of_distribution,
        },
      };
      const updated = [run, ...history].slice(0, MAX_SIM_HISTORY);
      setHistory(updated);
      saveSimHistory(updated);
    } catch (err) {
      setRunError(err?.detail || err?.message || 'Simulation failed');
    } finally { setRunning(false); }
  };

  const rerunFromHistory = (run) => { setSite(run.site); setHorizon(run.horizon); setConditions(run.conditions.map((c) => makeCondition(c))); setResult(null); setRunError(null); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  const toggleCompare = (id) => setCompareIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : prev.length < 2 ? [...prev, id] : [prev[1], id]);
  const deleteHistoryRun = (id) => { const updated = history.filter((r) => r.id !== id); setHistory(updated); saveSimHistory(updated); setCompareIds((prev) => prev.filter((x) => x !== id)); };
  const clearHistory = () => { setHistory([]); saveSimHistory([]); setCompareIds([]); };

  const kpis = useMemo(() => deriveKPIs(result, conditions, horizon), [result, conditions, horizon]);
  const chartData = useMemo(() => result ? generateHorizonChart(result.before, result.after, horizon, result.uncertainty) : [], [result, horizon]);
  const keyImpacts = useMemo(() => deriveKeyImpacts(result), [result]);
  const interpretation = useMemo(() => buildInterpretation(result, conditions, siteName, horizon), [result, conditions, siteName, horizon]);
  const causalSteps = useMemo(() => buildCausalSteps(result), [result]);
  const compareA = compareIds[0] != null ? history.find((r) => r.id === compareIds[0]) : null;
  const compareB = compareIds[1] != null ? history.find((r) => r.id === compareIds[1]) : null;
  const resultReady = result && !running && !runError;

  return <main className="page">
    <div className="page-head">
      <div>
        <div className="eyebrow">Scenario simulator · decision rehearsal</div>
        <h1>Build your scenario. See the trade-off.</h1>
        <p className="subhead">A model-backed what-if surface for shift planning. Stack multiple conditions to stress-test the plan.</p>
      </div>
      <div className="filter-row">
        <button className="btn" onClick={resetScenario} data-testid="button-reset-scenario"><RotateCcw size={13} /> Reset scenario</button>
      </div>
    </div>

    {/* Scenario summary strip */}
    <div className="sim-summary-strip">
      <div className="sim-summary-left">
        <span className="sim-summary-count">{conditions.length}</span>
        <span>active condition{conditions.length !== 1 ? 's' : ''}</span>
        <span className="sim-summary-dot">·</span>
        <span>{horizon}-day horizon</span>
      </div>
      <div className="sim-summary-right">
        <div className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          <label style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 600 }}>Site</label>
          <select className="select" value={site} onChange={(e) => setSite(Number(e.target.value))} data-testid="select-simulation-site">
            <option value="1">Balaghat</option>
            <option value="2">Nagpur</option>
            <option value="3">Bhandara</option>
          </select>
        </div>
        <div className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8, minWidth: 180 }}>
          <label style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 600, whiteSpace: 'nowrap' }}>Horizon</label>
          <input type="range" min="1" max="30" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} className="sim-slider" data-testid="input-simulation-duration" />
          <span className="slider-value">{horizon}d</span>
        </div>
      </div>
    </div>

    <div className="two-col">
      {/* Left: Condition builder */}
      <section className="section-stack">
        <div className="card section-card">
          <div className="card-head">
            <div>
              <div className="card-title">Scenario conditions</div>
              <div className="card-kicker">add multiple levers to stress-test your plan</div>
            </div>
            <SlidersHorizontal size={16} />
          </div>
          <div className="condition-list">
            {conditions.map((condition, i) => (
              <ConditionCard
                key={condition.id}
                condition={condition}
                index={i}
                onChange={(updated) => updateCondition(condition.id, updated)}
                onRemove={() => removeCondition(condition.id)}
                canRemove={conditions.length > 1}
                trainingRanges={trainingRanges}
                oodStatus={result?.conditions_ood?.[i]}
              />
            ))}
          </div>
          <button className="btn sim-add-btn" onClick={addCondition} data-testid="button-add-condition">
            <Plus size={14} /> Add condition
          </button>
        </div>
        <button className="btn primary sim-run-btn" onClick={runSimulation} disabled={running} data-testid="button-run-simulation">
          {running ? <RefreshCw size={14} className="spin" /> : <Zap size={14} />}
          {running ? 'Running model…' : `Run simulation · ${conditions.length} condition${conditions.length !== 1 ? 's' : ''}`}
        </button>
      </section>

      {/* Right: Results panel */}
      <section className="card section-card">
        <div className="card-head">
          <div>
            <div className="card-title">Simulation results</div>
            <div className="card-kicker">impact snapshot · {horizon}-day horizon</div>
          </div>
          {running && <span className="pill warn"><RefreshCw size={11} className="spin" /> Running</span>}
          {!running && runError && <span className="pill critical"><AlertCircle size={11} /> Error</span>}
          {resultReady && (
            result.out_of_distribution
              ? <span className="pill warn" data-testid="pill-sim-ood"><AlertTriangle size={11} /> Out of distribution</span>
              : <span className="pill good"><Check size={11} /> Validated range</span>
          )}
        </div>

        {running && <LoadingCard lines={6} />}

        {!running && runError && (
          <div className="error-box">
            <strong>Simulation failed</strong>
            <p className="subhead">{runError}</p>
            <button className="btn small" onClick={runSimulation} style={{ marginTop: 10 }} data-testid="button-retry-simulation"><RefreshCw size={13} /> Retry</button>
          </div>
        )}

        {resultReady && <div className="section-stack">
          {result.out_of_distribution && (
            <div className="sim-ood-banner" data-testid="sim-ood-banner">
              <AlertTriangle size={16} className="sim-ood-banner-icon" />
              <div className="sim-ood-banner-content">
                <div className="sim-ood-banner-title">Out-of-Distribution Warning</div>
                <div className="sim-ood-banner-desc">
                  {result.out_of_distribution_warning || 'One or more condition parameters exceed the range the model was validated on. Projections are extrapolations beyond historical bounds — treat results with extra caution.'}
                </div>
              </div>
            </div>
          )}

          <div className="sim-kpi-grid">
            {kpis.map((kpi) => (
              <div className={`sim-kpi-card ${kpi.isOOD ? 'ood-card' : ''}`} key={kpi.label} data-testid={`kpi-card-${kpi.label.toLowerCase().replace(/\s+/g, '-')}`}>
                <div className="metric-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span><kpi.icon size={10} style={{ verticalAlign: 'middle', marginRight: 4 }} />{kpi.label}</span>
                  {kpi.isOOD && (
                    <span className="kpi-ood-badge" title="Input condition is outside model validation bounds — projection is an extrapolation">
                      <AlertTriangle size={9} />
                      <span>Caution</span>
                    </span>
                  )}
                </div>
                <div className="metric-value">{kpi.value}</div>
                <div className="stat-foot">
                  {kpi.trend != null && <span className={kpi.trend > 0 ? 'trend-up' : kpi.trend < 0 ? 'trend-down' : ''}>{kpi.trend > 0 ? <ArrowUpRight size={10} /> : <ArrowDownRight size={10} />}</span>}
                  {kpi.sub && <span>{kpi.sub}</span>}
                  {kpi.isOOD && <span className="ood-sub-flag">⚠️ Extrapolated</span>}
                </div>
              </div>
            ))}
          </div>

          {keyImpacts.length > 0 && <div className="sim-impacts">
            <div className="card-title" style={{ fontSize: 11, marginBottom: 8 }}>Key impacts</div>
            {keyImpacts.map((impact) => (
              <div className="sim-impact-item" key={impact.label}>
                <div className={`sim-impact-marker ${impact.positive ? 'positive' : 'negative'}`} />
                <div><div className="sim-impact-label">{impact.label}</div><div className="sim-impact-desc">{impact.description}</div></div>
              </div>
            ))}
          </div>}

          {interpretation && (
            <div className={`sim-interpretation ${result.out_of_distribution ? 'ood' : ''}`} data-testid="sim-interpretation">
              {result.out_of_distribution ? <AlertTriangle size={13} style={{ flexShrink: 0, marginTop: 1, color: 'hsl(38 92% 50%)' }} /> : <CircleHelp size={13} style={{ flexShrink: 0, marginTop: 1 }} />}
              <span>{interpretation}</span>
            </div>
          )}

          <div className="sim-actions">
            <button className="btn small" onClick={runSimulation} data-testid="button-rerun-simulation"><RefreshCw size={12} /> Run again</button>

            {history.length >= 2 && <button className="btn small" onClick={() => setHistoryOpen(true)} data-testid="button-compare-runs"><BarChart3 size={12} /> Compare runs</button>}
            <Link className="btn small" to={`/site/${site}?tab=graph`}>Open graph <ChevronRight size={12} /></Link>
          </div>
        </div>}

        {!running && !runError && !result && <EmptyState icon={GitBranch} title="No scenario run yet">Stack conditions on the left and run the model to compare plan outcomes.</EmptyState>}
      </section>
    </div>

    {/* ── Below two-col: detailed results sections ── */}
    {resultReady && <>
      {/* Baseline vs Scenario chart */}
      <section className="card section-card" style={{ marginTop: 14 }}>
        <div className="card-head">
          <div>
            <div className="card-title">Baseline vs scenario</div>
            <div className="card-kicker">daily production forecast · {horizon}-day horizon</div>
          </div>
          <div className="legend">
            <span><i />Scenario</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'hsl(var(--muted-foreground))' }}>
              <span style={{ width: 10, height: 10, background: 'hsl(var(--primary) / 0.25)', borderRadius: 2, display: 'inline-block' }} />
              Confidence band (± residual error)
            </span>
            <span><i className="target" />Baseline</span>
          </div>
        </div>
        {chartData.length > 0 ? (
          <div style={{ height: 190 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={45} domain={['dataMin - 20', 'auto']} />
                <Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', fontSize: 11 }} />
                <Area type="monotone" dataKey="scenarioBand" stroke="none" fill="hsl(var(--primary) / 0.16)" name="Confidence band (± residual error)" />
                <Area type="monotone" dataKey="baseline" stroke="hsl(var(--accent) / .38)" fill="hsl(var(--accent) / .07)" strokeWidth={2} name="Baseline" />
                <Area type="monotone" dataKey="scenario" stroke="hsl(var(--primary))" fill="none" strokeWidth={2} name="Scenario" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : <EmptyState title="Chart unavailable">Insufficient data to render the horizon chart.</EmptyState>}
      </section>

      {/* Timeline + Causal chain */}
      <div className="two-col" style={{ marginTop: 14 }}>
        <section className="card section-card">
          <div className="card-head">
            <div>
              <div className="card-title">Impact timeline</div>
              <div className="card-kicker">condition coverage across {horizon}-day horizon</div>
            </div>
            <Activity size={16} />
          </div>
          <div className="sim-timeline-wrap">
            <div className="sim-timeline-axis">
              <div />
              <div className="sim-timeline-ticks">
                {Array.from({ length: Math.min(horizon + 1, 8) }, (_, i) => {
                  const day = Math.round((i / Math.min(horizon, 7)) * horizon);
                  return <span key={i}>D{day}</span>;
                })}
              </div>
            </div>
            {conditions.map((c, i) => {
              const typeLabel = CONDITION_TYPES.find((t) => t.value === c.type)?.label || c.type;
              const widthPct = Math.min(100, Math.max(5, (c.duration / horizon) * 100));
              return (
                <div className="sim-timeline-row" key={c.id || i}>
                  <div className="sim-timeline-label">{typeLabel}</div>
                  <div className="sim-timeline-track">
                    <div className="sim-timeline-bar" style={{ width: `${widthPct}%` }}>{c.duration}d</div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="card section-card">
          <div className="card-head">
            <div>
              <div className="card-title">Why did this happen?</div>
              <div className="card-kicker">causal path from scenario model</div>
            </div>
            <GitBranch size={16} />
          </div>
          {causalSteps && causalSteps.length > 0 ? <div className="sim-causal-chain">
            {causalSteps.map((step, i) => (
              <div key={step.id}>
                <div className="sim-causal-step">
                  <span className="sim-causal-step-label">{step.label}</span>
                  <span className="sim-causal-step-type">{step.type}</span>
                </div>
                {i < causalSteps.length - 1 && <div className="sim-causal-arrow">↓</div>}
              </div>
            ))}
            <div className="alert-strip" style={{ marginTop: 14 }}>
              <GitBranch size={13} />
              <span>Affected path: <b>{result.affected_graph_path.join(' → ')}</b></span>
            </div>
            <Link className="btn small" to={`/site/${site}?tab=graph`} style={{ marginTop: 10 }}>View full causal graph <ChevronRight size={12} /></Link>
          </div> : <EmptyState icon={GitBranch} title="Causal path unavailable">Causal path unavailable for this scenario.</EmptyState>}
        </section>
      </div>
    </>}

    {/* ── Simulation history ── */}
    {history.length > 0 && (
      <section className="card section-card" style={{ marginTop: 14 }}>
        <div className="sim-history-toggle" onClick={() => setHistoryOpen(!historyOpen)} data-testid="button-toggle-history">
          <div>
            <div className="card-title">Simulation history</div>
            <div className="card-kicker">{history.length} previous run{history.length !== 1 ? 's' : ''} · select two to compare</div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {compareIds.length === 2 && <span className="pill good"><Check size={10} /> Ready to compare</span>}
            <ChevronRight size={16} style={{ transform: historyOpen ? 'rotate(90deg)' : 'none', transition: 'transform .2s' }} />
          </div>
        </div>
        {historyOpen && <>
          {compareA && compareB && (
            <div className="sim-compare-wrap" style={{ marginTop: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <div className="card-title" style={{ fontSize: 11 }}>Run comparison</div>
                <button className="btn ghost small" onClick={() => setCompareIds([])}><X size={11} /> Clear</button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Metric</th><th>Run #{history.findIndex((r) => r.id === compareA.id) + 1}</th><th>Run #{history.findIndex((r) => r.id === compareB.id) + 1}</th><th>Difference</th></tr></thead>
                  <tbody>
                    {[
                      { label: 'Production impact', a: safeDelta(compareA.result?.after?.production_forecast_tonnes, compareA.result?.before?.production_forecast_tonnes), b: safeDelta(compareB.result?.after?.production_forecast_tonnes, compareB.result?.before?.production_forecast_tonnes), fmt: (v) => `${v > 0 ? '+' : ''}${v.toLocaleString()} t` },
                      { label: 'Risk change', a: safeDelta(compareA.result?.after?.risk_score, compareA.result?.before?.risk_score), b: safeDelta(compareB.result?.after?.risk_score, compareB.result?.before?.risk_score), fmt: (v) => percent(v) },
                      { label: 'Reserve Δ', a: safeDelta(compareA.result?.after?.reserve_confidence, compareA.result?.before?.reserve_confidence), b: safeDelta(compareB.result?.after?.reserve_confidence, compareB.result?.before?.reserve_confidence), fmt: (v) => percent(v) },
                    ].map(({ label, a, b, fmt }) => {
                      const diff = safeDelta(a, b);
                      return <tr key={label}><td><b>{label}</b></td><td className="mono">{safeDisplay(a, fmt)}</td><td className="mono">{safeDisplay(b, fmt)}</td><td className={`mono ${diff != null ? (diff > 0 ? 'trend-up' : diff < 0 ? 'trend-down' : '') : ''}`}>{safeDisplay(diff, fmt)}</td></tr>;
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          <div className="table-wrap" style={{ marginTop: compareA && compareB ? 0 : 14 }}>
            <table>
              <thead><tr><th style={{ width: 30 }}></th><th>Run</th><th>Time</th><th>Site</th><th>Conds</th><th>Horizon</th><th>Prod Δ</th><th>Risk Δ</th><th></th></tr></thead>
              <tbody>
                {history.map((run, i) => {
                  const prodDelta = safeDelta(run.result?.after?.production_forecast_tonnes, run.result?.before?.production_forecast_tonnes);
                  const riskDelta = safeDelta(run.result?.after?.risk_score, run.result?.before?.risk_score);
                  return <tr key={run.id} className={compareIds.includes(run.id) ? 'sim-compare-selected' : ''}>
                    <td><input type="checkbox" checked={compareIds.includes(run.id)} onChange={() => toggleCompare(run.id)} /></td>
                    <td className="mono">#{i + 1}</td>
                    <td className="mono">{new Date(run.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</td>
                    <td>{run.siteName}</td>
                    <td>{run.conditions?.length || 0}</td>
                    <td>{run.horizon}d</td>
                    <td className={`mono ${prodDelta != null ? (prodDelta > 0 ? 'trend-up' : 'trend-down') : ''}`}>{safeDisplay(prodDelta, (v) => `${v > 0 ? '+' : ''}${v.toLocaleString()} t`)}</td>
                    <td className={`mono ${riskDelta != null ? (riskDelta < 0 ? 'trend-up' : 'trend-down') : ''}`}>{safeDisplay(riskDelta, (v) => percent(v))}</td>
                    <td><div style={{ display: 'flex', gap: 4 }}><button className="btn ghost small" onClick={() => rerunFromHistory(run)} title="Rerun configuration"><RotateCcw size={11} /></button><button className="btn ghost small" onClick={() => deleteHistoryRun(run.id)} title="Delete run"><Trash2 size={11} /></button></div></td>
                  </tr>;
                })}
              </tbody>
            </table>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button className="btn small" onClick={clearHistory} data-testid="button-clear-history"><Trash2 size={11} /> Clear history</button>
          </div>
        </>}
      </section>
    )}
  </main>;
}

// Same hardcoded 3-site list every other Field Intake tab (Equipment,
// Production, Blasting) already uses — reused here rather than introducing
// a new site-fetching pattern for just the Notes tab.
const FIELD_INTAKE_SITE_OPTIONS = [
  { id: 1, name: 'Balaghat' },
  { id: 2, name: 'Nagpur' },
  { id: 3, name: 'Bhandara' },
];

function FieldIntakePage() {
  const { data, loading, error, retry } = useAsync(() => api.getFieldWorkspace(), []);
  // Same ?tab= pattern as SitePage, so Field Intake also survives a hard
  // refresh and back/forward navigation instead of always resetting to
  // "Equipment".
  const [searchParams, setSearchParams] = useSearchParams();
  const active = searchParams.get('tab') || 'equipment';
  const setActive = (next) => setSearchParams({ tab: next });
  const [equipmentRows, setEquipmentRows] = useState([]);
  const [note, setNote] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [searchedNotes, setSearchedNotes] = useState([]);
  // Defaults to Balaghat (site 1) — same site getFieldWorkspace() preloads
  // notes for, so the default view needs no extra round trip.
  const [noteSiteId, setNoteSiteId] = useState(FIELD_INTAKE_SITE_OPTIONS[0].id);
  const [toast, setToast] = useState('');
  useEffect(() => { if (data) setEquipmentRows(data.equipment); }, [data]);
  // Debounce, and trim before checking length: the backend rejects both an
  // empty `q` (min_length=1) and a whitespace-only one with a 400, and this
  // used to fire on first paint with q='' before the user had typed anything.
  useEffect(() => { const handle = setTimeout(() => setQuery(searchInput.trim()), 250); return () => clearTimeout(handle); }, [searchInput]);
  useEffect(() => {
    if (!data) return;
    // The workspace load already fetched site 1's notes for an empty query —
    // reuse that instead of re-querying when nothing has changed from the
    // default. Any other site, or a non-empty query, needs its own fetch.
    if (!query && noteSiteId === FIELD_INTAKE_SITE_OPTIONS[0].id) { setSearchedNotes(data.notes); return; }
    const loader = query ? api.searchSiteNotes(query, noteSiteId) : api.getSiteNotes(noteSiteId);
    loader.then(setSearchedNotes).catch(() => setSearchedNotes([]));
  }, [query, data, noteSiteId]);
  if (loading) return <main className="page"><LoadingCard lines={10} /></main>;
  if (error) return <main className="page"><ErrorState retry={retry} /></main>;
  const showToast = (message) => { setToast(message); setTimeout(() => setToast(''), 2600); };
  const onStatusChange = async (item, status) => { try { const updated = await api.updateEquipmentStatus(item.id, { status, status_reason: status === 'up' ? 'Returned to service from field intake' : 'Marked down from field intake' }); setEquipmentRows((rows) => rows.map((row) => row.id === item.id ? updated : row)); showToast(`${item.name} marked ${status}`); } catch (statusError) { showToast(statusError.status === 409 ? '409 conflict: equipment changed elsewhere; reload before retrying.' : statusError.detail || 'Status update failed'); } };
  const refetchEquipment = async () => { try { const fresh = await api.getFieldWorkspace(); setEquipmentRows(fresh.equipment); } catch { /* keep current rows; bulk summary already reflects per-item results */ } };
  const noteSiteName = FIELD_INTAKE_SITE_OPTIONS.find((s) => s.id === noteSiteId)?.name || 'the selected site';
  const saveNote = async () => {
    if (!note.trim()) { showToast('Validation: note text is required.'); return; }
    try {
      await api.createSiteNote({ site_id: noteSiteId, text: note });
      setNote('');
      showToast(`Note added to ${noteSiteName} field log`);
      // Refresh the visible list so the new note shows up immediately.
      const loader = query ? api.searchSiteNotes(query, noteSiteId) : api.getSiteNotes(noteSiteId);
      loader.then(setSearchedNotes).catch(() => {});
    } catch (noteError) {
      showToast(noteError.status === 409 ? '409 conflict: the note was updated elsewhere.' : noteError.detail || 'Note save failed');
    }
  };
  const notes = searchedNotes;
  return <main className="page"><div className="page-head"><div><div className="eyebrow">Field intake · operations loop</div><h1>Bring the shift into the model</h1><p className="subhead">Capture equipment status, production reality, geology documents, and the notes that explain the deviation.</p></div></div><div className="tabs">{['equipment', 'production', 'blasting', 'geology', 'notes'].map((item) => <button className={`tab ${active === item ? 'active' : ''}`} onClick={() => setActive(item)} key={item} data-testid={`tab-field-${item}`}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div>
    {['equipment', 'production', 'blasting', 'geology'].includes(active) && <ErrorBoundary resetKey={active} FallbackComponent={FieldIntakeTabFallback}><Suspense fallback={<LoadingCard lines={6} />}>
      {active === 'equipment' && <EquipmentTab equipmentRows={equipmentRows} setEquipmentRows={setEquipmentRows} onStatusChange={onStatusChange} showToast={showToast} refetchAll={refetchEquipment} />}
      {active === 'production' && <ProductionTab showToast={showToast} />}
      {active === 'blasting' && <BlastLogTab showToast={showToast} />}
      {active === 'geology' && <GeologyTab />}
    </Suspense></ErrorBoundary>}
    {active === 'notes' && <div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Site notes</div><div className="card-kicker">GET /site-notes/search · searchable field context</div></div><Search size={15} /></div><div className="filter-row" style={{ marginBottom: 10 }}><select className="select" value={noteSiteId} onChange={(e) => setNoteSiteId(Number(e.target.value))} data-testid="select-notes-site">{FIELD_INTAKE_SITE_OPTIONS.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></div><input className="input" value={searchInput} onChange={(e) => setSearchInput(e.target.value)} placeholder="Search notes by keyword" data-testid="input-search-notes" />{notes.length ? notes.map((item) => <div className="risk-item" key={item.id}><div className="risk-marker medium" /><div className="risk-item-main"><div className="risk-title">{item.text}</div><div className="risk-meta">{dateLabel(item.created_at)} · relevance {percent(item.relevance)}</div></div></div>) : <EmptyState icon={Search} title="No notes found" />}</section><section className="card section-card"><div className="card-title">Add shift note</div><p className="subhead">Notes are local preview writes and are attached to {noteSiteName} (site {noteSiteId}).</p><textarea className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Record a site observation…" style={{ width: '100%', marginTop: 14 }} data-testid="textarea-site-note" /><button className="btn primary" onClick={saveNote} style={{ marginTop: 10 }} data-testid="button-save-note"><Check size={13} /> Save note</button><div className="alert-strip" style={{ marginTop: 18 }}><CircleHelp size={15} /><span>Live API conflict responses (409) are shown inline so stale writes can be reviewed before retrying.</span></div></section></div>}
    {toast && <div className="toast">{toast}</div>}</main>;
}

function SettingsPage() {
  const sites = useSites();
  const { data, loading, error, retry } = useAsync(() => api.getSettingsWorkspace(), []);
  const [prefs, setPrefs] = useState(localPreferences);
  if (loading) return <main className="page"><LoadingCard lines={8} /></main>;
  if (error) return <main className="page"><ErrorState retry={retry} /></main>;
  return <main className="page"><div className="page-head"><div><div className="eyebrow">Settings · workspace controls</div><h1>Keep the room predictable</h1><p className="subhead">Local preferences and live service status. Admin controls are clearly separated from planning decisions.</p></div></div><div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Local preferences</div><div className="card-kicker">stored on this device only</div></div><SettingsIcon size={16} /></div><div className="field"><label>Workspace density</label><select className="select" value={prefs.density} onChange={(e) => setPrefs({ ...prefs, density: e.target.value })} data-testid="select-density"><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></div><div className="field" style={{ marginTop: 14 }}><label>Default site</label><select className="select" value={prefs.defaultSite} onChange={(e) => setPrefs({ ...prefs, defaultSite: Number(e.target.value) })} data-testid="select-default-site">{sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div><div className="mini-stat" style={{ marginTop: 13 }}><span>Browser notifications</span><input type="checkbox" checked={prefs.notifications} onChange={(e) => setPrefs({ ...prefs, notifications: e.target.checked })} data-testid="input-notifications" /></div><div className="alert-strip" style={{ marginTop: 15 }}><CircleHelp size={15} /><span>Theme, density, and default site do not update the server.</span></div></section><section className="section-stack"><div className="card section-card"><div className="card-head"><div><div className="card-title">Live health</div><div className="card-kicker">GET /health · service dependencies</div></div><span className="pill good"><span className="dot" /> {data.health.status}</span></div>{[['Service', data.health.service], ['Database', data.health.db], ['Graph store', data.health.neo4j]].map(([label, value]) => <div className="mini-stat" key={label}><span>{label}</span><b style={{ color: 'hsl(var(--accent))' }}>{value}</b></div>)}</div><div className="card section-card"><div className="card-head"><div><div className="card-title">Admin jobs</div><div className="card-kicker">GET /admin/jobs · read-only</div></div><Database size={16} /></div>{data.jobs.map((job) => <div className="mini-stat" key={job.id}><span><b>{job.id === 'run_watcher' ? 'Risk refresh' : 'Reserve index'}</b><br /><small className="muted">next {timeLabel(job.next_run_time)} IST</small></span><span className="pill good"><Check size={10} /> {job.last_status}</span></div>)}</div></section></div></main>;
}

function LoginPage() { const navigate = useNavigate(); const [email, setEmail] = useState('anika.kulkarni@oresight.in'); return <div className="login-page"><section className="login-art"><div className="brand"><div className="brand-mark">O</div><div><div className="brand-word">OreSight</div><span className="brand-sub">mine intelligence</span></div></div><div><div className="eyebrow">Operations intelligence · India</div><h1>See the plan<br />beneath the ground.</h1><p>One control room for reserve confidence, production drift, and the decisions that keep a shift moving.</p><div className="login-pattern" /></div><div className="muted" style={{ fontSize: 10 }}>Preview workspace · v0.9.4</div></section><section className="login-form-side"><form className="login-form" onSubmit={(e) => { e.preventDefault(); navigate('/'); }}><div className="eyebrow">Planner sign in</div><h2>Welcome back.</h2><p className="subhead">Continue to your operating workspace.</p><div className="field"><label>Work email</label><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="input-login-email" /></div><div className="field"><label>Access key</label><input className="input" type="password" defaultValue="preview-access" data-testid="input-login-password" /></div><button className="btn primary" type="submit" data-testid="button-login">Enter OreSight <ChevronRight size={14} /></button><div className="footer-note">Visual-only sign in for the preview environment. No credentials are transmitted.</div></form></section></div>; }
function NotFound() { return <main className="page" style={{ minHeight: '100dvh', display: 'grid', placeItems: 'center' }}><div style={{ textAlign: 'center', maxWidth: 420 }}><div className="brand-mark" style={{ margin: '0 auto 17px' }}>O</div><div className="eyebrow">404 · outside the mine plan</div><h1 style={{ marginTop: 10 }}>This page is not mapped.</h1><p className="subhead">The route does not exist in the current OreSight workspace.</p><Link className="btn primary" to="/" style={{ marginTop: 20 }}>Return to dashboard <Home size={13} /></Link></div></main>; }
// The sidebar/nav (Shell) stays outside the boundary so a crash in one
// routed page doesn't blank the whole app -- only the boundary's own
// subtree (the Routes below) gets replaced by the fallback UI.
function RoutedShell() { const location = useLocation(); return <Shell><ErrorBoundary resetKey={location.pathname}><Routes><Route path="/" element={<Dashboard />} /><Route path="/site/:id" element={<SitePage />} /><Route path="/map" element={<MapPage />} /><Route path="/reports" element={<ReportsPage />} /><Route path="/simulator" element={<SimulatorPage />} /><Route path="/field-intake" element={<FieldIntakePage />} /><Route path="/settings" element={<SettingsPage />} /><Route path="/timeline" element={<Navigate to="/reports" replace />} /><Route path="/recommendations" element={<Navigate to="/reports" replace />} /><Route path="/data-input" element={<Navigate to="/field-intake" replace />} /><Route path="*" element={<NotFound />} /></Routes></ErrorBoundary></Shell>; }

function App() {
  return <BrowserRouter><Routes><Route path="/login" element={<LoginPage />} /><Route path="*" element={<RoutedShell />} /></Routes></BrowserRouter>;
}

export default App;
