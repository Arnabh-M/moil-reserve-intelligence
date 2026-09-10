import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, BarChart3, Check, Loader2, Zap } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { api } from '../../api/client';
import { useSites } from '../../hooks/useSites';
import { MAX_TONNES } from '../../constants/validationLimits';

const STATUS_OPTIONS = ['planned', 'completed', 'delayed', 'cancelled'];

const DELAY_REASONS = [
  { value: 'permit_pending', label: 'Permit pending' },
  { value: 'weather_hold', label: 'Weather hold' },
  { value: 'safety_hold', label: 'Safety hold' },
  { value: 'equipment_unavailable', label: 'Equipment unavailable' },
  { value: 'explosive_supply', label: 'Explosive supply' },
];

// Mirrors the Equipment tab's up=good / down=critical pill vocabulary.
const STATUS_PILL = { planned: 'warn', completed: 'good', delayed: 'critical', cancelled: 'critical' };

const reasonLabel = (value) => DELAY_REASONS.find((r) => r.value === value)?.label || 'Unattributed';
const dateLabel = (value) => value ? new Date(value).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—';

const initialForm = { site_id: 1, reserve_zone_id: '', planned_date: '2026-09-10', expected_yield_tonnes: '', notes: '' };
const initialUpdate = { status: 'delayed', delay_reason: '', actual_date: '', actual_yield_tonnes: '' };

