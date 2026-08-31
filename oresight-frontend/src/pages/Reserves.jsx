import React, { useState, useMemo } from 'react';
import {
  BarChart, Bar, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, ZAxis,
} from 'recharts';
import { Mountain, Gem, CheckCircle, Layers } from 'lucide-react';
import { Card, KPIStat, Badge } from '../components';
import { deposits, gradeDistribution, sites } from '../data/mockData';

const COLORS = {
  orange: '#e0793a',
  orangeSoft: '#f2a768',
  teal: '#2a7f8c',
  navy: '#101a2b',
  navy2: '#16233a',
  muted: '#8896a8',
  success: '#22c55e',
};

const SITE_COLORS = {
  balaghat: '#e0793a',
  nagpur: '#2a7f8c',
  bhandara: '#16233a',
};

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload;
  if (!data) return null;
  return (
    <div className="bg-navy text-white px-3 py-2 rounded-lg shadow-lg text-xs">
      {data.id && <p className="font-semibold mb-1">{data.id}</p>}
      {data.range && <p>Range: {data.range}% Mn</p>}
      {data.count !== undefined && <p>Count: {data.count} deposits</p>}
      {data.depth_m !== undefined && <p>Depth: {data.depth_m}m</p>}
      {data.grade_percent !== undefined && <p>Grade: {data.grade_percent}% Mn</p>}
      {data.site_id && <p className="capitalize">Site: {data.site_id}</p>}
      {data.confirmed !== undefined && <p>Status: {data.confirmed ? 'Confirmed' : 'Unconfirmed'}</p>}
    </div>
  );
};

