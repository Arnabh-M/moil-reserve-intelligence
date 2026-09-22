import React, { useState, useEffect, useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import {
  CloudRain,
  Droplets,
  Thermometer,
  Leaf,
  Satellite,
  AlertTriangle,
  RefreshCw,
  Clock,
} from 'lucide-react';

const SITE_ID_MAP = {
  1: 'balaghat',
  2: 'nagpur',
  3: 'bhandara',
  '1': 'balaghat',
  '2': 'nagpur',
  '3': 'bhandara',
  balaghat: 'balaghat',
  nagpur: 'nagpur',
  bhandara: 'bhandara',
};

function formatDisplayDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}

function CustomChartTooltip({ active, payload, label, unit, labelName, isNdvi }) {
  if (!active || !payload || !payload.length) return null;
  const item = payload[0];
  const val = item.value;
  const raw = item.payload;

  return (
    <div
      style={{
        background: 'hsl(var(--card))',
        border: '1px solid hsl(var(--border))',
        borderRadius: 6,
        padding: '8px 12px',
        boxShadow: '0 4px 14px rgba(0,0,0,0.14)',
        fontSize: 11,
        color: 'hsl(var(--foreground))',
        lineHeight: 1.4,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 4, color: 'hsl(var(--muted-foreground))' }}>
        {label ? new Date(label).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : ''}
      </div>
      {val != null ? (
        <div>
          <span style={{ color: item.color || item.fill, fontWeight: 700 }}>
            {labelName || item.name}:{' '}
          </span>
          <span className="mono" style={{ fontWeight: 600 }}>
            {typeof val === 'number' ? (unit === 'm³/m³' || unit === 'NDVI' ? val.toFixed(4) : val.toFixed(2)) : val}
          </span>{' '}
          {unit}
        </div>
      ) : (
        <div style={{ color: 'hsl(var(--muted-foreground))', fontStyle: 'italic' }}>
          No satellite retrieval (cloud or sensor gap)
        </div>
      )}
      {isNdvi && raw?.ndvi_age_days != null && raw.ndvi_age_days > 0 && (
        <div style={{ marginTop: 4, fontSize: 10, color: 'hsl(var(--primary))' }}>
          *Carried forward ({raw.ndvi_age_days}d since clear pass)
        </div>
      )}
    </div>
  );
}

