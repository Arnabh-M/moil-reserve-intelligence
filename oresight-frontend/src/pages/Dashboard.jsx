import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import {
  Mountain, MapPin, Target, Sparkles, Layers,
  Compass, AlertTriangle, ArrowUpRight, ArrowRight, ShieldCheck, CheckCircle2,
} from 'lucide-react';
import { Card, KPIStat, Badge, InlineError, RecentRiskEvents } from '../components';
import { getSites, getRiskEvents, getReserveZones } from '../api/client';
import MapPage from './MapPage';

// Color Palette Tokens
const COLOR_FOREST = '#164A3A';
const COLOR_SECONDARY_GREEN = '#2F6B52';
const COLOR_MINERAL_ORANGE = '#C56A32';
const COLOR_COPPER_LIGHT = '#E8B38A';

const monthlyProduction = [
  { month: 'Jan', actual: 3100, target: 2800 },
  { month: 'Feb', actual: 3800, target: 3400 },
  { month: 'Mar', actual: 2600, target: 3000 },
  { month: 'Apr', actual: 4000, target: 3600 },
  { month: 'May', actual: 2400, target: 2700 },
  { month: 'Jun', actual: 1900, target: 2200 },
  { month: 'Jul', actual: 1600, target: 1800 },
  { month: 'Aug', actual: 3876, target: 3600 },
  { month: 'Sep', actual: 2400, target: 2300 },
  { month: 'Oct', actual: 1400, target: 1600 },
  { month: 'Nov', actual: 1200, target: 1300 },
  { month: 'Dec', actual: 2500, target: 2200 },
];

const ndviTrendData = [
  { month: 'W1', ndvi: 0.68, moisture: 42, probability: 78 },
  { month: 'W2', ndvi: 0.72, moisture: 45, probability: 84 },
  { month: 'W3', ndvi: 0.75, moisture: 48, probability: 89 },
  { month: 'W4', ndvi: 0.71, moisture: 44, probability: 86 },
];

const zoneDiscoveryData = [
  { zone: 'MZ-01 (Balaghat East)', location: 'Balaghat Belt', potential: 'High (4.8M t)', confidence: 94, geoScore: 8.9, ndvi: 0.75, status: 'Active Target' },
  { zone: 'MZ-04 (Dongri Buzurg)', location: 'Bhandara Sector', potential: 'High (3.2M t)', confidence: 88, geoScore: 8.4, ndvi: 0.68, status: 'Validation' },
  { zone: 'MZ-07 (Tirodi Core)', location: 'Balaghat West', potential: 'Med (2.1M t)', confidence: 82, geoScore: 7.8, ndvi: 0.62, status: 'Surveying' },
  { zone: 'MZ-12 (Mansar South)', location: 'Nagpur Sector', potential: 'Med (1.9M t)', confidence: 79, geoScore: 7.5, ndvi: 0.59, status: 'Exploration' },
  { zone: 'MZ-15 (Ukwa Sector)', location: 'Balaghat Belt', potential: 'High (3.9M t)', confidence: 91, geoScore: 8.7, ndvi: 0.73, status: 'Active Target' },
];