export default function Reserves() {
  const [sortBy, setSortBy] = useState('grade_percent');
  const [sortDir, setSortDir] = useState('desc');
  const [filterSite, setFilterSite] = useState('all');

  const confirmedCount = deposits.filter(d => d.confirmed).length;
  const avgGrade = (deposits.reduce((s, d) => s + d.grade_percent, 0) / deposits.length).toFixed(1);
  const avgConfirmedGrade = (
    deposits.filter(d => d.confirmed).reduce((s, d) => s + d.grade_percent, 0) / confirmedCount
  ).toFixed(1);

  const filteredDeposits = useMemo(() => {
    let data = filterSite === 'all' ? deposits : deposits.filter(d => d.site_id === filterSite);
    return [...data].sort((a, b) => {
      const aVal = a[sortBy];
      const bVal = b[sortBy];
      return sortDir === 'asc' ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
    });
  }, [sortBy, sortDir, filterSite]);

  const handleSort = (col) => {
    if (sortBy === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(col);
      setSortDir('desc');
    }
  };

  // Per-site summaries
  const siteSummaries = sites.map(site => {
    const siteDeposits = deposits.filter(d => d.site_id === site.id);
    const confirmed = siteDeposits.filter(d => d.confirmed).length;
    const avg = (siteDeposits.reduce((s, d) => s + d.grade_percent, 0) / siteDeposits.length).toFixed(1);
    return {
      ...site,
      total: siteDeposits.length,
      confirmed,
      avgGrade: avg,
      confirmedPct: Math.round((confirmed / siteDeposits.length) * 100),
    };
  });

  return (
    <div className="page-container">
      <h2 className="page-title">Reserves & Deposits</h2>
      <p className="page-subtitle">Geological deposit inventory, grade analysis, and confirmation status</p>

      {/* KPI Row */}
      <div className="grid-kpi stagger-children">
        <KPIStat
          label="Total Deposits"
          value={deposits.length}
          delta={null}
          deltaLabel="surveyed locations"
          icon={Mountain}
          color="navy"
        />
        <KPIStat
          label="Confirmed Deposits"
          value={confirmedCount}
          delta={null}
          deltaLabel={`${Math.round((confirmedCount / deposits.length) * 100)}% confirmation rate`}
          icon={CheckCircle}
          color="success"
        />
        <KPIStat
          label="Avg Mn Grade"
          value={`${avgGrade}%`}
          delta={null}
          deltaLabel={`${avgConfirmedGrade}% for confirmed`}
          icon={Gem}
          color="orange"
        />
        <KPIStat
          label="Sites Covered"
          value={sites.length}
          delta={null}
          deltaLabel="across 2 belts"
          icon={Layers}
          color="teal"
        />
      </div>

      {/* Charts Row */}
      <div className="grid-2">
        {/* Grade Distribution */}
        <Card title="Grade Distribution" subtitle="Mn grade (%) across all deposits">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <BarChart data={gradeDistribution} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e7ee" />
                <XAxis dataKey="range" tick={{ fontSize: 11, fill: COLORS.muted }} label={{ value: '% Mn Grade', position: 'insideBottom', offset: -2, fontSize: 10, fill: COLORS.muted }} />
                <YAxis tick={{ fontSize: 10, fill: COLORS.muted }} label={{ value: 'Deposits', angle: -90, position: 'insideLeft', fontSize: 10, fill: COLORS.muted }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" fill={COLORS.teal} radius={[6, 6, 0, 0]} barSize={40}>
                  {gradeDistribution.map((entry, idx) => (
                    <Cell key={idx} fill={idx >= 3 ? COLORS.orange : COLORS.teal} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Depth vs Grade Scatter */}
        <Card title="Depth vs Grade" subtitle="Colored by site, sized by confirmation">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer>
              <ScatterChart margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e7ee" />
                <XAxis
                  type="number" dataKey="depth_m" name="Depth"
                  tick={{ fontSize: 10, fill: COLORS.muted }}
                  label={{ value: 'Depth (m)', position: 'insideBottom', offset: -2, fontSize: 10, fill: COLORS.muted }}
                />
                <YAxis
                  type="number" dataKey="grade_percent" name="Grade"
                  tick={{ fontSize: 10, fill: COLORS.muted }}
                  label={{ value: 'Grade (%)', angle: -90, position: 'insideLeft', fontSize: 10, fill: COLORS.muted }}
                />
                <ZAxis type="number" dataKey="confirmed" range={[40, 100]} name="Confirmed" />
                <Tooltip content={<CustomTooltip />} />
                {sites.map(site => (
                  <Scatter
                    key={site.id}
                    name={site.name.replace(' Mine', '')}
                    data={deposits.filter(d => d.site_id === site.id)}
                    fill={SITE_COLORS[site.id]}
                    fillOpacity={0.7}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-4 mt-2 justify-center">
            {sites.map(site => (
              <div key={site.id} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: SITE_COLORS[site.id] }} />
                <span className="text-xs text-text-muted">{site.name.replace(' Mine', '')}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Site Summary Cards */}
      <div className="grid-3 mb-1.5">
        {siteSummaries.map(site => (
          <Card key={site.id}>
            <div className="flex items-center gap-2 mb-3">
              <span className="w-3 h-3 rounded-full" style={{ backgroundColor: SITE_COLORS[site.id] }} />
              <h4 className="text-sm font-semibold text-text-primary">{site.name}</h4>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-lg font-bold text-text-primary">{site.total}</p>
                <p className="text-[10px] text-text-muted">Deposits</p>
              </div>
              <div>
                <p className="text-lg font-bold text-success">{site.confirmed}</p>
                <p className="text-[10px] text-text-muted">Confirmed</p>
              </div>
              <div>
                <p className="text-lg font-bold text-orange">{site.avgGrade}%</p>
                <p className="text-[10px] text-text-muted">Avg Grade</p>
              </div>
            </div>
            <div className="mt-3 pt-2 border-t border-border">
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-muted">Confirmation Rate</span>
                <Badge variant={site.confirmedPct >= 60 ? 'operational' : 'warning'}>{site.confirmedPct}%</Badge>
              </div>
              <div className="w-full bg-bg rounded-full h-1.5 mt-1.5 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${site.confirmedPct}%`, backgroundColor: SITE_COLORS[site.id] }}
                />
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Deposit Table */}
      <Card title="Deposit Inventory" subtitle={`${filteredDeposits.length} deposits`}
        action={
          <div className="flex gap-1 p-0.5 bg-bg rounded-lg border border-border">
            {['all', ...sites.map(s => s.id)].map(s => (
              <button
                key={s}
                onClick={() => setFilterSite(s)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                  filterSite === s ? 'bg-white text-text-primary shadow-sm' : 'text-text-muted hover:text-text-primary'
                }`}
              >
                {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        }
      >
        <div className="max-h-80 overflow-y-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th className="cursor-pointer hover:text-text-primary" onClick={() => handleSort('site_id')}>
                  Site {sortBy === 'site_id' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th>Lat / Lon</th>
                <th className="cursor-pointer hover:text-text-primary" onClick={() => handleSort('depth_m')}>
                  Depth {sortBy === 'depth_m' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th className="cursor-pointer hover:text-text-primary" onClick={() => handleSort('grade_percent')}>
                  Mn Grade {sortBy === 'grade_percent' ? (sortDir === 'asc' ? '↑' : '↓') : ''}
                </th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredDeposits.map(d => (
                <tr key={d.id}>
                  <td className="font-mono text-xs">{d.id}</td>
                  <td className="capitalize">{d.site_id}</td>
                  <td className="text-xs text-text-muted">{d.lat.toFixed(4)}, {d.lon.toFixed(4)}</td>
                  <td>{d.depth_m}m</td>
                  <td>
                    <span className={`font-semibold ${d.grade_percent >= 30 ? 'text-orange' : d.grade_percent >= 15 ? 'text-teal' : 'text-text-secondary'}`}>
                      {d.grade_percent}%
                    </span>
                  </td>
                  <td>
                    <Badge variant={d.confirmed ? 'confirmed' : 'unconfirmed'}>
                      {d.confirmed ? 'Confirmed' : 'Unconfirmed'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