export default function SatelliteConditionsPanel({ site }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [daysWindow, setDaysWindow] = useState(90);

  const siteKey = useMemo(() => {
    if (!site) return 'balaghat';
    if (typeof site === 'string') return site.toLowerCase();
    if (site.name && SITE_ID_MAP[site.name.toLowerCase()]) {
      return site.name.toLowerCase();
    }
    if (site.id && SITE_ID_MAP[site.id]) {
      return SITE_ID_MAP[site.id];
    }
    return 'balaghat';
  }, [site]);

  const loadData = () => {
    setLoading(true);
    setError(null);
    const basePath = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');
    const url = `${basePath}/satellite/site_daily_features.json`;

    fetch(url)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Failed to load satellite features (HTTP ${res.status})`);
        }
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        console.error('[SatelliteConditionsPanel] Error loading satellite features:', err);
        setError(err.message || 'Could not load satellite data');
        setLoading(false);
      });
  };

  useEffect(() => {
    loadData();
  }, []);

  const siteSeries = useMemo(() => {
    if (!data || !data.sites || !data.sites[siteKey]) return [];
    const all = data.sites[siteKey];
    return all.slice(-daysWindow);
  }, [data, siteKey, daysWindow]);

  const siteDisplayName = useMemo(() => {
    if (typeof site === 'object' && site?.name) return site.name;
    return siteKey.charAt(0).toUpperCase() + siteKey.slice(1);
  }, [site, siteKey]);

  return (
    <section className="card section-card" style={{ marginBottom: 16 }}>
      {/* Header */}
      <div
        className="card-head"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 12,
          paddingBottom: 14,
          borderBottom: '1px solid hsl(var(--border))',
          marginBottom: 16,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Satellite size={16} color="hsl(var(--primary))" />
            <h2 className="card-title" style={{ fontSize: 15 }}>
              Satellite conditions · {siteDisplayName}
            </h2>
            {data?.simulated && (
              <span className="pill warn" style={{ fontSize: 10, padding: '2px 7px' }}>
                Simulated data
              </span>
            )}
          </div>
          <div className="card-kicker" style={{ marginTop: 4 }}>
            CHIRPS · SMAP L4 · MODIS MOD11A1 · Sentinel-2 via Google Earth Engine
            {data?.latest_date && (
              <span style={{ marginLeft: 8, color: 'hsl(var(--muted-foreground))' }}>
                · Updated {data.latest_date}
              </span>
            )}
          </div>
        </div>

        {/* Days Window Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {[30, 90, 180].map((days) => (
            <button
              key={days}
              type="button"
              className={`btn small ${daysWindow === days ? 'primary' : 'ghost'}`}
              style={{ padding: '4px 9px', fontSize: 11 }}
              onClick={() => setDaysWindow(days)}
            >
              {days}d
            </button>
          ))}
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div style={{ padding: '30px 0', textAlign: 'center' }}>
          <div className="skeleton" style={{ width: '45%', height: 20, margin: '0 auto 12px' }} />
          <div className="skeleton" style={{ width: '80%', height: 180, margin: '0 auto' }} />
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="error-box" style={{ margin: '10px 0' }}>
          <strong>Could not load satellite conditions</strong>
          <p className="subhead" style={{ margin: '6px 0 10px' }}>
            {error}. Ensure the frontend satellite bundle exists in public/satellite.
          </p>
          <button className="btn small" onClick={loadData}>
            <RefreshCw size={13} style={{ marginRight: 5 }} /> Retry
          </button>
        </div>
      )}

      {/* 4 Compact Charts Grid */}
      {!loading && !error && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 16,
          }}
        >
          {/* Chart 1: Rainfall */}
          <div
            style={{
              background: 'hsl(var(--secondary) / .2)',
              border: '1px solid hsl(var(--border))',
              borderRadius: 8,
              padding: '12px 14px 8px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <CloudRain size={14} color="#0284c7" />
                <span style={{ fontSize: 12, fontWeight: 700 }}>Daily Rainfall</span>
              </div>
              <span className="mono" style={{ fontSize: 10, color: 'hsl(var(--muted-foreground))' }}>
                mm/day
              </span>
            </div>
            <div style={{ height: 130 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={siteSeries} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDisplayDate}
                    tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine={false}
                    tickLine={false}
                    minTickGap={25}
                  />
                  <YAxis
                    tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine={false}
                    tickLine={false}
                    width={32}
                  />
                  <Tooltip
                    content={
                      <CustomChartTooltip unit="mm" labelName="Rainfall" />
                    }
                  />
                  <Bar dataKey="rainfall_mm" fill="#0284c7" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: Soil Moisture */}
          <div
            style={{
              background: 'hsl(var(--secondary) / .2)',
              border: '1px solid hsl(var(--border))',
              borderRadius: 8,
              padding: '12px 14px 8px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Droplets size={14} color="#d97706" />
                <span style={{ fontSize: 12, fontWeight: 700 }}>Soil Moisture (0–5cm)</span>
              </div>
              <span className="mono" style={{ fontSize: 10, color: 'hsl(var(--muted-foreground))' }}>
                m³/m³
              </span>
            </div>
            <div style={{ height: 130 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={siteSeries} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                  <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDisplayDate}
                    tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine={false}
                    tickLine={false}
                    minTickGap={25}
                  />
                  <YAxis
                    tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine={false}
                    tickLine={false}
                    width={32}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip
                    content={
                      <CustomChartTooltip unit="m³/m³" labelName="Moisture" />
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="soil_moisture_m3m3"
                    stroke="#d97706"
                    strokeWidth={1.75}
                    dot={false}
                    connectNulls={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 3: Land Surface Temperature */}
          <div
            style={{
              background: 'hsl(var(--secondary) / .2)',
              border: '1px solid hsl(var(--border))',
              borderRadius: 8,
              padding: '12px 14px 8px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Thermometer size={14} color="#ea580c" />
                <span style={{ fontSize: 12, fontWeight: 700 }}>Daytime LST</span>
              </div>
              <span className="mono" style={{ fontSize: 10, color: 'hsl(var(--muted-foreground))' }}>
                °C
              </span>
            </div>
            <div style={{ height: 130 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={siteSeries} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                  <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDisplayDate}
                    tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine={false}
                    tickLine={false}
                    minTickGap={25}
                  />
                  <YAxis
                    tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine={false}
                    tickLine={false}
                    width={32}
                    domain={['auto', 'auto']}
                  />
                  <Tooltip
                    content={
                      <CustomChartTooltip unit="°C" labelName="LST Day" />
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="lst_day_c"
                    stroke="#ea580c"
                    strokeWidth={1.75}
                    dot={false}
                    connectNulls={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 4: Vegetation Index (NDVI) */}
          <div
            style={{
              background: 'hsl(var(--secondary) / .2)',
              border: '1px solid hsl(var(--border))',
              borderRadius: 8,
              padding: '12px 14px 8px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Leaf size={14} color="#16a34a" />
                <span style={{ fontSize: 12, fontWeight: 700 }}>Vegetation (NDVI)</span>
              </div>
              <span className="mono" style={{ fontSize: 10, color: 'hsl(var(--muted-foreground))' }}>
                index [-1, 1]
              </span>
            </div>
            <div style={{ height: 130 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={siteSeries} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                  <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={formatDisplayDate}
                    tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine={false}
                    tickLine={false}
                    minTickGap={25}
                  />
                  <YAxis
                    tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }}
                    axisLine={false}
                    tickLine={false}
                    width={32}
                    domain={[0, 1]}
                  />
                  <Tooltip
                    content={
                      <CustomChartTooltip unit="NDVI" labelName="NDVI" isNdvi />
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="ndvi"
                    stroke="#16a34a"
                    strokeWidth={1.75}
                    dot={false}
                    connectNulls={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
