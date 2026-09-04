import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  Upload, ChevronDown, FileText, CheckCircle2, Loader2, X, AlertCircle, TrendingUp, TrendingDown,
  Network, Eye,
} from 'lucide-react';
import { Card, Button, Badge, InlineError } from '../components';
import { postEquipmentStatus, postProduction, getEquipment, uploadReport, USE_MOCK } from '../api/client';
import { sites } from '../data/mockData';

const DEFAULT_TARGETS = {
  1: 1250.0,
  2: 1050.0,
  3: 980.0,
  balaghat: 1250.0,
  nagpur: 1050.0,
  bhandara: 980.0,
};

// Resolve an extracted deposit's belt/zone string to a numeric site id so the
// "View in graph" link can jump to that site — mirrors the backend's
// name-based match (app/routers/reports.py:_match_site).
const SITE_KEY_TO_ID = { balaghat: 1, nagpur: 2, bhandara: 3 };
function resolveSiteFromBeltZones(beltZones) {
  const hay = beltZones.map(z => (z || '').toLowerCase());
  for (const [key, id] of Object.entries(SITE_KEY_TO_ID)) {
    if (hay.some(z => z.includes(key))) return id;
  }
  return null;
}

export default function DataInput() {
  const navigate = useNavigate();

  // ── Equipment Form State ─────────────────────────────────────────────
  const [equipmentList, setEquipmentList] = useState([]);
  const [loadingEq, setLoadingEq] = useState(true);
  const [equipmentError, setEquipmentError] = useState(null);
  const [eqId, setEqId] = useState('');
  const [eqStatus, setEqStatus] = useState('up');
  const [eqReason, setEqReason] = useState('');
  const [isSubmittingEq, setIsSubmittingEq] = useState(false);
  const [eqErrors, setEqErrors] = useState({});

  // ── Production Form State ────────────────────────────────────────────
  const [prodSite, setProdSite] = useState(1);
  const [prodDate, setProdDate] = useState('2026-08-31');
  const [prodActual, setProdActual] = useState('');
  const [prodTarget, setProdTarget] = useState(DEFAULT_TARGETS[1]);
  const [isSubmittingProd, setIsSubmittingProd] = useState(false);
  const [prodErrors, setProdErrors] = useState({});

  // ── PDF Upload State ─────────────────────────────────────────────────
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  // Load equipment catalog
  const loadEquipmentCatalog = async () => {
    try {
      setLoadingEq(true);
      setEquipmentError(null);
      const data = await getEquipment();
      setEquipmentList(data);
      if (data.length > 0) {
        setEqId(data[0].id);
        setEqStatus(data[0].status);
        setEqReason(data[0].status_reason || '');
      }
    } catch (err) {
      console.error('Failed to load equipment catalog:', err);
      setEquipmentError(err.message || 'Unable to load equipment catalog.');
    } finally {
      setLoadingEq(false);
    }
  };

  useEffect(() => {
    loadEquipmentCatalog();
  }, []);

  const handleEquipmentChange = (selectedId) => {
    setEqId(selectedId);
    setEqErrors({});
    const found = equipmentList.find(e => String(e.id) === String(selectedId));
    if (found) {
      setEqStatus(found.status);
      setEqReason(found.status_reason || '');
    }
  };

  const handleSiteChange = (selectedSite) => {
    const numId = Number(selectedSite);
    setProdSite(numId);
    setProdTarget(DEFAULT_TARGETS[numId] || 1000);
    setProdErrors(prev => ({ ...prev, site: undefined }));
  };

  // ── Equipment Form Submit Handler ────────────────────────────────────
  const handleEqSubmit = async (e) => {
    e.preventDefault();
    const errors = {};

    if (!eqId) {
      errors.eqId = 'Please select an equipment unit';
    }

    if (eqStatus === 'down' && !eqReason.trim()) {
      errors.reason = 'Reason is required when marking equipment as down';
    }

    if (Object.keys(errors).length > 0) {
      setEqErrors(errors);
      return;
    }

    setEqErrors({});
    setIsSubmittingEq(true);

    try {
      const updated = await postEquipmentStatus(eqId, {
        status: eqStatus,
        reason: eqReason.trim() || null,
      });

      // Update in-memory catalog
      setEquipmentList(prev =>
        prev.map(item => String(item.id) === String(updated.id) ? { ...item, ...updated } : item)
      );

      // Success toast via react-hot-toast (styled with teal/navy)
      toast.success(
        <div>
          <p className="font-semibold text-xs">Equipment status updated</p>
          <p className="text-[11px] text-white/70 mt-0.5">
            {updated.name} is now marked {updated.status.toUpperCase()}
          </p>
        </div>,
        {
          id: 'eq-status-toast',
        }
      );

      // Clear form on success
      setEqReason('');
      setEqStatus('up');
    } catch (err) {
      // Error toast styled with muted red; keep form inputs intact
      toast.error(
        <div>
          <p className="font-semibold text-xs">Failed to update equipment</p>
          <p className="text-[11px] text-white/70 mt-0.5">{err.message}</p>
        </div>,
        {
          id: 'eq-status-error',
        }
      );
    } finally {
      setIsSubmittingEq(false);
    }
  };

  // ── Production Form Validation & Submit Handler ──────────────────────
  const handleProdSubmit = async (e) => {
    e.preventDefault();
    const errors = {};

    // 1. Site validation
    if (!prodSite) {
      errors.site = 'Site selection is required';
    }

    // 2. Date validation
    if (!prodDate) {
      errors.date = 'Date is required';
    }

    // 3. Actual output validation (must be positive number)
    const actual = parseFloat(prodActual);
    if (prodActual === '' || isNaN(actual)) {
      errors.actual = 'Actual output is required';
    } else if (actual < 0) {
      errors.actual = 'Actual output must be a positive number';
    }

    // 4. Target output validation (must be positive number)
    const target = parseFloat(prodTarget);
    if (prodTarget === '' || isNaN(target)) {
      errors.target = 'Target output is required';
    } else if (target <= 0) {
      errors.target = 'Target output must be greater than 0';
    }

    if (Object.keys(errors).length > 0) {
      setProdErrors(errors);
      return;
    }

    setProdErrors({});
    setIsSubmittingProd(true);

    try {
      const record = await postProduction({
        site_id: prodSite,
        date: prodDate,
        actual_output: actual,
        target_output: target,
      });

      const selectedSiteName = sites.find(s => s.id === Number(prodSite) || s.id === prodSite)?.name || `Site ${prodSite}`;

      toast.success(
        <div>
          <p className="font-semibold text-xs">Production recorded successfully</p>
          <p className="text-[11px] text-white/70 mt-0.5">
            {selectedSiteName} ({record.date}): {record.actual_output} t (Variance: {record.variance_pct >= 0 ? '+' : ''}{record.variance_pct}%)
          </p>
        </div>,
        {
          id: 'prod-record-toast',
        }
      );

      // Clear actual output on success
      setProdActual('');
    } catch (err) {
      toast.error(
        <div>
          <p className="font-semibold text-xs">Failed to record production</p>
          <p className="text-[11px] text-white/70 mt-0.5">{err.message}</p>
        </div>,
        {
          id: 'prod-record-error',
        }
      );
    } finally {
      setIsSubmittingProd(false);
    }
  };

  // ── PDF Upload Handler (real API) ────────────────────────────────────
  const processFile = async (file) => {
    if (!file) return;
    if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
      toast.error('Only PDF geological reports are accepted.');
      return;
    }

    setUploadedFile(file);
    setIsUploading(true);
    setUploadResult(null);
    setUploadError(null);

    try {
      const result = await uploadReport(file);
      setUploadResult(result);
      if (result.text_extracted === false) {
        toast.error('No readable text found in that PDF');
      } else {
        const n = result.deposit_count ?? (result.deposits?.length ?? 0);
        toast.success(`Report parsed — ${n} deposit${n === 1 ? '' : 's'} extracted`);
      }
    } catch (err) {
      console.error('[DataInput] PDF upload failed:', err);
      setUploadError(
        err.isServiceUnavailable
          ? 'The backend is temporarily unavailable. Please retry shortly.'
          : (err.message || 'Failed to upload and parse the report.')
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleRetryUpload = () => {
    if (uploadedFile) {
      processFile(uploadedFile);
    }
  };

  const handleClearUpload = () => {
    setUploadedFile(null);
    setUploadResult(null);
    setUploadError(null);
    setIsUploading(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) processFile(file);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const currentSelectedEq = equipmentList.find(e => String(e.id) === String(eqId));
  const currentActual = parseFloat(prodActual);
  const currentTarget = parseFloat(prodTarget);
  const liveVariance = (!isNaN(currentActual) && !isNaN(currentTarget) && currentTarget > 0)
    ? Math.round(((currentActual - currentTarget) / currentTarget) * 1000) / 10
    : null;

  // Helper to safely display a field value or "—"
  const displayField = (value) => (value != null && value !== '' ? String(value) : '—');

  // ── Upload result shape: { filename, text_extracted, deposit_count,
  //    deposits[], nodes_created[], warnings[] } ─────────────────────────
  const uploadOk = !!uploadResult && uploadResult.text_extracted === true;
  const uploadNoText = !!uploadResult && uploadResult.text_extracted === false;
  const uploadDeposits = uploadOk && Array.isArray(uploadResult.deposits) ? uploadResult.deposits : [];
  const uploadNodes = uploadResult && Array.isArray(uploadResult.nodes_created) ? uploadResult.nodes_created : [];
  const uploadWarnings = uploadResult && Array.isArray(uploadResult.warnings) ? uploadResult.warnings : [];
  const graphSiteId = uploadDeposits.length
    ? resolveSiteFromBeltZones(uploadDeposits.map(d => d.belt_zone))
    : null;

  return (
    <div className="page-container">
      {/* Page Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="page-title">Data Input</h2>
          <p className="page-subtitle mb-0">
            Submit field observations, equipment updates, and geological reports
          </p>
        </div>

        {/* Development MOCK indicator */}
        {USE_MOCK && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-600 text-xs font-bold shadow-xs animate-fade-in">
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            USE_MOCK = true (Simulated API)
          </div>
        )}
      </div>

      {/* Two forms side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Equipment Status Form */}
        <Card
          title="Equipment Status Update"
          subtitle="Report telemetry status changes for mine machinery"
          action={
            currentSelectedEq && (
              <Badge variant={currentSelectedEq.status} dot>
                {currentSelectedEq.status === 'up' ? 'Operational' : 'Down'}
              </Badge>
            )
          }
        >
          <form onSubmit={handleEqSubmit} className="space-y-4 mt-2">
            {/* Equipment Dropdown */}
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                Select Equipment
              </label>
              <div className={`relative ${loadingEq ? 'animate-pulse' : ''}`}>
                <select
                  value={eqId}
                  disabled={loadingEq || isSubmittingEq || !!equipmentError}
                  onChange={e => handleEquipmentChange(e.target.value)}
                  className={`w-full appearance-none bg-bg border rounded-lg px-3.5 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 ${
                    eqErrors.eqId
                      ? 'border-danger focus:border-danger'
                      : 'border-border hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20'
                  }`}
                >
                  {loadingEq ? (
                    <option>Loading equipment catalog...</option>
                  ) : equipmentError ? (
                    <option>Equipment catalog unavailable</option>
                  ) : (
                    equipmentList.map(eq => (
                      <option key={eq.id} value={eq.id}>
                        {eq.name} — {eq.site_name || 'Unknown Site'} ({(eq.status || 'unknown').toUpperCase()})
                      </option>
                    ))
                  )}
                </select>
                <ChevronDown size={14} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
              </div>
              {eqErrors.eqId && (
                <p className="text-[11px] text-danger mt-1 flex items-center gap-1 font-medium">
                  <AlertCircle size={12} /> {eqErrors.eqId}
                </p>
              )}
              {equipmentError && (
                <InlineError
                  message="Unable to load equipment catalog."
                  onRetry={loadEquipmentCatalog}
                  className="mt-2"
                />
              )}
            </div>

            {/* Status Radio Group */}
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-2">
                Machine Operational State
              </label>
              <div className="flex gap-3">
                {[
                  { val: 'up', label: 'Operational (Up)' },
                  { val: 'down', label: 'Down / Breakdown' },
                ].map(({ val, label }) => (
                  <label
                    key={val}
                    className={`flex items-center gap-2.5 flex-1 px-4 py-3 rounded-lg border cursor-pointer transition-all duration-150 ${
                      eqStatus === val
                        ? val === 'up'
                          ? 'bg-success/5 border-success/40 text-success shadow-xs'
                          : 'bg-danger/5 border-danger/40 text-danger shadow-xs'
                        : 'bg-bg border-border text-text-secondary hover:border-teal/30'
                    }`}
                  >
                    <input
                      type="radio"
                      name="eqStatus"
                      value={val}
                      checked={eqStatus === val}
                      onChange={e => setEqStatus(e.target.value)}
                      disabled={isSubmittingEq}
                      className="sr-only"
                    />
                    <span
                      className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                        eqStatus === val
                          ? val === 'up'
                            ? 'border-success'
                            : 'border-danger'
                          : 'border-border'
                      }`}
                    >
                      {eqStatus === val && (
                        <span
                          className={`w-2 h-2 rounded-full ${
                            val === 'up' ? 'bg-success' : 'bg-danger'
                          }`}
                        />
                      )}
                    </span>
                    <span className="text-xs font-bold">{label}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Reason Textarea */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-text-secondary">
                  Reason / Maintenance Notes
                </label>
                {eqStatus === 'down' && (
                  <span className="text-[10px] text-danger font-semibold">* Required when Down</span>
                )}
              </div>
              <textarea
                value={eqReason}
                disabled={isSubmittingEq}
                onChange={e => {
                  setEqReason(e.target.value);
                  if (eqErrors.reason) setEqErrors(prev => ({ ...prev, reason: undefined }));
                }}
                placeholder={
                  eqStatus === 'down'
                    ? 'e.g. Hydraulic pump pressure loss - parts on order'
                    : 'Optional observations or service notes...'
                }
                rows={3}
                className={`w-full bg-bg border rounded-lg px-3.5 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 resize-none placeholder:text-text-muted ${
                  eqErrors.reason
                    ? 'border-danger focus:border-danger'
                    : 'border-border hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20'
                }`}
              />
              {eqErrors.reason && (
                <p className="text-[11px] text-danger mt-1 flex items-center gap-1 font-medium">
                  <AlertCircle size={12} /> {eqErrors.reason}
                </p>
              )}
            </div>

            {/* Submit Button with Spinner */}
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={isSubmittingEq || loadingEq || !!equipmentError}
            >
              {isSubmittingEq ? (
                <span className="flex items-center gap-2">
                  <Loader2 size={15} className="animate-spin" /> Submitting Status...
                </span>
              ) : (
                'Submit Status Update'
              )}
            </Button>
          </form>
        </Card>

        {/* Production Entry Form */}
        <Card
          title="Daily Production Entry"
          subtitle="Record actual extraction output against daily targets"
        >
          <form onSubmit={handleProdSubmit} className="space-y-4 mt-2">
            {/* Mine Site Dropdown */}
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                Mine Site
              </label>
              <div className="relative">
                <select
                  value={prodSite}
                  disabled={isSubmittingProd}
                  onChange={e => handleSiteChange(e.target.value)}
                  className={`w-full appearance-none bg-bg border rounded-lg px-3.5 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 ${
                    prodErrors.site
                      ? 'border-danger focus:border-danger'
                      : 'border-border hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20'
                  }`}
                >
                  <option value={1}>Balaghat Mine (Balaghat Manganese Belt)</option>
                  <option value={2}>Nagpur Mine (Nagpur-Bhandara Belt)</option>
                  <option value={3}>Bhandara Mine (Nagpur-Bhandara Belt)</option>
                </select>
                <ChevronDown size={14} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
              </div>
              {prodErrors.site && (
                <p className="text-[11px] text-danger mt-1 flex items-center gap-1 font-medium">
                  <AlertCircle size={12} /> {prodErrors.site}
                </p>
              )}
            </div>

            {/* Date Picker */}
            <div>
              <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                Production Date
              </label>
              <input
                type="date"
                value={prodDate}
                disabled={isSubmittingProd}
                onChange={e => {
                  setProdDate(e.target.value);
                  if (prodErrors.date) setProdErrors(prev => ({ ...prev, date: undefined }));
                }}
                className={`w-full bg-bg border rounded-lg px-3.5 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 ${
                  prodErrors.date
                    ? 'border-danger focus:border-danger'
                    : 'border-border hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20'
                }`}
              />
              {prodErrors.date && (
                <p className="text-[11px] text-danger mt-1 flex items-center gap-1 font-medium">
                  <AlertCircle size={12} /> {prodErrors.date}
                </p>
              )}
            </div>

            {/* Actual Output & Target Output Grid */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Actual Output (t)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={prodActual}
                  disabled={isSubmittingProd}
                  onChange={e => {
                    setProdActual(e.target.value);
                    if (prodErrors.actual) setProdErrors(prev => ({ ...prev, actual: undefined }));
                  }}
                  placeholder="e.g. 1235.4"
                  className={`w-full bg-bg border rounded-lg px-3.5 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 placeholder:text-text-muted ${
                    prodErrors.actual
                      ? 'border-danger focus:border-danger'
                      : 'border-border hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20'
                  }`}
                />
                {prodErrors.actual && (
                  <p className="text-[11px] text-danger mt-1 flex items-center gap-1 font-medium">
                    <AlertCircle size={12} /> {prodErrors.actual}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-text-secondary mb-1.5">
                  Target Output (t)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={prodTarget}
                  disabled={isSubmittingProd}
                  onChange={e => {
                    setProdTarget(e.target.value);
                    if (prodErrors.target) setProdErrors(prev => ({ ...prev, target: undefined }));
                  }}
                  placeholder="e.g. 1250"
                  className={`w-full bg-bg border rounded-lg px-3.5 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 ${
                    prodErrors.target
                      ? 'border-danger focus:border-danger'
                      : 'border-border hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20'
                  }`}
                />
                {prodErrors.target && (
                  <p className="text-[11px] text-danger mt-1 flex items-center gap-1 font-medium">
                    <AlertCircle size={12} /> {prodErrors.target}
                  </p>
                )}
              </div>
            </div>

            {/* Calculated Live Variance */}
            {liveVariance !== null && (
              <div className="flex items-center justify-between p-2.5 rounded-lg bg-bg border border-border text-xs">
                <span className="text-text-muted font-medium">Projected Variance:</span>
                <span className={`font-bold flex items-center gap-1 ${liveVariance >= 0 ? 'text-success' : 'text-danger'}`}>
                  {liveVariance >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                  {liveVariance >= 0 ? `+${liveVariance}% (Over Target)` : `${liveVariance}% (Under Target)`}
                </span>
              </div>
            )}

            {/* Submit Button with Spinner */}
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={isSubmittingProd}
            >
              {isSubmittingProd ? (
                <span className="flex items-center gap-2">
                  <Loader2 size={15} className="animate-spin" /> Recording Production...
                </span>
              ) : (
                'Submit Production Entry'
              )}
            </Button>
          </form>
        </Card>
      </div>

      {/* PDF Upload Card */}
      <Card title="Geological Report PDF Upload" subtitle="Drop exploration or borehole lithology reports for parsing">
        <div
          onDragOver={e => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => {
            // Don't reopen file picker when result/error is showing
            if (!uploadResult && !uploadError && !isUploading) {
              document.getElementById('pdf-upload-input').click();
            }
          }}
          className={`relative mt-1 border-2 border-dashed rounded-xl p-8 text-center transition-all duration-150 ${
            dragActive
              ? 'border-orange bg-orange/5 scale-[1.005] cursor-pointer'
              : uploadOk
                ? 'border-success/40 bg-success/5'
                : uploadNoText
                  ? 'border-warning/40 bg-warning/5'
                  : uploadError
                    ? 'border-danger/40 bg-danger/5'
                    : isUploading
                      ? 'border-orange/40 bg-orange/5'
                      : 'border-border hover:border-teal/40 hover:bg-teal/5 cursor-pointer'
          }`}
        >
          <input
            id="pdf-upload-input"
            type="file"
            accept=".pdf"
            onChange={handleFileSelect}
            className="sr-only"
          />

          {/* === Uploading state (spinner) === */}
          {isUploading && uploadedFile && (
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-xl bg-orange/10 flex items-center justify-center mb-3 text-orange">
                <Loader2 size={24} className="animate-spin" />
              </div>
              <p className="text-sm font-semibold text-text-primary mb-0.5">{uploadedFile.name}</p>
              <p className="text-xs text-text-muted mb-2">
                {(uploadedFile.size / 1024).toFixed(1)} KB — Extracting lithology tables…
              </p>
              <div className="w-48 bg-border rounded-full h-1.5 overflow-hidden">
                <div className="h-full bg-orange rounded-full animate-pulse" style={{ width: '60%' }} />
              </div>
            </div>
          )}

          {/* === Success state — deposits extracted === */}
          {!isUploading && uploadOk && uploadedFile && (
            <div className="flex flex-col items-center w-full" onClick={e => e.stopPropagation()}>
              <div className="w-12 h-12 rounded-xl bg-success/10 flex items-center justify-center mb-3 text-success">
                <CheckCircle2 size={24} />
              </div>
              <p className="text-sm font-semibold text-text-primary mb-1">
                {uploadResult.filename || uploadedFile.name}
              </p>
              <p className="text-xs text-text-muted mb-4">
                {(uploadedFile.size / 1024).toFixed(1)} KB — {uploadResult.deposit_count} deposit
                {uploadResult.deposit_count === 1 ? '' : 's'} extracted
              </p>

              {/* One card per extracted deposit */}
              {uploadDeposits.length > 0 ? (
                <div className="w-full max-w-lg space-y-3 mb-4">
                  {uploadDeposits.map((dep, i) => (
                    <div
                      key={dep.deposit_id || i}
                      className="bg-white rounded-lg border border-border p-3 shadow-xs text-left"
                    >
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <p className="text-sm font-bold text-navy truncate" title={displayField(dep.deposit_id)}>
                          {displayField(dep.deposit_id)}
                        </p>
                        {dep.belt_zone && (
                          <span className="text-[10px] text-text-muted truncate" title={dep.belt_zone}>
                            {dep.belt_zone}
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        <div>
                          <p className="text-[10px] text-text-muted font-semibold uppercase tracking-wide mb-0.5">Depth</p>
                          <p className="text-sm font-bold text-navy">
                            {dep.depth != null ? `${dep.depth}m` : '—'}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-text-muted font-semibold uppercase tracking-wide mb-0.5">Grade</p>
                          <p className="text-sm font-bold text-orange">
                            {dep.grade != null ? `${dep.grade}%` : '—'}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-text-muted font-semibold uppercase tracking-wide mb-0.5">Structure</p>
                          <p className="text-sm font-bold text-teal truncate" title={displayField(dep.structure_type)}>
                            {displayField(dep.structure_type)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-muted mb-4 max-w-sm">
                  Text was read, but no deposit entities could be extracted — see notes below.
                </p>
              )}

              {/* Graph nodes MERGE-d by this upload */}
              <div className="w-full max-w-lg mb-4 text-left">
                <p className="text-[10px] text-text-muted font-semibold uppercase tracking-wide mb-1.5 flex items-center gap-1">
                  <Network size={12} /> Graph nodes created
                </p>
                {uploadNodes.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {uploadNodes.map(node => (
                      <span
                        key={node.id}
                        title={node.id}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white border border-border text-[11px]"
                      >
                        <span className="font-semibold text-text-primary">{node.label}</span>
                        <span className="text-text-muted">{node.type}</span>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-text-muted">
                    No graph nodes were created — see notes below.
                  </p>
                )}
              </div>

              {/* Warnings from the extraction / graph write */}
              {uploadWarnings.length > 0 && (
                <div className="w-full max-w-lg mb-4 space-y-1.5 text-left">
                  {uploadWarnings.map((w, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-[11px] text-warning bg-warning/10 border border-warning/20 rounded-lg px-3 py-2"
                    >
                      <AlertCircle size={13} className="shrink-0 mt-0.5" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Action buttons */}
              <div className="flex items-center gap-3">
                {graphSiteId && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => navigate(`/site/${graphSiteId}`)}
                  >
                    <Eye size={14} />
                    View in graph
                  </Button>
                )}
                <button
                  onClick={handleClearUpload}
                  className="text-xs text-text-muted hover:text-danger flex items-center gap-1 transition-colors duration-150"
                >
                  <X size={12} /> Upload another
                </button>
              </div>
            </div>
          )}

          {/* === Parsed, but no extractable text (distinct from success) === */}
          {!isUploading && uploadNoText && uploadedFile && (
            <div className="flex flex-col items-center" onClick={e => e.stopPropagation()}>
              <div className="w-12 h-12 rounded-xl bg-warning/10 flex items-center justify-center mb-3 text-warning">
                <FileText size={24} />
              </div>
              <p className="text-sm font-semibold text-text-primary mb-0.5">
                {uploadResult.filename || uploadedFile.name}
              </p>
              <p className="text-xs text-text-muted mb-3 max-w-sm">
                No readable text could be extracted from this PDF — it may be a scan or an
                image-only export. Nothing was added to the graph.
              </p>
              {uploadWarnings.length > 0 && (
                <div className="w-full max-w-sm mb-3 space-y-1.5 text-left">
                  {uploadWarnings.map((w, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 text-[11px] text-warning bg-warning/10 border border-warning/20 rounded-lg px-3 py-2"
                    >
                      <AlertCircle size={13} className="shrink-0 mt-0.5" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex items-center gap-3">
                <Button variant="primary" size="sm" onClick={handleRetryUpload}>
                  Retry Upload
                </Button>
                <button
                  onClick={handleClearUpload}
                  className="text-xs text-text-muted hover:text-danger flex items-center gap-1 transition-colors duration-150"
                >
                  <X size={12} /> Remove file
                </button>
              </div>
            </div>
          )}

          {/* === Error state === */}
          {!isUploading && uploadError && uploadedFile && (
            <div className="flex flex-col items-center" onClick={e => e.stopPropagation()}>
              <div className="w-12 h-12 rounded-xl bg-danger/10 flex items-center justify-center mb-3 text-danger">
                <AlertCircle size={24} />
              </div>
              <p className="text-sm font-semibold text-text-primary mb-0.5">{uploadedFile.name}</p>
              <p className="text-xs text-danger mb-3 max-w-sm">{uploadError}</p>
              <div className="flex items-center gap-3">
                <Button variant="primary" size="sm" onClick={handleRetryUpload}>
                  Retry Upload
                </Button>
                <button
                  onClick={handleClearUpload}
                  className="text-xs text-text-muted hover:text-danger flex items-center gap-1 transition-colors duration-150"
                >
                  <X size={12} /> Remove file
                </button>
              </div>
            </div>
          )}

          {/* === Empty / initial state === */}
          {!uploadedFile && !isUploading && (
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-xl bg-bg flex items-center justify-center mb-3 border border-border text-text-muted">
                <Upload size={22} />
              </div>
              <p className="text-sm font-semibold text-text-primary mb-1">
                Drop geological report PDF here or click to browse
              </p>
              <p className="text-xs text-text-muted max-w-sm">
                Upload drill-core logs and grade distribution sheets (.pdf up to 25 MB)
              </p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
