import { useEffect, useState } from 'react';
import { AlertTriangle, Check, Loader2 } from 'lucide-react';
import { api } from '../../api/client';

const SITE_OPTIONS = [
  { id: 1, name: 'Balaghat' },
  { id: 2, name: 'Nagpur' },
  { id: 3, name: 'Bhandara' },
];

const SHIFT_OPTIONS = [
  { value: 'general', label: 'General' },
  { value: 'day', label: 'Day' },
  { value: 'night', label: 'Night' },
];

// Fallback only — the real vocabulary is fetched from
// GET /production/shortfall-reasons (backend-owned, see schemas/production.py).
const FALLBACK_SHORTFALL_REASONS = [
  { value: 'equipment_failure', label: 'Equipment failure' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'weather', label: 'Weather' },
  { value: 'material_availability', label: 'Material availability' },
  { value: 'labour_shortage', label: 'Labour shortage' },
  { value: 'geological_conditions', label: 'Geological conditions' },
  { value: 'safety_stoppage', label: 'Safety stoppage' },
  { value: 'other', label: 'Other' },
];

// Fallback only — the real thresholds are fetched from
// GET /production/thresholds so client and server never disagree.
const FALLBACK_THRESHOLDS = { on_target_min_pct: -3, slightly_below_min_pct: -12 };

const STATUS_COPY = {
  on_target: { label: 'On target', pill: 'good' },
  slightly_below: { label: 'Slightly below target', pill: 'warn' },
  significantly_below: { label: 'Significantly below target', pill: 'critical' },
};

const initialForm = {
  site_id: 1,
  date: '2026-09-05',
  shift: 'general',
  actual_output: '',
  target_output: '',
  operating_hours: '',
  downtime_hours: '',
  material_processed: '',
  quality_grade: '',
  shortfall_reasons: [],
  shortfall_other_note: '',
  note: '',
};

