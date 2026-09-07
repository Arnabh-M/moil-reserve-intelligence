import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Activity, AlertCircle, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3, Bell, Check, ChevronRight, CircleHelp, ClipboardList, Database, Download, FileText, Gauge, GitBranch, Home, Layers3, MapPin, Loader2, Map as MapIcon, Menu, Moon, RefreshCw, Search, Settings as SettingsIcon, ShieldCheck, SlidersHorizontal, Sun, Truck, X, Zap } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, AreaChart, Area, BarChart, Bar, CartesianGrid } from 'recharts';
import { ReactFlowProvider } from 'reactflow';
import 'reactflow/dist/style.css';
import { api } from './api/client';
import { previewNotice, localPreferences } from './api/placeholders';
import { ErrorBoundary } from './components/error-boundary';
import { SAMPLE_SITES, DEFAULT_RASTER_OPACITY, MAP_CENTER, MAP_ZOOM, REGIONAL_BOUNDS, prospectivityUrl, prospectivityBandsUrl } from './lib/map';
import LayerToggle from './components/map/LayerToggle';
import MineMap from './components/map/MineMap';
import ZoneDetailPanel from './components/map/ZoneDetailPanel';
import CrossSectionDrawer from './components/map/CrossSectionDrawer';
import ProspectivityCellPanel from './components/map/ProspectivityCellPanel';
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

