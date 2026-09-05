import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { Mountain, Target, Gem, Layers } from 'lucide-react';
import { Card, KPIStat, Badge, EmptyState, ErrorState, SkeletonKPIRow, SkeletonCard } from '../components';
import { getSites, getReserveZones, USE_MOCK } from '../api/client';

const COLORS = {
  orange: '#e0793a',
  teal: '#2a7f8c',
  muted: '#8896a8',
  success: '#22c55e',
};

// Keyed by numeric site id (GET /sites), not the string slugs mockData used.
const SITE_COLORS = {
  1: '#e0793a', // Balaghat
  2: '#2a7f8c', // Nagpur
  3: '#16233a', // Bhandara
};

function confidenceTier(score) {
  if (score == null) return { label: 'Unknown', variant: 'unconfirmed' };
  if (score >= 0.7) return { label: 'High', variant: 'confirmed' };
  if (score >= 0.4) return { label: 'Medium', variant: 'warning' };
  return { label: 'Low', variant: 'unconfirmed' };
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload;
  if (!data) return null;
  return (
    <div className="bg-navy text-white px-3 py-2 rounded-lg shadow-lg text-xs">
      {data.zone_name && <p className="font-semibold mb-1">{data.zone_name}</p>}
      {data.range && <p>Range: {data.range}% Mn</p>}
      {data.count !== undefined && <p>Count: {data.count} zones</p>}
      {data.confidence_score !== undefined && <p>Confidence: {Math.round(data.confidence_score * 100)}%</p>}
      {data.estimated_grade_pct !== undefined && <p>Grade: {data.estimated_grade_pct}% Mn</p>}
      {data.siteName && <p>Site: {data.siteName}</p>}
    </div>
  );
};

