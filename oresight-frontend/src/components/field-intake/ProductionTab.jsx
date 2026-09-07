import { useState } from 'react';
import { AlertTriangle, Check, Loader2 } from 'lucide-react';
import { api } from '../../api/client';

const SITE_OPTIONS = [
  { id: 1, name: 'Balaghat' },
  { id: 2, name: 'Nagpur' },
  { id: 3, name: 'Bhandara' },
];

const VARIANCE_REASONS = ['Equipment failure', 'Maintenance', 'Weather', 'Material availability', 'Labour shortage', 'Geological conditions', 'Safety stoppage', 'Other'];

const STATUS_COPY = {
  on_target: { label: 'On target', pill: 'good' },
  slightly_below: { label: 'Slightly below target', pill: 'warn' },
  significantly_below: { label: 'Significantly below target', pill: 'critical' },
};

const initialForm = {
  site_id: 1,
  date: '2026-09-05',
  actual_output: '',
  target_output: '',
  operating_hours: '',
  downtime_hours: '',
  material_processed: '',
  quality_grade: '',
  variance_reasons: [],
  variance_other: '',
  note: '',
};

function classifyVariance(variancePct) {
  if (variancePct === null) return null;
  if (variancePct >= -3) return 'on_target';
  if (variancePct >= -12) return 'slightly_below';
  return 'significantly_below';
}

export default function ProductionTab({ showToast }) {
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState('idle');
  const [errors, setErrors] = useState({});

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const toggleReason = (reason) => setForm((f) => ({
    ...f,
    variance_reasons: f.variance_reasons.includes(reason) ? f.variance_reasons.filter((r) => r !== reason) : [...f.variance_reasons, reason],
  }));

  const actual = form.actual_output === '' ? null : Number(form.actual_output);
  const target = form.target_output === '' ? null : Number(form.target_output);
  const hasBoth = actual !== null && target !== null && !Number.isNaN(actual) && !Number.isNaN(target) && target > 0;
  const diff = hasBoth ? actual - target : null;
  const pctAchieved = hasBoth ? (actual / target) * 100 : null;
  const variancePct = hasBoth ? (diff / target) * 100 : null;
  const varianceState = classifyVariance(variancePct);
  const isBelowTarget = diff !== null && diff < 0;

  const validate = () => {
    const next = {};
    if (form.actual_output === '' || Number.isNaN(actual)) next.actual_output = 'Enter the actual tonnes produced.';
    else if (actual < 0) next.actual_output = 'Actual output cannot be negative.';
    if (form.target_output === '' || Number.isNaN(target)) next.target_output = 'Enter a target output.';
    else if (target < 0) next.target_output = 'Target output cannot be negative.';
    else if (target === 0) next.target_output = 'Target output must be greater than zero.';
    if (!form.date) next.date = 'Select a shift date.';
    if (varianceState === 'significantly_below' && form.variance_reasons.length === 0) next.variance_reasons = 'Select at least one reason for the shortfall.';
    if (form.variance_reasons.includes('Other') && !form.variance_other.trim()) next.variance_other = 'Describe the other reason.';
    if (form.operating_hours !== '' && (Number(form.operating_hours) < 0 || Number(form.operating_hours) > 24)) next.operating_hours = 'Enter hours between 0 and 24.';
    if (form.downtime_hours !== '' && Number(form.downtime_hours) < 0) next.downtime_hours = 'Downtime cannot be negative.';
    if (form.quality_grade !== '' && (Number(form.quality_grade) < 0 || Number(form.quality_grade) > 100)) next.quality_grade = 'Enter a grade between 0 and 100%.';
    return next;
  };

  const handleSubmit = async () => {
    const nextErrors = validate();
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) { setStatus('error'); return; }
    setStatus('saving');
    try {
      await api.createProduction({ site_id: form.site_id, date: form.date, actual_output: actual, target_output: target });
      setStatus('saved');
      showToast('Daily production submitted');
      setForm((f) => ({ ...initialForm, site_id: f.site_id, date: f.date }));
      setTimeout(() => setStatus((s) => (s === 'saved' ? 'idle' : s)), 2200);
    } catch (submitError) {
      setStatus('error');
      setErrors({ submit: submitError.status === 409 ? 'A production record has already been submitted for this site and date.' : (submitError.detail || 'Could not submit production. Please try again.') });
    }
  };

  const statusPill = status === 'saving' ? { label: 'Saving…', pill: 'warn' }
    : status === 'saved' ? { label: 'Saved', pill: 'good' }
    : status === 'error' ? { label: 'Needs attention', pill: 'critical' }
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
        </div>
      )}

      {isBelowTarget && (
        <div className="field full" style={{ marginTop: 16 }}>
          <label>Why was production below target?</label>
          <div className="chip-row">
            {VARIANCE_REASONS.map((reason) => (
              <button type="button" key={reason} className={`chip ${form.variance_reasons.includes(reason) ? 'selected' : ''}`} onClick={() => toggleReason(reason)} data-testid={`chip-reason-${reason.toLowerCase().replaceAll(' ', '-')}`}>
                {reason}
              </button>
            ))}
          </div>
          {errors.variance_reasons && <span className="field-error">{errors.variance_reasons}</span>}
          {form.variance_reasons.includes('Other') && (
            <div style={{ marginTop: 10 }}>
              <input className="input" style={{ width: '100%' }} value={form.variance_other} onChange={(e) => setField('variance_other', e.target.value)} placeholder="Describe the reason" data-testid="input-variance-other" />
              {errors.variance_other && <span className="field-error">{errors.variance_other}</span>}
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
        {status === 'saving' ? 'Saving…' : 'Submit production'}
      </button>
    </section>
  );
}