function Shell({ children }) {
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem('oresight-theme') === 'dark');
  const location = useLocation();
  const current = navGroups.flatMap((g) => g.links).find((link) => link.to === location.pathname || (link.to !== '/' && location.pathname.startsWith(link.to)));
  useEffect(() => { document.documentElement.classList.toggle('dark', dark); localStorage.setItem('oresight-theme', dark ? 'dark' : 'light'); }, [dark]);
  return <div className="app-shell">
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="brand"><div className="brand-mark">O</div><div><div className="brand-word">OreSight</div><span className="brand-sub">mine intelligence</span></div></div>
      {navGroups.map((group) => <div className="nav-group" key={group.label}><div className="nav-label">{group.label}</div>{group.links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive || (to !== '/' && location.pathname.startsWith(to)) ? 'active' : ''}`} data-testid={`link-${label.toLowerCase().replaceAll(' ', '-')}`}><Icon size={15} strokeWidth={1.8} /><span>{label}</span>{label === 'Dashboard' && <span style={{ marginLeft: 'auto', font: '9px var(--app-font-mono)', color: 'hsl(var(--primary))' }}>04</span>}</NavLink>)}</div>)}
      <div className="sidebar-footer"><div className="user-chip"><div className="avatar">AK</div><div><div className="user-name">Anika Kulkarni</div><div className="user-role">Planning lead · IN-WEST</div></div></div></div>
    </aside>
    <div className="main-col">
      <header className="topbar"><div className="breadcrumb"><button className="btn ghost mobile-toggle" onClick={() => setOpen(!open)} aria-label="Open navigation" data-testid="button-open-navigation"><Menu size={17} /></button><span>OreSight</span><ChevronRight size={13} /><strong>{current?.label || 'Workspace'}</strong></div><div className="top-actions"><button className="btn ghost small" title="Toggle theme" onClick={() => setDark(!dark)} data-testid="button-toggle-theme">{dark ? <Sun size={15} /> : <Moon size={15} />}</button><button className="btn ghost small" title="Notifications" data-testid="button-notifications"><Bell size={15} /></button></div></header>
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
function Recommendation({ recommendation }) { const option = recommendation.options[0]; if (!option) return <EmptyState title="No graph-sourced alternatives found for this event" />; return <div className="card recommend-card"><div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><div><span className="eyebrow">Response to {riskTypeLabel(recommendation.trigger)}</span><h3 style={{ marginTop: 5 }}>{recommendationTypeLabel(option.type)}</h3></div><Zap size={15} color="hsl(var(--primary))" /></div><p>{option.description}</p><div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><span className="recommend-impact">+{option.projected_impact}% projected impact</span><button className="btn small" data-testid={`button-review-${recommendation.risk_event_id}`}>Review <ChevronRight size={12} /></button></div></div>; }

function Dashboard() {
  const { data, loading, error, retry } = useAsync(() => api.getDashboard(), []);
  const [riskFilter, setRiskFilter] = useState('all');
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
    <div className="dashboard-grid equal"><section className="card section-card"><div className="card-head"><div><div className="card-title">Production pulse</div><div className="card-kicker">all sites · tonnes per day</div></div><div className="legend"><span><i />Actual</span><span><i className="target" />Target</span></div></div><div style={{ height: 220 }}><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData}><CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="day" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={35} /><Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', fontSize: 11 }} /><Area type="monotone" dataKey="target" stroke="hsl(var(--accent) / .38)" fill="hsl(var(--accent) / .07)" strokeWidth={2} /><Area type="monotone" dataKey="actual" stroke="hsl(var(--primary))" fill="hsl(var(--primary) / .12)" strokeWidth={2} /></AreaChart></ResponsiveContainer></div></section><section className="card section-card"><div className="card-head"><div><div className="card-title">Recommended actions</div><div className="card-kicker">model-ranked options · choose before shift change</div></div><Link to="/reports" className="btn small">All insights</Link></div>{recommendations.slice(0, 2).map((item) => <Recommendation recommendation={item} key={item.risk_event_id} />)}</section></div>
    <div className="footer-note"><CircleHelp size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} /> {previewNotice} Twin state last refreshed at {timeLabel(kpi.twin_last_updated)} IST.</div>
  </main>;
}

function SitePage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || 'overview';
  const { data, loading, error, retry } = useAsync(() => api.getSiteWorkspace(id), [id]);
  const tabs = ['overview', 'production', 'reserve', 'recommendations', 'graph'];
  if (loading) return <main className="page"><LoadingCard lines={9} /></main>;
  if (error || !data) return <main className="page"><ErrorState retry={retry} /></main>;
  const { site, risks, equipment, production, zones, recommendations, graph } = data;
  const setTab = (next) => setSearchParams({ tab: next });
  return <main className="page"><div className="site-banner"><div><div className="eyebrow">Site intelligence · {site.id}</div><h1>{site.name}</h1><div className="site-place">{site.belt_name} · {site.district}, {site.state} · updated 08:05 IST</div></div><div className="filter-row"><span className={`pill ${site.active_risk_count > 2 ? 'critical' : 'warn'}`}>{site.active_risk_count} active risks</span><Link className="btn small" to="/map">View on map <MapIcon size={12} /></Link></div></div><div className="tabs">{tabs.map((item) => <button className={`tab ${tab === item ? 'active' : ''}`} onClick={() => setTab(item)} key={item} data-testid={`tab-site-${item}`}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div>
    {tab === 'overview' && <SiteOverview site={site} risks={risks} equipment={equipment} zones={zones} production={production} />}
    {tab === 'production' && <ProductionView production={production} site={site} />}
    {tab === 'reserve' && <ReserveView zones={zones} site={site} />}
    {tab === 'recommendations' && <RecommendationsView recommendations={recommendations} risks={risks} />}
    {tab === 'graph' && <GraphView graph={graph} />}
  </main>;
}
function SiteOverview({ site, risks, equipment, zones, production }) { return <><div className="stat-grid"><StatCard label="Reserve confidence" value={percent(site.avg_reserve_confidence)} foot="weighted active zones" trend={2.1} icon={ShieldCheck} /><StatCard label="Output variance" value={`${production.reduce((a, b) => a + b.variance_pct, 0) / production.length > 0 ? '+' : ''}${(production.reduce((a, b) => a + b.variance_pct, 0) / production.length).toFixed(1)}%`} foot="7-day average" icon={BarChart3} /><StatCard label="Equipment online" value={`${equipment.filter((e) => e.status === 'up').length}/${equipment.length}`} foot="current shift" icon={Truck} /><StatCard label="Zones inventoried" value={zones.length} foot="confidence screened" icon={Layers3} /></div><div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Risk register</div><div className="card-kicker">open events linked to site signals</div></div><Link to="/reports" className="btn small">View reports</Link></div>{risks.length ? risks.map((risk) => <RiskItem risk={risk} key={risk.id} />) : <EmptyState title="No open risk events" />}</section><section className="card section-card"><div className="card-head"><div><div className="card-title">Equipment posture</div><div className="card-kicker">reported by field operations</div></div><Truck size={16} color="hsl(var(--muted-foreground))" /></div>{equipment.map((item) => <div className="mini-stat" key={item.id}><span><b>{item.name}</b><br /><small className="muted">{item.equipment_type}</small></span><span className={`pill ${item.status === 'up' ? 'good' : 'critical'}`}>{item.status}</span></div>)}</section></div></>; }
function ProductionView({ production, site }) { return <div className="section-stack"><section className="card section-card"><div className="card-head"><div><div className="card-title">Production variance · {site.name}</div><div className="card-kicker">actual vs target output · tonnes per day</div></div><span className="pill warn">7 day window</span></div><div style={{ height: 300 }}><ResponsiveContainer width="100%" height="100%"><BarChart data={production}><CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} tickFormatter={(v) => v.slice(5)} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', fontSize: 11 }} /><Bar dataKey="target_output" fill="hsl(var(--accent) / .3)" name="Target" radius={[3, 3, 0, 0]} /><Bar dataKey="actual_output" fill="hsl(var(--primary))" name="Actual" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div></section><section className="card section-card"><div className="card-head"><div className="card-title">Shift ledger</div><div className="card-kicker">frozen API response</div></div><div className="table-wrap"><table><thead><tr><th>Date</th><th>Actual</th><th>Target</th><th>Variance</th><th>Plan read</th></tr></thead><tbody>{production.map((item) => <tr key={item.id}><td className="mono">{item.date}</td><td>{item.actual_output.toLocaleString()} t</td><td>{item.target_output.toLocaleString()} t</td><td className={item.variance_pct < 0 ? 'risk-high' : 'trend-up'}>{item.variance_pct > 0 ? '+' : ''}{item.variance_pct}%</td><td><div className="progress" style={{ width: 120 }}><span style={{ width: `${Math.min(100, 100 + item.variance_pct)}%` }} /></div></td></tr>)}</tbody></table></div></section></div>; }
function ReserveView({ zones, site }) { const rows = zones.map((zone) => zone.properties); return <div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Grade distribution</div><div className="card-kicker">confidence-weighted zone estimate · {site.name}</div></div></div><div style={{ height: 270 }}><ResponsiveContainer width="100%" height="100%"><BarChart data={rows}><CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="zone_name" tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} /><YAxis tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', fontSize: 11 }} /><Bar dataKey="estimated_grade_pct" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></section><section className="card section-card"><div className="card-head"><div><div className="card-title">Zone inventory</div><div className="card-kicker">prospectivity signal, not a reserve statement</div></div><Layers3 size={16} /></div>{rows.length ? rows.map((zone) => <div className="mini-stat" key={zone.id}><span><b>{zone.zone_name}</b><br /><small className="muted">{zone.estimated_grade_pct}% estimated grade · {zone.estimated_depth_m} m</small></span><span><b>{percent(zone.confidence_score)}</b><br /><small className="muted">confidence</small></span></div>) : <EmptyState title="No zone inventory" />}</section></div>; }
function RecommendationsView({ recommendations, risks }) { return <div className="two-col"><section className="section-stack">{recommendations.map((item) => <div key={item.risk_event_id}><div className="eyebrow" style={{ margin: '5px 0 7px' }}>{riskTypeLabel(risks.find((r) => r.id === item.risk_event_id)?.risk_type || item.trigger)}</div>{item.options.length ? item.options.map((option) => <div className="card recommend-card" key={option.type}><div className="card-head" style={{ marginBottom: 7 }}><h3>{recommendationTypeLabel(option.type)}</h3><span className="pill good">{percent(option.confidence)} confidence</span></div><p>{option.description}</p><div className="recommend-impact">+{option.projected_impact}% projected impact</div><button className="btn small" style={{ marginTop: 12 }} data-testid={`button-apply-${option.type.toLowerCase().replaceAll('_', '-')}`}><Check size={12} /> Add to shift plan</button></div>) : <EmptyState title="No graph-sourced alternatives found for this event" />}</div>)}</section><section className="card section-card"><div className="card-title">How to read recommendations</div><p className="subhead">Each option combines the active risk trigger with site state and graph context. Projected impact is already expressed as a percentage; it is not a probability.</p><div className="alert-strip" style={{ marginTop: 18 }}><CircleHelp size={15} /><span>{previewNotice}</span></div></section></div>; }
function GraphView({ graph }) { return <div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Causal graph</div><div className="card-kicker">{graph.graph_source} · relationship edges</div></div></div><ReactFlowProvider><div className="graph-panel"><div className="graph-lines" /><div className="connector" style={{ left: '27%', top: '55%', width: '29%', transform: 'rotate(-24deg)' }} /><div className="connector" style={{ left: '49%', top: '54%', width: '26%', transform: 'rotate(17deg)' }} /><div className="connector" style={{ left: '52%', top: '58%', width: '28%', transform: 'rotate(23deg)' }} />{graph.nodes.map((node, i) => <div className={`graph-node ${node.type === 'RiskEvent' ? 'alert' : ''}`} style={{ left: `${[8, 39, 10, 64][i]}%`, top: `${[47, 17, 73, 67][i]}%` }} key={node.id}><strong>{node.label}</strong><small>{node.type}</small></div>)}</div></ReactFlowProvider></section><section className="card section-card"><div className="card-title">Relationships</div>{graph.edges.map((edge) => <div className="mini-stat" key={`${edge.source}-${edge.target}`}><span>{graph.nodes.find((n) => n.id === edge.source)?.label}<br /><small className="muted">{edge.relationship}</small></span><ChevronRight size={14} /><span>{graph.nodes.find((n) => n.id === edge.target)?.label}</span></div>)}<div className="footer-note">{graph.note}</div></section></div>; }

function MapPage() {
  // Ported from the pre-Replit oresight-frontend (git 230f49a) — real MapLibre
  // layers (prospectivity heatmap, spectral alteration, drone DSM, NDVI
  // time-series, structural lineaments) instead of the Replit import's
  // schematic placeholder map. See components/map/* and lib/map.js.
  const [prospectivityVisible, setProspectivityVisible] = useState(false);
  const [spectralVisible, setSpectralVisible] = useState(false);
  const [droneVisible, setDroneVisible] = useState(false);
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
    if (siteId === 'balaghat' || siteId === 1) return 'Balaghat Mine';
    if (siteId === 'nagpur' || siteId === 2) return 'Nagpur Mine';
    if (siteId === 'bhandara' || siteId === 3) return 'Bhandara Mine';
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

  function handleSiteSelect(siteId) {
    setSelectedSiteIdForFlyTo(siteId);
    if (!siteId) {
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
    const site = SAMPLE_SITES.find((s) => s.id === siteId);
    if (site) {
      setFlyToTarget({
        id: site.id,
        name: site.name,
        latitude: site.latitude,
        longitude: site.longitude,
        bounds: site.bounds,
        zoom: 11,
      });
      setProspectivitySiteId(site.id);
    }
  }

  function handleSelectCrossSectionPoint(point) {
    setCrossSectionPoint(point);
    setCrossSectionDrawerOpen(true);
  }

  function handleInspectZoneCrossSection() {
    if (!selectedZone) return;
    const lat = selectedZone.latitude ?? (selectedZone.site_id === 'balaghat' ? 21.8 : selectedZone.site_id === 'nagpur' ? 21.1 : 21.2);
    const lng = selectedZone.longitude ?? (selectedZone.site_id === 'balaghat' ? 80.2 : selectedZone.site_id === 'nagpur' ? 79.1 : 79.6);
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
        droneVisible={droneVisible}
        onDroneChange={setDroneVisible}
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
          droneVisible={droneVisible}
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
  const exportCsv = () => { const csv = ['site,risk,severity,score,detected_at', ...risks.map((r) => `${r.site_name},${r.risk_type},${r.severity},${r.score},${r.detected_at}`)].join('\n'); const blob = new Blob([csv], { type: 'text/csv' }); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'oresight-risk-register.csv'; anchor.click(); URL.revokeObjectURL(url); setToast('CSV report generated'); setTimeout(() => setToast(''), 2200); };
  return <main className="page"><div className="page-head"><div><div className="eyebrow">Reports & insights · decision trail</div><h1>Make the risk legible</h1><p className="subhead">A concise record of model signals, chosen responses, and the operational story behind the numbers.</p></div><button className="btn primary" onClick={exportCsv} data-testid="button-export-csv"><Download size={14} /> Export CSV</button></div><div className="card section-card" style={{ marginBottom: 14 }}><div className="filter-row"><SlidersHorizontal size={15} color="hsl(var(--muted-foreground))" /><select className="select" value={severity} onChange={(e) => setSeverity(e.target.value)} data-testid="select-report-severity"><option value="all">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select><span className="muted" style={{ fontSize: 10 }}>{risks.length} events in preview</span></div></div><div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Risk timeline</div><div className="card-kicker">detected events across the current planning window</div></div><span className="pill good"><Activity size={11} /> Live preview</span></div><div className="timeline">{risks.map((risk) => <div className="timeline-item" key={risk.id}><div className="timeline-date">{dateLabel(risk.detected_at)} · {timeLabel(risk.detected_at)} IST · {risk.site_name}</div><div className="timeline-text"><b>{riskTypeLabel(risk.risk_type)}</b> — {risk.description}</div><span className={`pill ${severityClass(risk.severity)}`} style={{ marginTop: 7 }}>{severityLabel(risk.severity)} · {percent(risk.score)}</span></div>)}</div></section><section className="section-stack"><div className="card section-card"><div className="card-head"><div><div className="card-title">Corrective actions</div><div className="card-kicker">response coverage</div></div><Check size={16} color="hsl(var(--accent))" /></div>{data.recommendations.map((rec) => <div className="mini-stat" key={rec.risk_event_id}><span><b>{riskTypeLabel(rec.trigger)}</b><br /><small className="muted">{rec.options.length} model-ranked options</small></span><Link to={`/site/${data.risks.find((r) => r.id === rec.risk_event_id)?.site_id || 1}?tab=recommendations`} className="btn small">Review</Link></div>)}</div><div className="card section-card"><div className="card-title">Report preview</div><p className="subhead">The export contains the filtered risk register, current severity, model score, site, and detection timestamp. Narrative and graph evidence remain in site intelligence.</p><button className="btn" onClick={exportCsv} data-testid="button-download-report"><FileText size={13} /> Download report packet</button></div></section></div>{toast && <div className="toast"><Check size={14} style={{ verticalAlign: 'middle', marginRight: 7 }} />{toast}</div>}</main>;
}

function SimulatorPage() {
  const [params] = useSearchParams();
  const [scenario, setScenario] = useState(isValidScenarioType(params.get('scenario_type')) ? params.get('scenario_type') : 'equipment_down');
  const [site, setSite] = useState(Number(params.get('site_id')) || 1);
  const [duration, setDuration] = useState(Number(params.get('duration_days')) || 7);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const runSimulation = async () => {
    setRunning(true);
    setError(null);
    try {
      const value = await api.simulate({ scenario_type: scenario, site_id: site, duration_days: duration });
      setResult(value);
    } catch (simulateError) {
      setError(simulateError.detail || 'The simulation could not be run. Try again.');
    } finally {
      setRunning(false);
    }
  };
  return <main className="page"><div className="page-head"><div><div className="eyebrow">Scenario simulator · decision rehearsal</div><h1>Change one lever. See the trade-off.</h1><p className="subhead">A model-backed what-if surface for shift planning. Results are directional and should be checked against field conditions.</p></div></div><div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Scenario inputs</div><div className="card-kicker">query parameters can prefill this workspace</div></div><SlidersHorizontal size={16} /></div><div className="form-grid"><div className="field"><label>Scenario type</label><select className="select" value={scenario} onChange={(e) => setScenario(e.target.value)} data-testid="select-scenario">{SCENARIO_TYPE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></div><div className="field"><label>Site</label><select className="select" value={site} onChange={(e) => setSite(Number(e.target.value))} data-testid="select-simulation-site"><option value="1">Balaghat</option><option value="2">Nagpur</option><option value="3">Bhandara</option></select></div><div className="field full"><label>Scenario horizon · {duration} days</label><input type="range" min="1" max="30" value={duration} onChange={(e) => setDuration(Number(e.target.value))} data-testid="input-simulation-duration" /></div></div><button className="btn primary" onClick={runSimulation} disabled={running} style={{ marginTop: 19 }} data-testid="button-run-simulation">{running ? <RefreshCw size={14} className="spin" /> : <Zap size={14} />}{running ? 'Running model…' : 'Run simulation'}</button>{error && <div className="alert-strip danger" style={{ marginTop: 14 }}><AlertCircle size={15} color="hsl(var(--destructive))" /><span>{error}</span><button className="btn small" style={{ marginLeft: 'auto' }} onClick={runSimulation} data-testid="button-retry-simulation"><RefreshCw size={12} /> Retry</button></div>}</section><section className="card section-card"><div className="card-head"><div><div className="card-title">Before / after</div><div className="card-kicker">impact snapshot · {duration}-day horizon</div></div>{result && <span className="pill good"><Check size={11} /> Complete</span>}</div>{result ? <div className="section-stack"><div className="three-col">{[['Reserve confidence', percent(result.before.reserve_confidence), percent(result.after.reserve_confidence), result.after.reserve_confidence - result.before.reserve_confidence], ['Production forecast', `${result.before.production_forecast_tonnes} t`, `${result.after.production_forecast_tonnes} t`, result.after.production_forecast_tonnes - result.before.production_forecast_tonnes], ['Risk score', percent(result.before.risk_score), percent(result.after.risk_score), result.after.risk_score - result.before.risk_score]].map(([label, before, after, delta]) => <div className="card section-card" key={label} style={{ padding: 12 }}><div className="metric-label">{label}</div><div className="metric-value">{after}</div><div className={delta >= 0 ? 'trend-up' : 'trend-down'} style={{ font: '10px var(--app-font-mono)', marginTop: 4 }}>{delta >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />} {typeof delta === 'number' && delta > 1 ? '+' : ''}{typeof delta === 'number' && label !== 'Production forecast' ? percent(delta) : delta} </div><div className="muted" style={{ fontSize: 9, marginTop: 3 }}>before {before}</div></div>)}</div><div className="alert-strip"><GitBranch size={15} /><span>Affected path: <b>{result.affected_graph_path.join(' → ')}</b>. This is a scenario output, not a commitment to execute.</span></div><Link className="btn" to={`/site/${site}?tab=graph`}>Open affected graph <ChevronRight size={13} /></Link></div> : <EmptyState icon={GitBranch} title="No scenario run yet">Set a lever on the left and run the model to compare plan outcomes.</EmptyState>}</section></div></main>;
}

function FieldIntakePageLegacy() {
  const { data, loading, error, retry } = useAsync(() => api.getFieldWorkspace(), []);
  const [active, setActive] = useState('equipment');
  const [note, setNote] = useState('');
  const [query, setQuery] = useState('');
  const [searchedNotes, setSearchedNotes] = useState([]);
  const [uploadResult, setUploadResult] = useState(null);
  const [toast, setToast] = useState('');
  if (loading) return <main className="page"><LoadingCard lines={10} /></main>;
  if (error) return <main className="page"><ErrorState retry={retry} /></main>;
  const onUpload = async (event) => { const file = event.target.files?.[0]; if (!file) return; setUploadResult(await api.uploadReport(file)); };
  const saveNote = async () => { if (!note.trim()) return; await api.createSiteNote({ site_id: 1, text: note }); setNote(''); setToast('Note added to Balaghat field log'); setTimeout(() => setToast(''), 2200); };
  const notes = data.notes.filter((item) => item.text.toLowerCase().includes(query.toLowerCase()));
  return <main className="page"><div className="page-head"><div><div className="eyebrow">Field intake · legacy preview</div><h1>Bring the shift into the model</h1></div><span className="pill mock">Contract surface below</span></div></main>;
}

function FieldIntakePage() {
  const { data, loading, error, retry } = useAsync(() => api.getFieldWorkspace(), []);
  const [active, setActive] = useState('equipment');
  const [equipmentRows, setEquipmentRows] = useState([]);
  const [note, setNote] = useState('');
  const [query, setQuery] = useState('');
  const [searchedNotes, setSearchedNotes] = useState([]);
  const [toast, setToast] = useState('');
  useEffect(() => { if (data) setEquipmentRows(data.equipment); }, [data]);
  useEffect(() => { if (data) api.searchSiteNotes(query, 1).then(setSearchedNotes).catch(() => setSearchedNotes([])); }, [query, data]);
  if (loading) return <main className="page"><LoadingCard lines={10} /></main>;
  if (error) return <main className="page"><ErrorState retry={retry} /></main>;
  const showToast = (message) => { setToast(message); setTimeout(() => setToast(''), 2600); };
  const onStatusChange = async (item, status) => { try { const updated = await api.updateEquipmentStatus(item.id, { status, status_reason: status === 'up' ? 'Returned to service from field intake' : 'Marked down from field intake' }); setEquipmentRows((rows) => rows.map((row) => row.id === item.id ? updated : row)); showToast(`${item.name} marked ${status}`); } catch (statusError) { showToast(statusError.status === 409 ? '409 conflict: equipment changed elsewhere; reload before retrying.' : statusError.detail || 'Status update failed'); } };
  const refetchEquipment = async () => { try { const fresh = await api.getFieldWorkspace(); setEquipmentRows(fresh.equipment); } catch { /* keep current rows; bulk summary already reflects per-item results */ } };
  const saveNote = async () => { if (!note.trim()) { showToast('Validation: note text is required.'); return; } try { await api.createSiteNote({ site_id: 1, text: note }); setNote(''); showToast('Note added to Balaghat field log'); } catch (noteError) { showToast(noteError.status === 409 ? '409 conflict: the note was updated elsewhere.' : noteError.detail || 'Note save failed'); } };
  const notes = query ? searchedNotes : data.notes;
  return <main className="page"><div className="page-head"><div><div className="eyebrow">Field intake · operations loop</div><h1>Bring the shift into the model</h1><p className="subhead">Capture equipment status, production reality, geology documents, and the notes that explain the deviation.</p></div></div><div className="tabs">{['equipment', 'production', 'blasting', 'geology', 'notes'].map((item) => <button className={`tab ${active === item ? 'active' : ''}`} onClick={() => setActive(item)} key={item} data-testid={`tab-field-${item}`}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div>
    {['equipment', 'production', 'blasting', 'geology'].includes(active) && <ErrorBoundary resetKey={active} FallbackComponent={FieldIntakeTabFallback}><Suspense fallback={<LoadingCard lines={6} />}>
      {active === 'equipment' && <EquipmentTab equipmentRows={equipmentRows} setEquipmentRows={setEquipmentRows} onStatusChange={onStatusChange} showToast={showToast} refetchAll={refetchEquipment} />}
      {active === 'production' && <ProductionTab showToast={showToast} />}
      {active === 'blasting' && <BlastLogTab showToast={showToast} />}
      {active === 'geology' && <GeologyTab />}
    </Suspense></ErrorBoundary>}
    {active === 'notes' && <div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Site notes</div><div className="card-kicker">GET /site-notes/search · searchable field context</div></div><Search size={15} /></div><input className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search notes by keyword" data-testid="input-search-notes" />{notes.length ? notes.map((item) => <div className="risk-item" key={item.id}><div className="risk-marker medium" /><div className="risk-item-main"><div className="risk-title">{item.text}</div><div className="risk-meta">{dateLabel(item.created_at)} · relevance {percent(item.relevance)}</div></div></div>) : <EmptyState icon={Search} title="No notes found" />}</section><section className="card section-card"><div className="card-title">Add shift note</div><p className="subhead">Notes are local preview writes and are attached to Balaghat (site 1).</p><textarea className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Record a site observation…" style={{ width: '100%', marginTop: 14 }} data-testid="textarea-site-note" /><button className="btn primary" onClick={saveNote} style={{ marginTop: 10 }} data-testid="button-save-note"><Check size={13} /> Save note</button><div className="alert-strip" style={{ marginTop: 18 }}><CircleHelp size={15} /><span>Live API conflict responses (409) are shown inline so stale writes can be reviewed before retrying.</span></div></section></div>}
    {toast && <div className="toast">{toast}</div>}</main>;
}

function SettingsPage() {
  const { data, loading, error, retry } = useAsync(() => api.getSettingsWorkspace(), []);
  const [prefs, setPrefs] = useState(localPreferences);
  if (loading) return <main className="page"><LoadingCard lines={8} /></main>;
  if (error) return <main className="page"><ErrorState retry={retry} /></main>;
  return <main className="page"><div className="page-head"><div><div className="eyebrow">Settings · workspace controls</div><h1>Keep the room predictable</h1><p className="subhead">Local preferences and live service status. Admin controls are clearly separated from planning decisions.</p></div></div><div className="two-col"><section className="card section-card"><div className="card-head"><div><div className="card-title">Local preferences</div><div className="card-kicker">stored on this device only</div></div><SettingsIcon size={16} /></div><div className="field"><label>Workspace density</label><select className="select" value={prefs.density} onChange={(e) => setPrefs({ ...prefs, density: e.target.value })} data-testid="select-density"><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></div><div className="field" style={{ marginTop: 14 }}><label>Default site</label><select className="select" value={prefs.defaultSite} onChange={(e) => setPrefs({ ...prefs, defaultSite: Number(e.target.value) })} data-testid="select-default-site"><option value="1">Balaghat</option><option value="2">Nagpur</option><option value="3">Bhandara</option></select></div><div className="mini-stat" style={{ marginTop: 13 }}><span>Browser notifications</span><input type="checkbox" checked={prefs.notifications} onChange={(e) => setPrefs({ ...prefs, notifications: e.target.checked })} data-testid="input-notifications" /></div><div className="alert-strip" style={{ marginTop: 15 }}><CircleHelp size={15} /><span>Theme, density, and default site do not update the server.</span></div></section><section className="section-stack"><div className="card section-card"><div className="card-head"><div><div className="card-title">Live health</div><div className="card-kicker">GET /health · service dependencies</div></div><span className="pill good"><span className="dot" /> {data.health.status}</span></div>{[['Service', data.health.service], ['Database', data.health.db], ['Graph store', data.health.neo4j]].map(([label, value]) => <div className="mini-stat" key={label}><span>{label}</span><b style={{ color: 'hsl(var(--accent))' }}>{value}</b></div>)}</div><div className="card section-card"><div className="card-head"><div><div className="card-title">Admin jobs</div><div className="card-kicker">GET /admin/jobs · read-only</div></div><Database size={16} /></div>{data.jobs.map((job) => <div className="mini-stat" key={job.id}><span><b>{job.id === 'run_watcher' ? 'Risk refresh' : 'Reserve index'}</b><br /><small className="muted">next {timeLabel(job.next_run_time)} IST</small></span><span className="pill good"><Check size={10} /> {job.last_status}</span></div>)}</div></section></div></main>;
}

function LoginPage() { const navigate = useNavigate(); const [email, setEmail] = useState('anika.kulkarni@oresight.in'); return <div className="login-page"><section className="login-art"><div className="brand"><div className="brand-mark">O</div><div><div className="brand-word">OreSight</div><span className="brand-sub">mine intelligence</span></div></div><div><div className="eyebrow">Operations intelligence · India</div><h1>See the plan<br />beneath the ground.</h1><p>One control room for reserve confidence, production drift, and the decisions that keep a shift moving.</p><div className="login-pattern" /></div><div className="muted" style={{ fontSize: 10 }}>Preview workspace · v0.9.4</div></section><section className="login-form-side"><form className="login-form" onSubmit={(e) => { e.preventDefault(); navigate('/'); }}><div className="eyebrow">Planner sign in</div><h2>Welcome back.</h2><p className="subhead">Continue to your operating workspace.</p><div className="field"><label>Work email</label><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="input-login-email" /></div><div className="field"><label>Access key</label><input className="input" type="password" defaultValue="preview-access" data-testid="input-login-password" /></div><button className="btn primary" type="submit" data-testid="button-login">Enter OreSight <ChevronRight size={14} /></button><div className="footer-note">Visual-only sign in for the preview environment. No credentials are transmitted.</div></form></section></div>; }
function NotFound() { return <main className="page" style={{ minHeight: '100dvh', display: 'grid', placeItems: 'center' }}><div style={{ textAlign: 'center', maxWidth: 420 }}><div className="brand-mark" style={{ margin: '0 auto 17px' }}>O</div><div className="eyebrow">404 · outside the mine plan</div><h1 style={{ marginTop: 10 }}>This page is not mapped.</h1><p className="subhead">The route does not exist in the current OreSight workspace.</p><Link className="btn primary" to="/" style={{ marginTop: 20 }}>Return to dashboard <Home size={13} /></Link></div></main>; }
function RoutedShell() { const location = useLocation(); return <ErrorBoundary resetKey={location.pathname}><Shell><Routes><Route path="/" element={<Dashboard />} /><Route path="/site/:id" element={<SitePage />} /><Route path="/map" element={<MapPage />} /><Route path="/reports" element={<ReportsPage />} /><Route path="/simulator" element={<SimulatorPage />} /><Route path="/field-intake" element={<FieldIntakePage />} /><Route path="/settings" element={<SettingsPage />} /><Route path="*" element={<NotFound />} /></Routes></Shell></ErrorBoundary>; }

function App() {
  return <BrowserRouter><Routes><Route path="/login" element={<LoginPage />} /><Route path="*" element={<RoutedShell />} /></Routes></BrowserRouter>;
}

export default App;