import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { Mountain, Target, Gem, Layers } from 'lucide-react';
import { Card, KPIStat, Badge, EmptyState, ErrorState, SkeletonKPIRow, SkeletonCard, SectionDivider } from '../components';
import { getSites, getReserveZones } from '../api/client';

const SITE_COLORS = {
  1: '#C1571E', // Balaghat - warm terracotta
  2: '#706B62', // Nagpur - slate neutral
  3: '#4A7A4E', // Bhandara - forest green
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
    <div className="bg-[var(--bg-elevated)] text-[var(--text-primary)] px-3 py-2 rounded-lg border border-[var(--divider)] shadow-md text-xs">
      {data.zone_name && <p className="font-semibold mb-1 text-[var(--text-primary)]">{data.zone_name}</p>}
      {data.range && <p className="text-[var(--text-muted)]">Range: {data.range}% Mn</p>}
      {data.count !== undefined && <p className="text-[var(--text-muted)]">Count: {data.count} zones</p>}
      {data.confidence_score !== undefined && <p className="text-[var(--text-muted)]">Confidence: {Math.round(data.confidence_score * 100)}%</p>}
      {data.estimated_grade_pct !== undefined && <p className="text-[var(--text-muted)]">Grade: {data.estimated_grade_pct}% Mn</p>}
      {data.siteName && <p className="text-[var(--text-muted)]">Site: {data.siteName}</p>}
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

  const totalZones = zones.length;
  const avgConfidence = totalZones > 0
    ? Math.round((zones.reduce((s, z) => s + (z.confidence_score || 0), 0) / totalZones) * 100)
    : null;
  const grades = zones.map(z => z.estimated_grade_pct).filter(g => typeof g === 'number');
  const avgGrade = grades.length > 0
    ? (grades.reduce((s, g) => s + g, 0) / grades.length).toFixed(1)
    : null;

  const gradeDistribution = useMemo(() => {
    const buckets = [
      { range: '<30', min: 0, max: 30, count: 0 },
      { range: '30-35', min: 30, max: 35, count: 0 },
      { range: '35-40', min: 35, max: 40, count: 0 },
      { range: '40-45', min: 40, max: 45, count: 0 },
      { range: '45+', min: 45, max: 100, count: 0 },
    ];
    zones.forEach(z => {
      const g = z.estimated_grade_pct;
      if (typeof g === 'number') {
        const bucket = buckets.find(b => g >= b.min && (b.max === 100 ? g <= b.max : g < b.max));
        if (bucket) bucket.count++;
      }
    });
    return buckets;
  }, [zones]);

  const siteSummaries = useMemo(() => {
    return sites.map(s => {
      const siteZones = zones.filter(z => z.site_id === s.id);
      const cScores = siteZones.map(z => z.confidence_score).filter(c => typeof c === 'number');
      const gScores = siteZones.map(z => z.estimated_grade_pct).filter(g => typeof g === 'number');
      return {
        id: s.id,
        name: s.name,
        count: siteZones.length,
        avgConfidence: cScores.length ? cScores.reduce((a, b) => a + b, 0) / cScores.length : null,
        avgGrade: gScores.length ? gScores.reduce((a, b) => a + b, 0) / gScores.length : null,
      };
    });
  }, [sites, zones]);

  if (loading) {
    return (
      <div className="page-container">
        <div className="h-6 bg-[var(--divider)] rounded w-48 mb-3 animate-pulse" />
        <div className="h-4 bg-[var(--divider)]/50 rounded w-72 mb-8 animate-pulse" />
        <SkeletonKPIRow count={4} />
        <div className="mt-8">
          <SkeletonCard lines={4} />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container">
        <ErrorState title="Failed to load reserve data" message={error} onRetry={loadData} />
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div className="mb-10">
        <h1 className="page-title">Reserve Intelligence &amp; Deposits</h1>
        <p className="page-subtitle">Geological deposit classification, grade estimation, and spatial confidence analysis</p>
      </div>

      {/* Stacked KPI Row — No Card Boxes */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-12">
        <KPIStat
          label="Total Reserve Zones"
          value={totalZones}
          deltaLabel="mapped &amp; classified"
          icon={Mountain}
        />
        <KPIStat
          label="Avg Confidence"
          value={avgConfidence != null ? `${avgConfidence}%` : '—'}
          deltaLabel="Kriging spatial model"
          icon={Target}
        />
        <KPIStat
          label="Avg Mn Grade"
          value={avgGrade != null ? `${avgGrade}%` : '—'}
          deltaLabel="estimated, all zones"
          icon={Gem}
        />
        <KPIStat
          label="Sites Covered"
          value={sites.length}
          deltaLabel="active mine sites"
          icon={Layers}
        />
      </div>

      <SectionDivider />

      {/* Charts Row */}
      <div className="grid-2 mb-10">
        {/* Grade Distribution */}
        <Card title="Grade Distribution" subtitle="Estimated manganese grade (%) breakdown across zones">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={gradeDistribution} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--divider)" strokeOpacity={0.7} />
                <XAxis dataKey="range" tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }} axisLine={false} tickLine={false} width={36} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--divider)', fillOpacity: 0.3 }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} barSize={32}>
                  {gradeDistribution.map((entry, idx) => (
                    <Cell key={idx} fill={idx >= 3 ? '#C1571E' : '#706B62'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Confidence vs Grade Scatter */}
        <Card title="Confidence vs Grade" subtitle="Each point represents one reserve zone, colored by site">
          {totalZones === 0 ? (
            <EmptyState title="No reserve zones" message="No reserve zone data available to plot." tone="neutral" compact />
          ) : (
            <>
              <div style={{ width: '100%', height: 260 }}>
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--divider)" strokeOpacity={0.7} />
                    <XAxis
                      type="number" dataKey="confidence_score" name="Confidence"
                      domain={[0, 1]}
                      tickFormatter={v => `${Math.round(v * 100)}%`}
                      tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="number" dataKey="estimated_grade_pct" name="Grade"
                      tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'Inter, sans-serif' }}
                      axisLine={false}
                      tickLine={false}
                      width={36}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    {sites.map(site => (
                      <Scatter
                        key={site.id}
                        name={site.name}
                        data={zonesWithSiteName.filter(z => z.site_id === site.id)}
                        fill={SITE_COLORS[site.id] || '#8A8578'}
                        fillOpacity={0.8}
                      />
                    ))}
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              <div className="flex items-center gap-5 mt-2 justify-center">
                {sites.map(site => (
                  <div key={site.id} className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: SITE_COLORS[site.id] || '#8A8578' }} />
                    <span>{site.name}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>
      </div>

      <SectionDivider />

      {/* Site Summary Blocks */}
      <div className="grid-3 mb-10">
        {siteSummaries.map(site => {
          const confidencePct = site.avgConfidence != null ? Math.round(site.avgConfidence * 100) : null;
          return (
            <div key={site.id} className="bg-[var(--bg-elevated)]/50 rounded-xl p-5 border border-[var(--divider)]">
              <div className="flex items-center gap-2.5 mb-4">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: SITE_COLORS[site.id] || '#8A8578' }} />
                <h4 className="text-sm font-semibold text-[var(--text-primary)]">{site.name}</h4>
              </div>
              <div className="grid grid-cols-3 gap-3 text-left">
                <div>
                  <p className="text-[10px] uppercase font-semibold text-[var(--text-muted)] mb-1">Zones</p>
                  <p className="text-xl font-semibold text-[var(--text-primary)]">{site.count}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase font-semibold text-[var(--text-muted)] mb-1">Confidence</p>
                  <p className="text-xl font-semibold text-[var(--success)]">{confidencePct != null ? `${confidencePct}%` : '—'}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase font-semibold text-[var(--text-muted)] mb-1">Avg Grade</p>
                  <p className="text-xl font-semibold text-[var(--accent-primary)]">{site.avgGrade != null ? `${site.avgGrade.toFixed(1)}%` : '—'}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <SectionDivider />

      {/* Zone Table */}
      <div>
        <div className="flex items-center justify-between gap-4 mb-4 flex-wrap">
          <div>
            <h3 className="text-base font-semibold text-[var(--text-primary)]">Reserve Zone Inventory</h3>
            <p className="text-xs text-[var(--text-muted)]">{filteredZones.length} classified deposit zones</p>
          </div>
          <div className="flex items-center gap-1">
            {['all', ...sites.map(s => s.id)].map(s => (
              <button
                key={s}
                onClick={() => setFilterSite(s)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                  filterSite === s
                    ? 'bg-[var(--accent-soft)] text-[var(--accent-primary)] font-semibold'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                }`}
              >
                {s === 'all' ? 'All Sites' : (siteNameById[s] || `Site ${s}`).replace(' Mine', '')}
              </button>
            ))}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('zone_name')} className="cursor-pointer">Zone Name</th>
                <th onClick={() => handleSort('site_id')} className="cursor-pointer">Site</th>
                <th onClick={() => handleSort('estimated_grade_pct')} className="cursor-pointer">Est. Grade (% Mn)</th>
                <th onClick={() => handleSort('confidence_score')} className="cursor-pointer">Confidence Score</th>
                <th>Classification</th>
              </tr>
            </thead>
            <tbody>
              {filteredZones.map(z => {
                const tier = confidenceTier(z.confidence_score);
                return (
                  <tr key={z.id || z.zone_id || z.zone_name}>
                    <td className="font-medium text-[var(--text-primary)]">{z.zone_name}</td>
                    <td className="text-[var(--text-muted)]">{z.siteName}</td>
                    <td className="font-mono">{z.estimated_grade_pct != null ? `${z.estimated_grade_pct}%` : '—'}</td>
                    <td className="font-mono">
                      {z.confidence_score != null ? `${Math.round(z.confidence_score * 100)}%` : '—'}
                    </td>
                    <td>
                      <Badge variant={tier.variant}>{tier.label}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