function LogAndTimeline({ showToast }) {
  const sites = useSites();
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState('idle');
  const [errors, setErrors] = useState({});
  const [events, setEvents] = useState([]);
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [update, setUpdate] = useState(initialUpdate);
  const [updateErrors, setUpdateErrors] = useState({});

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const refetch = async (siteId) => {
    setLoading(true);
    try { setEvents(await api.listBlastEvents({ site_id: siteId })); }
    catch { setEvents([]); }
    finally { setLoading(false); }
  };

  useEffect(() => { refetch(form.site_id); }, [form.site_id]);

  useEffect(() => {
    api.getReserveZones(form.site_id)
      .then((collection) => setZones(collection.features || []))
      .catch(() => setZones([]));
  }, [form.site_id]);

  const expected = form.expected_yield_tonnes === '' ? null : Number(form.expected_yield_tonnes);

  const validate = () => {
    const next = {};
    if (!form.planned_date) next.planned_date = 'Select a planned blast date.';
    if (form.expected_yield_tonnes === '' || Number.isNaN(expected)) next.expected_yield_tonnes = 'Enter the expected yield in tonnes.';
    else if (expected <= 0) next.expected_yield_tonnes = 'Expected yield must be greater than zero.';
    else if (expected > MAX_TONNES) next.expected_yield_tonnes = `Expected yield cannot exceed ${MAX_TONNES.toLocaleString()} tonnes.`;
    return next;
  };

  const handleSubmit = async () => {
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) { setStatus('error'); return; }
    setStatus('saving');
    try {
      await api.createBlastEvent({ site_id: form.site_id, reserve_zone_id: form.reserve_zone_id || null, planned_date: form.planned_date, expected_yield_tonnes: expected, notes: form.notes });
      setStatus('saved');
      showToast('Blast plan logged');
      setForm((f) => ({ ...initialForm, site_id: f.site_id, planned_date: f.planned_date }));
      await refetch(form.site_id);
      setTimeout(() => setStatus((s) => (s === 'saved' ? 'idle' : s)), 2200);
    } catch (submitError) {
      setStatus('error');
      setErrors({ submit: submitError.detail || 'Could not log the blast. Please try again.' });
    }
  };

  const openUpdate = (event) => {
    setEditingId(event.id);
    setUpdateErrors({});
    setUpdate({ status: event.status, delay_reason: event.delay_reason || '', actual_date: event.actual_date || '', actual_yield_tonnes: event.actual_yield_tonnes ?? '' });
  };

  const validateUpdate = () => {
    const next = {};
    if (['delayed', 'cancelled'].includes(update.status) && !update.delay_reason) next.delay_reason = 'Select why this blast slipped.';
    if (update.status === 'completed') {
      if (!update.actual_date) next.actual_date = 'Enter the date the blast fired.';
      if (update.actual_yield_tonnes === '' || Number.isNaN(Number(update.actual_yield_tonnes))) next.actual_yield_tonnes = 'Enter the tonnes actually recovered.';
      else if (Number(update.actual_yield_tonnes) < 0) next.actual_yield_tonnes = 'Actual yield cannot be negative.';
      else if (Number(update.actual_yield_tonnes) > MAX_TONNES) next.actual_yield_tonnes = `Actual yield cannot exceed ${MAX_TONNES.toLocaleString()} tonnes.`;
    }
    return next;
  };

  const submitUpdate = async () => {
    const nextErrors = validateUpdate();
    setUpdateErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    try {
      await api.updateBlastEvent(editingId, update);
      showToast('Blast outcome updated');
      setEditingId(null);
      await refetch(form.site_id);
    } catch (updateError) {
      setUpdateErrors({ submit: updateError.detail || 'Could not update this blast.' });
    }
  };

  const statusPill = status === 'saving' ? { label: 'Saving…', pill: 'warn' }
    : status === 'saved' ? { label: 'Saved', pill: 'good' }
    : status === 'error' ? { label: 'Needs attention', pill: 'critical' }
    : { label: 'Ready to submit', pill: 'good' };

  return (
    <div className="section-stack">
      <section className="card section-card">
        <div className="card-head">
          <div><div className="card-title">Log a planned blast</div><div className="card-kicker">POST /blast-events · outcome is recorded later</div></div>
          <span className={`pill ${statusPill.pill}`} data-testid="blast-status-pill">
            {status === 'saving' && <Loader2 size={11} className="spin" />}
            {status === 'saved' && <Check size={11} />}
            {status === 'error' && <AlertTriangle size={11} />}
            {statusPill.label}
          </span>
        </div>

        <div className="form-grid">
          <div className="field">
            <label>Site</label>
            <select className="select" value={form.site_id} onChange={(e) => setField('site_id', Number(e.target.value))} data-testid="select-blast-site">
              {sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Reserve zone (optional)</label>
            <select className="select" value={form.reserve_zone_id} onChange={(e) => setField('reserve_zone_id', e.target.value)} data-testid="select-blast-zone">
              <option value="">No specific zone</option>
              {zones.map((zone) => <option key={zone.properties.id} value={zone.properties.id}>{zone.properties.zone_name || `Zone ${zone.properties.id}`}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Planned date</label>
            <input className="input" type="date" value={form.planned_date} onChange={(e) => setField('planned_date', e.target.value)} data-testid="input-blast-planned-date" />
            {errors.planned_date && <span className="field-error">{errors.planned_date}</span>}
          </div>
          <div className="field">
            <label>Expected yield (tonnes)</label>
            <input className="input" type="number" min="0" max={MAX_TONNES} value={form.expected_yield_tonnes} onChange={(e) => setField('expected_yield_tonnes', e.target.value)} placeholder="e.g. 1800" data-testid="input-blast-expected-yield" />
            {errors.expected_yield_tonnes && <span className="field-error">{errors.expected_yield_tonnes}</span>}
          </div>
          <div className="field full">
            <label>Notes</label>
            <textarea className="input" value={form.notes} onChange={(e) => setField('notes', e.target.value)} placeholder="Bench, face, pattern…" data-testid="textarea-blast-notes" />
          </div>
        </div>

        {errors.submit && <div className="alert-strip danger" style={{ marginTop: 14 }}><AlertTriangle size={15} color="hsl(var(--destructive))" /><span>{errors.submit}</span></div>}

        <button className="btn primary" style={{ marginTop: 18 }} onClick={handleSubmit} disabled={status === 'saving'} data-testid="button-submit-blast">
          {status === 'saving' ? <Loader2 size={14} className="spin" /> : <Check size={14} />}
          {status === 'saving' ? 'Saving…' : 'Log blast plan'}
        </button>
      </section>

      <section className="card section-card">
        <div className="card-head">
          <div><div className="card-title">Blast timeline</div><div className="card-kicker">planned vs actual · {sites.find((s) => s.id === form.site_id)?.name}</div></div>
          <Zap size={16} />
        </div>

        {loading ? <div className="muted" style={{ fontSize: 11 }}>Loading blasts…</div>
          : events.length === 0 ? <div className="empty"><Zap size={25} /><strong>No blasts logged for this site</strong><div className="subhead">Log a planned blast above to start the timeline.</div></div>
          : <div className="timeline">
              {events.map((event) => (
                <div className="timeline-item" key={event.id} data-testid={`row-blast-${event.id}`}>
                  <div className="timeline-date">
                    planned {dateLabel(event.planned_date)}
                    {event.actual_date && ` · fired ${dateLabel(event.actual_date)}`}
                    {' · '}{Number(event.expected_yield_tonnes).toLocaleString()} t expected
                    {event.actual_yield_tonnes !== null && ` · ${Number(event.actual_yield_tonnes).toLocaleString()} t recovered`}
                  </div>
                  <div className="timeline-text">{event.notes || 'No notes recorded.'}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 7 }}>
                    <span className={`pill ${STATUS_PILL[event.status]}`}>{event.status}</span>
                    {event.delay_reason && <span className="muted" style={{ fontSize: 10 }}>{reasonLabel(event.delay_reason)}</span>}
                    <button className="btn small ghost" style={{ marginLeft: 'auto' }} onClick={() => openUpdate(event)} data-testid={`button-update-blast-${event.id}`}>Update</button>
                  </div>

                  {editingId === event.id && (
                    <div className="card section-card" style={{ marginTop: 10, padding: 12 }} data-testid={`form-update-blast-${event.id}`}>
                      <div className="form-grid">
                        <div className="field">
                          <label>Status</label>
                          <select className="select" value={update.status} onChange={(e) => setUpdate((u) => ({ ...u, status: e.target.value }))} data-testid="select-blast-update-status">
                            {STATUS_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                          </select>
                        </div>

                        {['delayed', 'cancelled'].includes(update.status) && (
                          <div className="field">
                            <label>Delay reason</label>
                            <select className="select" value={update.delay_reason} onChange={(e) => setUpdate((u) => ({ ...u, delay_reason: e.target.value }))} data-testid="select-blast-delay-reason">
                              <option value="">Select a reason</option>
                              {DELAY_REASONS.map((reason) => <option key={reason.value} value={reason.value}>{reason.label}</option>)}
                            </select>
                            {updateErrors.delay_reason && <span className="field-error">{updateErrors.delay_reason}</span>}
                          </div>
                        )}

                        {update.status === 'completed' && (
                          <>
                            <div className="field">
                              <label>Actual date</label>
                              <input className="input" type="date" value={update.actual_date} onChange={(e) => setUpdate((u) => ({ ...u, actual_date: e.target.value }))} data-testid="input-blast-actual-date" />
                              {updateErrors.actual_date && <span className="field-error">{updateErrors.actual_date}</span>}
                            </div>
                            <div className="field">
                              <label>Actual yield (tonnes)</label>
                              <input className="input" type="number" min="0" max={MAX_TONNES} value={update.actual_yield_tonnes} onChange={(e) => setUpdate((u) => ({ ...u, actual_yield_tonnes: e.target.value }))} placeholder="e.g. 1725" data-testid="input-blast-actual-yield" />
                              {updateErrors.actual_yield_tonnes && <span className="field-error">{updateErrors.actual_yield_tonnes}</span>}
                            </div>
                          </>
                        )}
                      </div>

                      {updateErrors.submit && <div className="alert-strip danger" style={{ marginTop: 12 }}><AlertTriangle size={15} color="hsl(var(--destructive))" /><span>{updateErrors.submit}</span></div>}

                      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                        <button className="btn small primary" onClick={submitUpdate} data-testid="button-save-blast-update"><Check size={12} /> Save outcome</button>
                        <button className="btn small ghost" onClick={() => setEditingId(null)} data-testid="button-cancel-blast-update">Cancel</button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>}
      </section>
    </div>
  );
}

function DelayAnalysis() {
  const sites = useSites();
  const [siteId, setSiteId] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.getBlastEventSummary({ site_id: siteId === '' ? undefined : Number(siteId), from: from || undefined, to: to || undefined })
      .then((result) => { if (!cancelled) setRows(result); })
      .catch(() => { if (!cancelled) setRows([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [siteId, from, to]);

  const chartData = useMemo(() => rows.map((row) => ({ reason: reasonLabel(row.delay_reason), tonnes_lost: Number(row.tonnes_lost) })), [rows]);
  const totalLost = useMemo(() => rows.reduce((sum, row) => sum + Number(row.tonnes_lost), 0), [rows]);

  return (
    <div className="section-stack">
      <section className="card section-card">
        <div className="card-head">
          <div><div className="card-title">Delay analysis</div><div className="card-kicker">GET /blast-events/summary · delayed and cancelled blasts only</div></div>
          <BarChart3 size={16} />
        </div>

        <div className="filter-row">
          <select className="select" value={siteId} onChange={(e) => setSiteId(e.target.value)} data-testid="select-blast-summary-site">
            <option value="">All sites</option>
            {sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}
          </select>
          <input className="input" type="date" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="From date" data-testid="input-blast-summary-from" />
          <input className="input" type="date" value={to} onChange={(e) => setTo(e.target.value)} aria-label="To date" data-testid="input-blast-summary-to" />
          <span className="muted" style={{ fontSize: 10 }}>{totalLost.toLocaleString()} t lost across {rows.length} reason{rows.length === 1 ? '' : 's'}</span>
        </div>

        {loading ? <div className="muted" style={{ fontSize: 11, marginTop: 14 }}>Loading summary…</div>
          : rows.length === 0 ? <div className="empty"><BarChart3 size={25} /><strong>No delayed or cancelled blasts in range</strong><div className="subhead">Widen the date range, or clear the site filter.</div></div>
          : <>
              <div style={{ height: 260, marginTop: 16 }} data-testid="chart-blast-delay">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="reason" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                    <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                    <Tooltip formatter={(value) => [`${Number(value).toLocaleString()} t`, 'Tonnes lost']} />
                    <Bar dataKey="tonnes_lost" fill="hsl(var(--destructive))" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <table className="table" style={{ marginTop: 16, width: '100%' }} data-testid="table-blast-delay">
                <thead><tr><th style={{ textAlign: 'left' }}>Delay reason</th><th style={{ textAlign: 'right' }}>Blasts</th><th style={{ textAlign: 'right' }}>Expected (t)</th><th style={{ textAlign: 'right' }}>Recovered (t)</th><th style={{ textAlign: 'right' }}>Tonnes lost</th></tr></thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.delay_reason || 'unattributed'}>
                      <td>{reasonLabel(row.delay_reason)}</td>
                      <td style={{ textAlign: 'right' }}>{row.event_count}</td>
                      <td style={{ textAlign: 'right' }}>{Number(row.expected_yield_tonnes).toLocaleString()}</td>
                      <td style={{ textAlign: 'right' }}>{Number(row.actual_yield_tonnes).toLocaleString()}</td>
                      <td style={{ textAlign: 'right' }} className="risk-high">{Number(row.tonnes_lost).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>}
      </section>
    </div>
  );
}

export default function BlastLogTab({ showToast }) {
  const [view, setView] = useState('log');
  return (
    <div className="section-stack">
      <div className="segmented" role="group" aria-label="Blasting view" style={{ marginBottom: 12, width: 'fit-content' }}>
        <button type="button" className={view === 'log' ? 'active' : ''} onClick={() => setView('log')} data-testid="toggle-blast-log">Log &amp; timeline</button>
        <button type="button" className={view === 'analysis' ? 'active' : ''} onClick={() => setView('analysis')} data-testid="toggle-blast-analysis">Delay analysis</button>
      </div>
      {view === 'log' ? <LogAndTimeline showToast={showToast} /> : <DelayAnalysis />}
    </div>
  );
}
