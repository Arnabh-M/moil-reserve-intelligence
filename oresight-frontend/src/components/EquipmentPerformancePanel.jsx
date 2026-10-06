import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, ArrowDown, ArrowUp, ClipboardList, RefreshCw, Truck, X } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../api/client';

// Equipment performance for one site: availability, MTBF/MTTR, failures and
// maintenance-due state, over a selectable window. Reads GET /equipment/metrics
// (site-scoped); see the backend's docs/EQUIPMENT_METRICS.md for every formula.
//
// Styling uses the live theme classes from index.css (card/section-card, pill,
// table-wrap, progress) rather than components/Card.jsx + components/Badge.jsx,
// which reference a --success/--bg-surface token set that index.css never
// defines and which nothing in the app imports.

const WINDOW_OPTIONS = [30, 90, 180];

// Maintenance status -> the live `pill` variants. Same good/warn/critical
// ladder lib/confidence.js uses for zone tiers, plus the neutral pill for the
// fourth state confidence.js has no equivalent of ("never maintained").
const MAINTENANCE_PILLS = {
  ok: { className: 'good', label: 'OK' },
  due_soon: { className: 'warn', label: 'Due soon' },
  overdue: { className: 'critical', label: 'Overdue' },
  unknown: { className: 'neutral', label: 'Unknown' },
};

const COLUMNS = [
  { key: 'name', label: 'Equipment', align: 'left' },
  { key: 'equipment_type', label: 'Type', align: 'left' },
  { key: 'status', label: 'Status', align: 'left' },
  { key: 'physical_availability_pct', label: 'Physical avail.', align: 'left', numeric: true },
  { key: 'mtbf_hours', label: 'MTBF (h)', align: 'right', numeric: true },
  { key: 'mttr_hours', label: 'MTTR (h)', align: 'right', numeric: true },
  { key: 'failures', label: 'Failures', align: 'right', numeric: true },
  { key: 'downtime_hours', label: 'Downtime (h)', align: 'right', numeric: true },
  { key: 'utilisation_pct', label: 'Utilisation', align: 'right', sortable: false },
  { key: 'top_failure_reason', label: 'Top failure reason', align: 'left' },
  { key: 'maintenance_status', label: 'Maintenance', align: 'left' },
];

// Nulls always sort last, whichever direction is active -- a machine with no
// failures (null MTBF/MTTR by contract) shouldn't read as the best or worst.
function compareRows(a, b, key, direction) {
  const left = a[key];
  const right = b[key];
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  const result = typeof left === 'number' && typeof right === 'number'
    ? left - right
    : String(left).localeCompare(String(right));
  return direction === 'asc' ? result : -result;
}

const formatNumber = (value) => (value == null ? '—' : value.toLocaleString('en-IN'));
const formatDate = (value) => (value ? new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—');
const formatDateTime = (value) => (value ? `${new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })} ${new Date(value).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : '—');

function windowRange(anchorEnd, days) {
  if (!anchorEnd) return {};
  const start = new Date(`${anchorEnd}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() - days);
  return { start: start.toISOString().slice(0, 10), end: anchorEnd };
}