export default function ProductionTab({ showToast }) {
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState('idle');
  const [errors, setErrors] = useState({});
  const [reasons, setReasons] = useState(FALLBACK_SHORTFALL_REASONS);
  const [thresholds, setThresholds] = useState(FALLBACK_THRESHOLDS);
  const [existingRecord, setExistingRecord] = useState(null);
  const [checkingExisting, setCheckingExisting] = useState(false);
  const [savedRecord, setSavedRecord] = useState(null);

  useEffect(() => { api.getShortfallReasons().then(setReasons).catch(() => setReasons(FALLBACK_SHORTFALL_REASONS)); }, []);
  useEffect(() => { api.getProductionThresholds().then(setThresholds).catch(() => setThresholds(FALLBACK_THRESHOLDS)); }, []);

  // Look up whether a record already exists for the selected site/date/shift
  // so the form can switch into "edit" mode (PATCH) instead of colliding
  // with the 409 on submit. Debounced since it fires on every keystroke of
  // the date field.
  useEffect(() => {
    let cancelled = false;
    setCheckingExisting(true);
    const handle = setTimeout(async () => {
      try {
        const records = await api.getProduction(form.site_id, 365);
        const match = records.find((r) => r.date === form.date && (r.shift || 'general') === form.shift);
        if (!cancelled) setExistingRecord(match || null);
      } catch {
        if (!cancelled) setExistingRecord(null);
      } finally {
        if (!cancelled) setCheckingExisting(false);
      }
    }, 300);
    return () => { cancelled = true; clearTimeout(handle); };
  }, [form.site_id, form.date, form.shift]);

  // Load the existing record's values into the form so editing doesn't
  // start from a blank slate.
  useEffect(() => {
    if (!existingRecord) return;
    setForm((f) => ({
      ...f,
      actual_output: String(existingRecord.actual_output ?? ''),
      target_output: String(existingRecord.target_output ?? ''),
      operating_hours: existingRecord.operating_hours === null || existingRecord.operating_hours === undefined ? '' : String(existingRecord.operating_hours),
      downtime_hours: existingRecord.downtime_hours === null || existingRecord.downtime_hours === undefined ? '' : String(existingRecord.downtime_hours),
      material_processed: existingRecord.material_processed === null || existingRecord.material_processed === undefined ? '' : String(existingRecord.material_processed),
      quality_grade: existingRecord.quality_grade === null || existingRecord.quality_grade === undefined ? '' : String(existingRecord.quality_grade),
      shortfall_reasons: existingRecord.shortfall_reasons || [],
      shortfall_other_note: existingRecord.shortfall_other_note || '',
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingRecord?.id]);

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const toggleReason = (value) => setForm((f) => ({
    ...f,
    shortfall_reasons: f.shortfall_reasons.includes(value) ? f.shortfall_reasons.filter((r) => r !== value) : [...f.shortfall_reasons, value],
  }));

  const classifyVariance = (variancePct) => {
    if (variancePct === null) return null;
    if (variancePct >= thresholds.on_target_min_pct) return 'on_target';
    if (variancePct >= thresholds.slightly_below_min_pct) return 'slightly_below';
    return 'significantly_below';
  };

  const actual = form.actual_output === '' ? null : Number(form.actual_output);
  const target = form.target_output === '' ? null : Number(form.target_output);
  const hasBoth = actual !== null && target !== null && !Number.isNaN(actual) && !Number.isNaN(target) && target > 0;
  const diff = hasBoth ? actual - target : null;
  const pctAchieved = hasBoth ? (actual / target) * 100 : null;
  const variancePct = hasBoth ? (diff / target) * 100 : null;
  const varianceState = classifyVariance(variancePct);
  const isBelowTarget = diff !== null && diff < 0;
  const operatingHoursNum = form.operating_hours === '' ? null : Number(form.operating_hours);
  const downtimeHoursNum = form.downtime_hours === '' ? null : Number(form.downtime_hours);

  const isEditing = Boolean(existingRecord);
  // The server's canonical classification, shown once a save has completed
  // (variance_class is computed server-side, not trusted from the client).
  const serverVarianceState = savedRecord?.variance_class;

  const validate = () => {
    const next = {};
    if (form.actual_output === '' || Number.isNaN(actual)) next.actual_output = 'Enter the actual tonnes produced.';
    else if (actual < 0) next.actual_output = 'Actual output cannot be negative.';
    if (form.target_output === '' || Number.isNaN(target)) next.target_output = 'Enter a target output.';
    else if (target < 0) next.target_output = 'Target output cannot be negative.';
    else if (target === 0) next.target_output = 'Target output must be greater than zero.';
    if (!form.date) next.date = 'Select a shift date.';
    if (varianceState === 'significantly_below' && form.shortfall_reasons.length === 0) next.shortfall_reasons = 'Select at least one reason for the shortfall.';
    if (form.shortfall_reasons.includes('other') && !form.shortfall_other_note.trim()) next.shortfall_other_note = 'Describe the other reason.';
    if (form.operating_hours !== '' && (operatingHoursNum < 0 || operatingHoursNum > 24)) next.operating_hours = 'Enter hours between 0 and 24.';
    if (form.downtime_hours !== '' && downtimeHoursNum < 0) next.downtime_hours = 'Downtime cannot be negative.';
    if (operatingHoursNum !== null && downtimeHoursNum !== null && operatingHoursNum + downtimeHoursNum > 24) next.downtime_hours = 'Operating + downtime hours cannot exceed 24.';
    if (form.quality_grade !== '' && (Number(form.quality_grade) < 0 || Number(form.quality_grade) > 100)) next.quality_grade = 'Enter a grade between 0 and 100%.';
    return next;
  };

  const buildPayload = () => ({
    site_id: form.site_id,
    date: form.date,
    shift: form.shift,
    actual_output: actual,
    target_output: target,
    operating_hours: operatingHoursNum,
    downtime_hours: downtimeHoursNum,
    material_processed: form.material_processed === '' ? null : Number(form.material_processed),
    quality_grade: form.quality_grade === '' ? null : Number(form.quality_grade),
    shortfall_reasons: form.shortfall_reasons,
    shortfall_other_note: form.shortfall_other_note || null,
  });

  const handleSubmit = async () => {
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) { setStatus('error'); return; }
    setStatus('saving');
    try {
      const payload = buildPayload();
      const saved = isEditing ? await api.updateProduction(existingRecord.id, payload) : await api.createProduction(payload);
      setStatus('saved');
      setSavedRecord(saved);
      showToast(isEditing ? 'Production record updated' : 'Daily production submitted');
      if (!isEditing) {
        setForm((f) => ({ ...initialForm, site_id: f.site_id, date: f.date, shift: f.shift }));
      }
      setTimeout(() => setStatus((s) => (s === 'saved' ? 'idle' : s)), 2200);
    } catch (submitError) {
      setStatus('error');
      if (submitError.status === 409) {
        setErrors({ submit: submitError.detail || 'A production record has already been submitted for this site, date, and shift.' });
      } else if (submitError.status === 403) {
        setErrors({ submit: submitError.detail || 'This record is outside the edit window and can no longer be changed here.' });
      } else {
        setErrors({ submit: submitError.detail || 'Could not submit production. Please try again.' });
      }
    }
  };

  const statusPill = status === 'saving' ? { label: 'Saving…', pill: 'warn' }
    : status === 'saved' ? { label: 'Saved', pill: 'good' }
    : status === 'error' ? { label: 'Needs attention', pill: 'critical' }
    : isEditing ? { label: 'Editing existing record', pill: 'warn' }
    : { label: 'Ready to submit', pill: 'good' };

  return (
    <section className="card section-card">
      <div className="card-head">
        <div><div className="card-title">Daily production entry</div><div className="card-kicker">Log actual output against today's target</div></div>
        <span className={`pill ${statusPill.pill}`} data-testid="production-status-pill">
          {status === 'saving' && <Loader2 size={11} className="spin" />}
          {status === 'saved' && <Check size={11} />}
          {status === 'error' && <AlertTriangle size={11} />}
          {statusPill.label}
        </span>
      </div>

      {isEditing && !checkingExisting && (
        <div className="alert-strip" style={{ marginTop: 12 }} data-testid="production-edit-banner">
          <AlertTriangle size={15} />
          <span>
            A record already exists for this site, date, and shift — editing it instead of creating a new one.
            {existingRecord.updated_at ? ` Last updated ${new Date(existingRecord.updated_at).toLocaleString()} by ${existingRecord.updated_by || 'system'}.` : ` Created ${new Date(existingRecord.created_at).toLocaleString()} by ${existingRecord.created_by || 'system'}.`}
          </span>
        </div>
      )}

      {hasBoth && (
        <div className="prod-summary-grid" data-testid="production-summary">
          <div className="prod-summary-cell"><div className="metric-label">Actual</div><div className="metric-value">{actual.toLocaleString()} t</div></div>
          <div className="prod-summary-cell"><div className="metric-label">Target</div><div className="metric-value">{target.toLocaleString()} t</div></div>
          <div className="prod-summary-cell"><div className="metric-label">Achievement</div><div className="metric-value">{pctAchieved.toFixed(1)}%</div></div>
          <div className="prod-summary-cell"><div className="metric-label">Variance</div><div className={`metric-value ${diff < 0 ? 'risk-high' : 'trend-up'}`}>{diff > 0 ? '+' : ''}{diff.toLocaleString()} t</div></div>
        </div>
      )}

      <div className="form-grid">
        <div className="field">
          <label>Site</label>
          <select className="select" value={form.site_id} onChange={(e) => setField('site_id', Number(e.target.value))} data-testid="select-intake-site">
            {SITE_OPTIONS.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Shift date</label>
          <input className="input" type="date" value={form.date} onChange={(e) => setField('date', e.target.value)} data-testid="input-shift-date" />
          {errors.date && <span className="field-error">{errors.date}</span>}
        </div>
        <div className="field">
          <label>Shift</label>
          <select className="select" value={form.shift} onChange={(e) => setField('shift', e.target.value)} data-testid="select-shift">
            {SHIFT_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
        <div className="field">
          <label>Actual output (tonnes)</label>
          <input className="input" type="number" min="0" value={form.actual_output} onChange={(e) => setField('actual_output', e.target.value)} placeholder="e.g. 980" data-testid="input-actual-output" />
          {errors.actual_output && <span className="field-error">{errors.actual_output}</span>}
        </div>
        <div className="field">
          <label>Target output (tonnes)</label>
          <input className="input" type="number" min="0" value={form.target_output} onChange={(e) => setField('target_output', e.target.value)} placeholder="e.g. 1040" data-testid="input-target-output" />
          {errors.target_output && <span className="field-error">{errors.target_output}</span>}
        </div>
      </div>

      {hasBoth && (
        <div className="prod-progress" data-testid="production-progress">
          <div className="progress"><span style={{ width: `${Math.max(0, Math.min(100, pctAchieved))}%` }} /></div>
          <div className="prod-progress-caption">
            <span>{pctAchieved.toFixed(1)}% achieved</span>
            <span className={diff < 0 ? 'risk-high' : 'trend-up'}>{Math.abs(diff).toLocaleString()} t {diff < 0 ? 'below target' : diff > 0 ? 'above target' : 'on target'}</span>
          </div>
          <span className={`pill ${STATUS_COPY[varianceState].pill}`} style={{ marginTop: 8 }}>{STATUS_COPY[varianceState].label}</span>
          {serverVarianceState && serverVarianceState !== varianceState && (
            <div className="muted" style={{ fontSize: 10, marginTop: 6 }}>Server recorded this as <b>{STATUS_COPY[serverVarianceState]?.label || serverVarianceState}</b> on save.</div>
          )}
        </div>
      )}

      {isBelowTarget && (
        <div className="field full" style={{ marginTop: 16 }}>
          <label>Why was production below target?</label>
          <div className="chip-row">
            {reasons.map((reason) => (
              <button type="button" key={reason.value} className={`chip ${form.shortfall_reasons.includes(reason.value) ? 'selected' : ''}`} onClick={() => toggleReason(reason.value)} data-testid={`chip-reason-${reason.value.replaceAll('_', '-')}`}>
                {reason.label}
              </button>
            ))}
          </div>
          {errors.shortfall_reasons && <span className="field-error">{errors.shortfall_reasons}</span>}
          {form.shortfall_reasons.includes('other') && (
            <div style={{ marginTop: 10 }}>
              <input className="input" style={{ width: '100%' }} value={form.shortfall_other_note} onChange={(e) => setField('shortfall_other_note', e.target.value)} placeholder="Describe the reason" data-testid="input-variance-other" />
              {errors.shortfall_other_note && <span className="field-error">{errors.shortfall_other_note}</span>}
            </div>
          )}
        </div>
      )}

      <div className="form-grid" style={{ marginTop: 16 }}>
        <div className="field">
          <label>Operating hours</label>
          <input className="input" type="number" min="0" max="24" value={form.operating_hours} onChange={(e) => setField('operating_hours', e.target.value)} placeholder="e.g. 22" data-testid="input-operating-hours" />
          {errors.operating_hours && <span className="field-error">{errors.operating_hours}</span>}
        </div>
        <div className="field">
          <label>Downtime hours</label>
          <input className="input" type="number" min="0" value={form.downtime_hours} onChange={(e) => setField('downtime_hours', e.target.value)} placeholder="e.g. 2" data-testid="input-downtime-hours" />
          {errors.downtime_hours && <span className="field-error">{errors.downtime_hours}</span>}
        </div>
        <div className="field">
          <label>Material processed (t)</label>
          <input className="input" type="number" min="0" value={form.material_processed} onChange={(e) => setField('material_processed', e.target.value)} placeholder="e.g. 1150" data-testid="input-material-processed" />
        </div>
        <div className="field">
          <label>Quality / grade (%)</label>
          <input className="input" type="number" min="0" max="100" value={form.quality_grade} onChange={(e) => setField('quality_grade', e.target.value)} placeholder="e.g. 32.5" data-testid="input-quality-grade" />
          {errors.quality_grade && <span className="field-error">{errors.quality_grade}</span>}
        </div>
        <div className="field full">
          <label>Shift note</label>
          <textarea className="input" value={form.note} onChange={(e) => setField('note', e.target.value)} placeholder="What changed from plan?" data-testid="textarea-production-note" />
        </div>
      </div>

      {errors.submit && <div className="alert-strip danger" style={{ marginTop: 14 }}><AlertTriangle size={15} color="hsl(var(--destructive))" /><span>{errors.submit}</span></div>}

      <button className="btn primary" style={{ marginTop: 18 }} onClick={handleSubmit} disabled={status === 'saving'} data-testid="button-submit-production">
        {status === 'saving' ? <Loader2 size={14} className="spin" /> : <Check size={14} />}
        {status === 'saving' ? 'Saving…' : isEditing ? 'Save changes' : 'Submit production'}
      </button>
    </section>
  );
}