export default function Reserves() {
  const [sites, setSites] = useState([]);
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [sortBy, setSortBy] = useState('estimated_grade_pct');
  const [sortDir, setSortDir] = useState('desc');
  const [filterSite, setFilterSite] = useState('all');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sitesData, zonesGeo] = await Promise.all([getSites(), getReserveZones()]);
      setSites(sitesData || []);
      const features = Array.isArray(zonesGeo?.features) ? zonesGeo.features : [];
      setZones(features.map(f => ({ ...f.properties })));
    } catch (err) {
      console.error('[Reserves] Failed to load reserve zone data:', err);
      setError(err.message || 'Failed to load reserve zone data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const siteNameById = useMemo(
    () => Object.fromEntries(sites.map(s => [s.id, s.name])),
    [sites]
  );

  const zonesWithSiteName = useMemo(
    () => zones.map(z => ({ ...z, siteName: siteNameById[z.site_id] || `Site ${z.site_id}` })),
    [zones, siteNameById]
  );

  const filteredZones = useMemo(() => {
    let data = filterSite === 'all' ? zonesWithSiteName : zonesWithSiteName.filter(z => z.site_id === filterSite);
    return [...data].sort((a, b) => {
      const aVal = a[sortBy];
      const bVal = b[sortBy];
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      return sortDir === 'asc' ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
    });
  }, [zonesWithSiteName, sortBy, sortDir, filterSite]);

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir('desc');
    }
  };

  // Grade histogram — same 10%-wide binning the page always used, just fed
  // by real zone.estimated_grade_pct instead of fabricated deposit rows.
  const gradeDistribution = useMemo(() => {
    const bins = [
      { range: '0-10', count: 0 },
      { range: '10-20', count: 0 },
      { range: '20-30', count: 0 },
      { range: '30-40', count: 0 },
      { range: '40-50', count: 0 },
    ];
    zones.forEach(z => {
      if (z.estimated_grade_pct == null) return;
      const idx = Math.max(0, Math.min(Math.floor(z.estimated_grade_pct / 10), 4));
      bins[idx].count++;
    });
    return bins;
  }, [zones]);

  const siteSummaries = useMemo(() => sites.map(site => {
    const siteZones = zones.filter(z => z.site_id === site.id);
    const count = siteZones.length;
    const avgConfidence = count
      ? siteZones.reduce((s, z) => s + (z.confidence_score || 0), 0) / count
      : null;
    const avgGrade = count
      ? siteZones.reduce((s, z) => s + (z.estimated_grade_pct || 0), 0) / count
      : null;
    return { ...site, count, avgConfidence, avgGrade };
  }), [sites, zones]);

  const totalZones = zones.length;
  const avgConfidencePct = totalZones
    ? Math.round((zones.reduce((s, z) => s + (z.confidence_score || 0), 0) / totalZones) * 100)
    : null;
  const avgGrade = totalZones
    ? (zones.reduce((s, z) => s + (z.estimated_grade_pct || 0), 0) / totalZones).toFixed(1)
    : null;

  // ── Error state: entire page failed ──────────────────────────────────
  if (!loading && error) {
    return (
      <div className="page-container">
        <ErrorState title="Failed to load reserve data" message={error} onRetry={loadData} />
      </div>
    );
  }

  // ── Loading state ────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="page-container">
        <div className="h-8 bg-border/70 rounded w-72 mb-2 animate-pulse" />
        <div className="h-4 bg-border/50 rounded w-96 mb-6 animate-pulse" />
        <SkeletonKPIRow count={4} />
        <div className="grid-2 mt-6">
          <SkeletonCard lines={5} />
          <SkeletonCard lines={5} />
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="flex items-start justify-between mb-1">
        <div>
          <h2 className="page-title">Geological Structure &amp; Cross-Section</h2>
          <p className="page-subtitle">Reserve zone inventory, grade analysis, and confidence scoring</p>
        </div>
        {USE_MOCK && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-600 text-xs font-bold shadow-xs animate-fade-in shrink-0">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            USE_MOCK = true (Simulated API)
          </div>
        )}
      </div>

      {/* KPI Row */}
      <div className="grid-kpi stagger-children">
        <KPIStat
          label="Total Reserve Zones"
          value={totalZones}
          delta={null}
          deltaLabel="surveyed zones"
          icon={Mountain}
          color="navy"
        />
        <KPIStat
          label="Avg Confidence"
          value={avgConfidencePct != null ? `${avgConfidencePct}%` : '—'}
          delta={null}
          deltaLabel="across all zones"
          icon={Target}
          color="success"
        />
        <KPIStat
          label="Avg Mn Grade"
          value={avgGrade != null ? `${avgGrade}%` : '—'}
          delta={null}
          deltaLabel="estimated, all zones"
          icon={Gem}
          color="orange"
        />
        <KPIStat
          label="Sites Covered"
          value={sites.length}
          delta={null}
          deltaLabel="active mine sites"
          icon={Layers}
          color="teal"
        />
      </div>

      {/* Charts Row */}
      <div className="grid-2">
        {/* Grade Distribution */}
        <Card title="Grade Distribution" subtitle="Estimated Mn grade (%) across reserve zones">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={gradeDistribution} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.6} />
                <XAxis dataKey="range" tick={{ fontSize: 11, fill: COLORS.muted }} axisLine={{ stroke: 'var(--border)' }} tickLine={false} label={{ value: '% Mn Grade', position: 'insideBottom', offset: -2, fontSize: 10, fill: COLORS.muted }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: COLORS.muted }} axisLine={false} tickLine={false} width={36} label={{ value: 'Zones', angle: -90, position: 'insideLeft', fontSize: 10, fill: COLORS.muted }} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--border)', fillOpacity: 0.25 }} />
                <Bar dataKey="count" fill={COLORS.teal} radius={[4, 4, 0, 0]} barSize={34}>
                  {gradeDistribution.map((entry, idx) => (
                    <Cell key={idx} fill={idx >= 3 ? COLORS.orange : COLORS.teal} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Confidence vs Grade Scatter */}
        <Card title="Confidence vs Grade" subtitle="Each point is one reserve zone, colored by site">
          {totalZones === 0 ? (
            <EmptyState
              title="No reserve zones"
              message="No reserve zone data available to plot."
              tone="neutral"
              compact
            />
          ) : (
            <>
              <div style={{ width: '100%', height: 280 }}>
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.6} />
                    <XAxis
                      type="number" dataKey="confidence_score" name="Confidence"
                      domain={[0, 1]}
                      tickFormatter={v => `${Math.round(v * 100)}%`}
                      tick={{ fontSize: 10, fill: COLORS.muted }}
                      axisLine={{ stroke: 'var(--border)' }}
                      tickLine={false}
                      label={{ value: 'Confidence', position: 'insideBottom', offset: -2, fontSize: 10, fill: COLORS.muted }}
                    />
                    <YAxis
                      type="number" dataKey="estimated_grade_pct" name="Grade"
                      tick={{ fontSize: 10, fill: COLORS.muted }}
                      axisLine={false}
                      tickLine={false}
                      label={{ value: 'Grade (%)', angle: -90, position: 'insideLeft', fontSize: 10, fill: COLORS.muted }}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    {sites.map(site => (
                      <Scatter
                        key={site.id}
                        name={site.name}
                        data={zonesWithSiteName.filter(z => z.site_id === site.id)}
                        fill={SITE_COLORS[site.id] || COLORS.muted}
                        fillOpacity={0.75}
                      />
                    ))}
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              <div className="flex items-center gap-4 mt-2 justify-center">
                {sites.map(site => (
                  <div key={site.id} className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: SITE_COLORS[site.id] || COLORS.muted }} />
                    <span className="text-xs text-text-muted">{site.name}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      {/* Site Summary Cards */}
      <div className="grid-3">
        {siteSummaries.map(site => {
          const confidencePct = site.avgConfidence != null ? Math.round(site.avgConfidence * 100) : null;
          return (
            <Card key={site.id}>
              <div className="flex items-center gap-2 mb-3">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: SITE_COLORS[site.id] || COLORS.muted }} />
                <h4 className="text-sm font-semibold text-text-primary">{site.name}</h4>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="text-lg font-bold text-text-primary">{site.count}</p>
                  <p className="text-[10px] text-text-muted">Zones</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-success">{confidencePct != null ? `${confidencePct}%` : '—'}</p>
                  <p className="text-[10px] text-text-muted">Avg Confidence</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-orange">{site.avgGrade != null ? `${site.avgGrade.toFixed(1)}%` : '—'}</p>
                  <p className="text-[10px] text-text-muted">Avg Grade</p>
                </div>
              </div>
              <div className="mt-3 pt-2 border-t border-border">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">Confidence Level</span>
                  <Badge variant={confidencePct != null && confidencePct >= 60 ? 'operational' : 'warning'}>
                    {confidencePct != null ? `${confidencePct}%` : '—'}
                  </Badge>
                </div>
                <div className="w-full bg-bg rounded-full h-1.5 mt-1.5 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${confidencePct || 0}%`, backgroundColor: SITE_COLORS[site.id] || COLORS.muted }}
                  />
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Zone Table */}
      <Card title="Reserve Zone Inventory" subtitle={`${filteredZones.length} zones`}
        action={
          <div className="flex gap-1 p-0.5 bg-bg rounded-lg border border-border">
            {['all', ...sites.map(s => s.id)].map(s => (
              <button
                key={s}
                onClick={() => setFilterSite(s)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors duration-150 ${
                  filterSite === s ? 'bg-bg-surface text-text-primary shadow-sm' : 'text-text-muted hover:text-text-primary'
                }`}
              >
                {s === 'all' ? 'All' : siteNameById[s] || s}
              </button>
            ))}
          </div>
        }
      >
        <div className="max-h-80 overflow-y-auto">
          {filteredZones.length === 0 ? (
            <EmptyState
              title="No reserve zones recorded"
              message="Reserve zone data will appear here once available."
              tone="neutral"
            />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th className="cursor-pointer hover:text-text-primary transition-colors duration-150" onClick={() => handleSort('siteName')}>
                    Site {sortBy === 'siteName' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                  </th>
                  <th>Zone Name</th>
                  <th className="cursor-pointer hover:text-text-primary transition-colors duration-150" onClick={() => handleSort('confidence_score')}>
                    Confidence {sortBy === 'confidence_score' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                  </th>
                  <th className="cursor-pointer hover:text-text-primary transition-colors duration-150" onClick={() => handleSort('estimated_grade_pct')}>
                    Mn Grade {sortBy === 'estimated_grade_pct' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredZones.map(z => {
                  const tier = confidenceTier(z.confidence_score);
                  return (
                    <tr key={z.id}>
                      <td className="font-mono text-xs">{z.id}</td>
                      <td>{z.siteName}</td>
                      <td className="text-xs text-text-secondary">{z.zone_name || '—'}</td>
                      <td>
                        <Badge variant={tier.variant}>
                          {tier.label} · {z.confidence_score != null ? `${Math.round(z.confidence_score * 100)}%` : '—'}
                        </Badge>
                      </td>
                      <td>
                        <span className={`font-semibold ${z.estimated_grade_pct >= 30 ? 'text-orange' : z.estimated_grade_pct >= 15 ? 'text-teal' : 'text-text-secondary'}`}>
                          {z.estimated_grade_pct != null ? `${z.estimated_grade_pct}%` : '—'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </Card>
    </div>
  );
}