// Per-machine detail: the weekly series and raw downtime events from
// GET /equipment/{id}/metrics, in the same slide-over the Field Intake
// equipment history already uses.
function MachineDetailDrawer({ machine, range, onClose }) {
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const closeRef = useRef(null);

  // Dialog focus contract: move focus into the drawer on open so a keyboard
  // user isn't stranded behind it, and hand focus back to whatever opened it
  // on close (the machine's name button) rather than dropping to <body>.
  useEffect(() => {
    const previouslyFocused = document.activeElement;
    closeRef.current?.focus();
    return () => {
      if (previouslyFocused instanceof HTMLElement && document.contains(previouslyFocused)) previouslyFocused.focus();
    };
  }, []);

  useEffect(() => {
    let active = true;
    setState({ loading: true, error: null, data: null });
    api.getEquipmentMetricsById(machine.equipment_id, range)
      .then((data) => active && setState({ loading: false, error: null, data }))
      .catch((error) => active && setState({ loading: false, error, data: null }));
    return () => { active = false; };
  }, [machine.equipment_id, range.start, range.end]);

  useEffect(() => {
    const onKeyDown = (event) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const detail = state.data;
  const weekly = (detail?.weekly || []).map((week) => ({ ...week, label: week.week_start.slice(5) }));

  return (
    <div className="eq-history-overlay" onClick={onClose}>
      <div
        className="card eq-history-panel eq-metrics-panel"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${machine.name} performance detail`}
        data-testid="panel-equipment-metrics-detail"
      >
        <div className="eq-history-head">
          <div>
            <div className="card-title">{machine.name}</div>
            <div className="card-kicker">{machine.equipment_type} · downtime detail</div>
          </div>
          <button ref={closeRef} type="button" className="btn ghost small" onClick={onClose} aria-label="Close detail panel" data-testid="button-close-equipment-detail">
            <X size={14} />
          </button>
        </div>

        {state.loading && <div className="eq-history-empty"><div className="skeleton" style={{ width: '100%', height: 90 }} /></div>}

        {state.error && (
          <div className="eq-history-empty" data-testid="text-equipment-detail-error">
            Could not load this machine&apos;s detail. {state.error.message || ''}
          </div>
        )}

        {detail && (
          <>
            <div className="mini-stat"><span>Physical availability</span><b>{detail.physical_availability_pct}%</b></div>
            <div className="mini-stat"><span>Overall availability</span><b>{detail.overall_availability_pct}%</b></div>
            <div className="mini-stat"><span>Failures</span><b>{detail.failures}</b></div>
            <div className="mini-stat"><span>MTBF</span><b>{detail.mtbf_hours == null ? '—' : `${formatNumber(detail.mtbf_hours)} h`}</b></div>
            <div className="mini-stat"><span>MTTR</span><b>{detail.mttr_hours == null ? '—' : `${formatNumber(detail.mttr_hours)} h`}</b></div>
            <div className="mini-stat"><span>Total downtime</span><b>{formatNumber(detail.downtime_hours)} h</b></div>
            <div className="mini-stat">
              <span>Maintenance</span>
              <span className={`pill ${(MAINTENANCE_PILLS[detail.maintenance_status] || MAINTENANCE_PILLS.unknown).className}`}>
                {(MAINTENANCE_PILLS[detail.maintenance_status] || MAINTENANCE_PILLS.unknown).label}
              </span>
            </div>
            <div className="mini-stat">
              <span>Next due</span>
              <b>{detail.next_maintenance_due ? formatDate(detail.next_maintenance_due) : '—'}</b>
            </div>

            <div className="card-title" style={{ marginTop: 18, marginBottom: 8 }}>Weekly downtime</div>
            {weekly.length === 0 ? (
              <div className="eq-history-empty">No weekly data in this window.</div>
            ) : (
              <div style={{ height: 150 }} data-testid="chart-equipment-weekly">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={weekly}>
                    <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 9, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={28} />
                    <Tooltip
                      contentStyle={{ background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', fontSize: 11 }}
                      formatter={(value, name) => [name === 'downtime_hours' ? `${value} h` : value, name === 'downtime_hours' ? 'Downtime' : 'Failures']}
                      labelFormatter={(label) => `Week of ${label}`}
                    />
                    <Bar dataKey="downtime_hours" fill="hsl(var(--primary))" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="card-title" style={{ marginTop: 18, marginBottom: 4 }}>
              Downtime events <span className="muted" style={{ fontWeight: 400 }}>({detail.events.length})</span>
            </div>
            {detail.events.length === 0 ? (
              <div className="eq-history-empty">No downtime recorded in this window.</div>
            ) : (
              [...detail.events].reverse().map((event, index) => (
                <div className="eq-history-item" key={`${event.start}-${index}`}>
                  <div>
                    <span className={`pill ${event.category === 'failure' ? 'critical' : event.category === 'planned_maintenance' ? 'good' : 'neutral'}`}>
                      {event.category.replaceAll('_', ' ')}
                    </span>
                    <span className="pill neutral" style={{ marginLeft: 6 }}>{formatNumber(event.hours)} h</span>
                  </div>
                  {event.reason && <div className="muted" style={{ marginTop: 6 }}>{event.reason}</div>}
                  <div className="muted mono" style={{ marginTop: 6, fontSize: 10 }}>
                    {formatDateTime(event.start)} → {event.end ? formatDateTime(event.end) : 'ongoing'} · {event.source}
                  </div>
                </div>
              ))
            )}
          </>
        )}
      </div>
    </div>
  );
}

function FleetStat({ label, value, foot }) {
  return (
    <div className="card stat-card" data-testid={`eqmetrics-stat-${label.toLowerCase().replaceAll(' ', '-')}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-foot"><span>{foot}</span></div>
    </div>
  );
}

export default function EquipmentPerformancePanel({ siteId }) {
  const [windowDays, setWindowDays] = useState(90);
  // The window is anchored to the data's own end date (window.end from the
  // first response), not to today -- the dataset is historical, so anchoring
  // to today would slide the window off the data entirely.
  const [anchorEnd, setAnchorEnd] = useState(null);
  const [sort, setSort] = useState({ key: 'physical_availability_pct', direction: 'asc' });
  const [state, setState] = useState({ loading: true, error: null, data: null });
  const [reloadToken, setReloadToken] = useState(0);
  const [selected, setSelected] = useState(null);

  // Shared by the table fetch and the detail drawer, so both always describe
  // the same window.
  const range = useMemo(
    () => (windowDays === 90 && !anchorEnd ? {} : windowRange(anchorEnd, windowDays)),
    [anchorEnd, windowDays],
  );

  useEffect(() => {
    let active = true;
    setState((current) => ({ ...current, loading: true, error: null }));
    api.getEquipmentMetrics(siteId, range)
      .then((data) => {
        if (!active) return;
        if (!anchorEnd && data?.window?.end) setAnchorEnd(data.window.end);
        setState({ loading: false, error: null, data });
      })
      .catch((error) => active && setState({ loading: false, error, data: null }));
    return () => { active = false; };
  }, [siteId, range, reloadToken]);

  // Don't leave a drawer open against a machine that isn't in the new site.
  useEffect(() => { setSelected(null); }, [siteId]);

  const rows = useMemo(() => {
    const list = state.data?.equipment ? [...state.data.equipment] : [];
    return list.sort((a, b) => compareRows(a, b, sort.key, sort.direction));
  }, [state.data, sort]);

  const toggleSort = (key) => {
    setSort((current) => (current.key === key
      ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
      : { key, direction: 'asc' }));
  };

  // Labelled and rendered as a `segmented` control rather than loose `btn small`
  // pills, so it reads as a different control from the satellite panel's
  // identical-looking 30/90/180d toggle that sits above every SitePage tab.
  const windowToggle = (
    <div className="filter-row">
      <span className="muted" style={{ fontSize: 10 }}>Window</span>
      <div className="segmented" role="group" aria-label="Analysis window">
        {WINDOW_OPTIONS.map((days) => (
          <button
            key={days}
            type="button"
            className={windowDays === days ? 'active' : ''}
            aria-pressed={windowDays === days}
            onClick={() => setWindowDays(days)}
            data-testid={`button-eqmetrics-window-${days}`}
          >
            {days}d
          </button>
        ))}
      </div>
    </div>
  );

  if (state.loading) {
    return (
      <div className="card section-card" aria-busy="true" aria-label="Loading equipment performance">
        <div className="skeleton" style={{ width: '32%', marginBottom: 16 }} />
        {Array.from({ length: 6 }).map((_, index) => <div className="skeleton" key={index} style={{ width: `${82 - index * 9}%`, marginBottom: 11 }} />)}
      </div>
    );
  }

  if (state.error) {
    return (
      <div className="error-box">
        <strong>Could not load equipment performance</strong>
        <p className="subhead">{state.error.message || 'The metrics service did not return a usable response.'}</p>
        <button className="btn small" onClick={() => setReloadToken((token) => token + 1)} data-testid="button-retry-equipment-metrics">
          <RefreshCw size={13} /> Retry
        </button>
      </div>
    );
  }

  const { fleet, window: windowInfo, data_note: dataNote } = state.data;

  if (!fleet.equipment_count) {
    return (
      <div className="section-stack">
        <section className="card section-card">
          <div className="card-head">
            <div>
              <div className="card-title">Equipment performance</div>
              <div className="card-kicker">availability, reliability and maintenance due</div>
            </div>
            {windowToggle}
          </div>
          <div className="empty">
            <Truck size={25} />
            <strong>No equipment at this site</strong>
            <div className="subhead">Nothing is registered against this site yet, so there is no downtime history to measure.</div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="section-stack">
      <div className="card-head" style={{ marginBottom: 4 }}>
        <div>
          <div className="card-title">Equipment performance</div>
          <div className="card-kicker">availability, reliability and maintenance due · {fleet.equipment_count} machines</div>
        </div>
        {windowToggle}
      </div>

      <div className="stat-grid">
        <FleetStat label="Physical availability" value={`${fleet.physical_availability_pct}%`} foot="excludes weather and crew gaps" />
        <FleetStat label="Overall availability" value={`${fleet.overall_availability_pct}%`} foot="all downtime included" />
        <FleetStat label="MTBF" value={fleet.mtbf_hours == null ? '—' : `${formatNumber(fleet.mtbf_hours)} h`} foot={`${fleet.failures} failures in window`} />
        <FleetStat label="MTTR" value={fleet.mttr_hours == null ? '—' : `${formatNumber(fleet.mttr_hours)} h`} foot="mean time to repair" />
      </div>

      <div className="stat-grid" style={{ gridTemplateColumns: 'repeat(3, minmax(0,1fr))' }}>
        <FleetStat label="Failures" value={formatNumber(fleet.failures)} foot="failure-category events" />
        <FleetStat label="Maintenance overdue" value={formatNumber(fleet.maintenance_overdue_count)} foot="past the assumed interval" />
        <FleetStat label="Due soon" value={formatNumber(fleet.maintenance_due_soon_count)} foot={`within ${state.data.assumptions.due_soon_days} days`} />
      </div>

      <section className="card section-card">
        <div className="card-head">
          <div>
            <div className="card-title">Per-machine performance</div>
            <div className="card-kicker">sortable · nulls last</div>
          </div>
          {fleet.maintenance_overdue_count > 0 && (
            <span className="pill critical"><AlertTriangle size={11} /> {fleet.maintenance_overdue_count} overdue</span>
          )}
        </div>

        <div className="table-wrap">
          <table data-testid="table-equipment-metrics">
            <thead>
              <tr>
                {COLUMNS.map((column) => {
                  const sortable = column.sortable !== false;
                  const active = sort.key === column.key;
                  if (!sortable) {
                    return <th key={column.key} style={{ textAlign: column.align }}>{column.label}</th>;
                  }
                  return (
                    <th key={column.key} style={{ textAlign: column.align }} aria-sort={active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'}>
                      {/* A real button, so the header is reachable and operable by keyboard, not click-only. */}
                      <button
                        type="button"
                        className="th-sort"
                        onClick={() => toggleSort(column.key)}
                        data-testid={`sort-${column.key}`}
                        aria-label={`Sort by ${column.label}`}
                      >
                        {column.label}
                        {active && (sort.direction === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />)}
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const pill = MAINTENANCE_PILLS[row.maintenance_status] || MAINTENANCE_PILLS.unknown;
                return (
                  <tr key={row.equipment_id} data-testid={`row-equipment-${row.equipment_id}`}>
                    <td>
                      {/* Button, not a row click handler: keyboard-reachable and it
                          doesn't swallow text selection in the rest of the row. */}
                      <button type="button" className="th-sort" style={{ fontWeight: 700 }} onClick={() => setSelected(row)} data-testid={`button-equipment-detail-${row.equipment_id}`}>
                        {row.name}
                      </button>
                    </td>
                    <td className="muted">{row.equipment_type}</td>
                    <td><span className={`pill ${row.status === 'up' ? 'good' : 'critical'}`}>{row.status}</span></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span className="mono" style={{ minWidth: 42 }}>{row.physical_availability_pct}%</span>
                        <div className="progress" style={{ width: 70 }} role="presentation">
                          <span style={{ width: `${Math.max(0, Math.min(100, row.physical_availability_pct))}%` }} />
                        </div>
                      </div>
                    </td>
                    <td className="mono" style={{ textAlign: 'right' }}>{formatNumber(row.mtbf_hours)}</td>
                    <td className="mono" style={{ textAlign: 'right' }}>{formatNumber(row.mttr_hours)}</td>
                    <td className="mono" style={{ textAlign: 'right' }}>{row.failures}</td>
                    <td className="mono" style={{ textAlign: 'right' }}>{formatNumber(row.downtime_hours)}</td>
                    {/* Always "—". The backend has no hour-meter data, so a number here would be invented. */}
                    <td style={{ textAlign: 'right' }}>
                      <abbr title={row.utilisation_note} style={{ textDecoration: 'none', cursor: 'help' }} data-testid={`utilisation-${row.equipment_id}`}>—</abbr>
                    </td>
                    <td className="muted">{row.top_failure_reason || '—'}</td>
                    <td>
                      <span className={`pill ${pill.className}`} title={row.next_maintenance_due ? `Next due ${formatDate(row.next_maintenance_due)} · last ${formatDate(row.last_maintenance_at)}` : 'No maintenance on record'}>
                        {pill.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="footer-note" data-testid="text-equipment-metrics-caption">
          <ClipboardList size={12} style={{ verticalAlign: 'middle', marginRight: 4 }} />
          Window {windowInfo.start} → {windowInfo.end} ({formatNumber(windowInfo.hours)} h) · data through {formatDateTime(windowInfo.data_through)}. {dataNote}
        </div>
      </section>

      {selected && <MachineDetailDrawer machine={selected} range={range} onClose={() => setSelected(null)} />}
    </div>
  );
}