const ModernTooltip = ({ active, payload, label, unit = '' }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[var(--bg-surface)] text-[var(--text-primary)] px-3 py-2 rounded-lg border border-[var(--border)] shadow-md text-xs font-mono space-y-1">
      <p className="font-semibold text-[var(--text-primary)] border-b border-[var(--divider)] pb-1">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center justify-between gap-3">
          <span className="text-[var(--text-muted)]">{p.name}:</span>
          <span className="font-bold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)]">
            {p.value} {unit}
          </span>
        </div>
      ))}
    </div>
  );
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [liveSites, setLiveSites] = useState([]);
  const [liveRiskEvents, setLiveRiskEvents] = useState([]);
  const [reserveZones, setReserveZones] = useState([]);
  const [liveStatus, setLiveStatus] = useState('loading');

  useEffect(() => {
    async function load() {
      setLiveStatus('loading');
      try {
        const [sitesData, riskData, zonesGeo] = await Promise.all([
          getSites(),
          getRiskEvents(),
          getReserveZones(),
        ]);
        setLiveSites(sitesData || []);
        setLiveRiskEvents(riskData || []);
        const features = Array.isArray(zonesGeo?.features) ? zonesGeo.features : [];
        setReserveZones(features.map(f => f.properties));
        setLiveStatus('ready');
      } catch (err) {
        console.error('[Dashboard] Error fetching telemetry:', err);
        setLiveStatus('error');
      }
    }
    load();
  }, []);

  const totalSites = liveSites.length || 3;
  const highPotentialZones = reserveZones.filter(z => (z.confidence_score || 0) >= 0.75).length || 14;

  return (
    <div className="page-container space-y-8">
      {/* ── 1. Page Header ─────────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Geological Intelligence &amp; Operations Command</h1>
          <p className="page-subtitle">
            Real-time MOIL manganese deposit telemetry, Kriging spatial reserves model, and AI target discovery
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            type="button"
            onClick={() => navigate('/data-input')}
            className="btn-gradient"
          >
            <Sparkles size={14} />
            <span>Field Data Entry</span>
          </button>
        </div>
      </div>

      {/* ── 2. KPI Row: 4 Compact Containers ──────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPIStat
          label="Est. Manganese Reserves"
          value="18.4M t"
          delta={4.8}
          deltaLabel="vs previous geological audit"
          icon={Mountain}
        />
        <KPIStat
          label="High-Potential Zones"
          value={String(highPotentialZones).padStart(2, '0')}
          delta={12.5}
          deltaLabel="confidence score > 75%"
          icon={Target}
        />
        <KPIStat
          label="Sites Analyzed"
          value={String(totalSites).padStart(2, '0')}
          delta={0.0}
          deltaLabel="active MOIL sector telemetry"
          icon={Layers}
        />
        <KPIStat
          label="AI Prediction Confidence"
          value="91.4%"
          delta={2.1}
          deltaLabel="Kriging twin spatial precision"
          icon={ShieldCheck}
        />
      </div>

      {/* ── 3. Main Visualizer: GIS Map + AI Exploration Insights Side-by-Side ─ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
        {/* Large GIS Map Viewport (2 cols) */}
        <div className="lg:col-span-2 rounded-xl border border-[var(--border)] overflow-hidden bg-[var(--bg-surface)] flex flex-col min-h-[440px]">
          <div className="px-4 py-3 border-b border-[var(--divider)] flex items-center justify-between bg-[var(--bg-secondary)]/50">
            <div className="flex items-center gap-2">
              <Compass size={16} className="text-[var(--forest-primary)] dark:text-[var(--forest-secondary)]" />
              <span className="text-xs font-heading font-semibold text-[var(--text-primary)]">
                MOIL GIS Spatial Telemetry &amp; Haulage Routing
              </span>
            </div>
            <span className="text-[11px] font-mono text-[var(--text-muted)]">Live Route Tracking • Balaghat Sector</span>
          </div>
          <div className="flex-1 relative">
            <MapPage inlineView />
          </div>
        </div>

        {/* AI Exploration Insight Box (1 col) */}
        <Card
          title="AI Exploration Insight"
          subtitle="Real-time predictive borehole recommendation"
          className="flex flex-col justify-between"
        >
          <div className="space-y-4">
            <div className="p-3.5 rounded-lg bg-[var(--accent-soft)] border border-[var(--border)]">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-mono font-bold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] uppercase">
                  Target Zone: MZ-01
                </span>
                <Badge variant="confirmed">94% Confidence</Badge>
              </div>
              <p className="text-xs text-[var(--text-primary)] font-body leading-relaxed">
                Balaghat East fault line shows 4.8M tonnes high-grade Mn (44% grade) with high NDVI vegetation structural anomaly.
              </p>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-[var(--divider)]">
                <span className="text-[var(--text-muted)]">Target Depth:</span>
                <span className="font-mono font-semibold text-[var(--text-primary)]">140m – 180m</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[var(--divider)]">
                <span className="text-[var(--text-muted)]">Expected Ore Grade:</span>
                <span className="font-mono font-semibold text-[var(--mineral-orange)]">43.8% Mn</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[var(--divider)]">
                <span className="text-[var(--text-muted)]">Geological Vector:</span>
                <span className="font-mono font-semibold text-[var(--text-primary)]">Syncline South-East</span>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="button"
                onClick={() => navigate('/recommendations')}
                className="w-full btn-gradient justify-center text-xs py-2.5"
              >
                <span>Execute Drilling Simulation</span>
                <ArrowRight size={13} />
              </button>
            </div>
          </div>
        </Card>
      </div>

      {/* ── 4. Analytics Grid: Un-boxed Sections ──────────────────────────── */}
      <div>
        <h3 className="text-sm font-heading font-semibold text-[var(--text-primary)] uppercase tracking-wider mb-4">
          Geological &amp; Spectral Telemetry Grid
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* NDVI & Vegetation Structural Anomaly */}
          <Card title="NDVI &amp; Spectral Anomaly" subtitle="Satellite canopy index correlation with shallow manganese float">
            <div style={{ width: '100%', height: 180 }}>
              <ResponsiveContainer>
                <AreaChart data={ndviTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--divider)" strokeOpacity={0.6} />
                  <XAxis dataKey="month" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={30} />
                  <Tooltip content={<ModernTooltip unit="" />} />
                  <Area type="monotone" dataKey="ndvi" name="NDVI Index" stroke={COLOR_FOREST} fill="var(--accent-soft)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Reserve Probability Distribution */}
          <Card title="Reserve Probability" subtitle="Probability curve derived from Kriging spatial covariance">
            <div style={{ width: '100%', height: 180 }}>
              <ResponsiveContainer>
                <AreaChart data={ndviTrendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--divider)" strokeOpacity={0.6} />
                  <XAxis dataKey="month" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={30} />
                  <Tooltip content={<ModernTooltip unit="%" />} />
                  <Area type="monotone" dataKey="probability" name="Probability %" stroke={COLOR_MINERAL_ORANGE} fill="rgba(197,106,50,0.12)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Time-Series Production Trend */}
          <Card title="Production Velocity" subtitle="Monthly manganese extraction output against targets">
            <div style={{ width: '100%', height: 180 }}>
              <ResponsiveContainer>
                <BarChart data={monthlyProduction.slice(0, 6)} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--divider)" strokeOpacity={0.6} />
                  <XAxis dataKey="month" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} width={35} tickFormatter={v => `${v/1000}k`} />
                  <Tooltip content={<ModernTooltip unit="t" />} />
                  <Bar dataKey="actual" name="Output (t)" fill={COLOR_SECONDARY_GREEN} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      </div>

      {/* ── 5. Zone Table: Structured Discovery ───────────────────────────── */}
      <Card title="Exploration Zone Target Directory" subtitle="Prioritized list of manganese reserve discovery zones">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Zone ID</th>
                <th>Location / Belt</th>
                <th>Reserve Potential</th>
                <th>AI Confidence</th>
                <th>Geological Score</th>
                <th>NDVI Anomaly</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {zoneDiscoveryData.map((z, idx) => (
                <tr key={idx}>
                  <td className="font-mono font-semibold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)]">{z.zone}</td>
                  <td className="text-[var(--text-muted)]">{z.location}</td>
                  <td className="font-mono font-medium">{z.potential}</td>
                  <td className="font-mono font-semibold text-[var(--success)]">{z.confidence}%</td>
                  <td className="font-mono">{z.geoScore} / 10</td>
                  <td className="font-mono text-[var(--text-muted)]">{z.ndvi}</td>
                  <td>
                    <Badge variant={z.confidence >= 90 ? 'confirmed' : z.confidence >= 80 ? 'warning' : 'unconfirmed'}>
                      {z.status}
                    </Badge>
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() => navigate('/reserves')}
                      className="text-xs font-semibold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] hover:underline inline-flex items-center gap-1 cursor-pointer"
                    >
                      <span>Inspect</span>
                      <ArrowUpRight size={12} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── 6. AI Recommendation Panel & Risk Telemetry Feed ──────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentRiskEvents />

        <Card title="High-Potential Drilling Recommendations" subtitle="Optimal drill-hole locations based on satellite &amp; borehole cross-validation">
          <div className="space-y-3">
            <div className="p-3.5 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)]/50">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-mono font-bold text-[var(--text-primary)]">Borehole Site DH-Balaghat-44</span>
                <span className="text-[11px] font-mono text-[var(--success)] font-semibold">Priority 1 (96% Conf)</span>
              </div>
              <p className="text-xs text-[var(--text-muted)] mb-2">
                Evidence: High manganese float (44.2%), shallow overburden (18m), positive magnetic anomaly.
              </p>
              <div className="flex items-center justify-between pt-2 border-t border-[var(--divider)] text-[11px]">
                <span className="text-[var(--text-subtle)]">Recommended Depth: 160m</span>
                <button
                  type="button"
                  onClick={() => navigate('/recommendations')}
                  className="font-semibold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] hover:underline cursor-pointer"
                >
                  View Evidence Chain →
                </button>
              </div>
            </div>

            <div className="p-3.5 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)]/50">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-mono font-bold text-[var(--text-primary)]">Borehole Site DH-Bhandara-12</span>
                <span className="text-[11px] font-mono text-[var(--warning)] font-semibold">Priority 2 (87% Conf)</span>
              </div>
              <p className="text-xs text-[var(--text-muted)] mb-2">
                Evidence: Structural syncline fold intersection, satellite spectral absorption peak at 2.2µm.
              </p>
              <div className="flex items-center justify-between pt-2 border-t border-[var(--divider)] text-[11px]">
                <span className="text-[var(--text-subtle)]">Recommended Depth: 210m</span>
                <button
                  type="button"
                  onClick={() => navigate('/recommendations')}
                  className="font-semibold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)] hover:underline cursor-pointer"
                >
                  View Evidence Chain →
                </button>
              </div>
            </div>
          </div>
        </Card>
      </div>

    </div>
  );
}



