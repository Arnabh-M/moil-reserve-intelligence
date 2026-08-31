import React, { useState } from 'react';
import { Upload, ChevronDown, FileText, CheckCircle } from 'lucide-react';
import { Card, Button } from '../components';
import { sites, equipment } from '../data/mockData';

export default function DataInput() {
  // Equipment form state
  const [eqId, setEqId] = useState(equipment[0].id);
  const [eqStatus, setEqStatus] = useState('up');
  const [eqReason, setEqReason] = useState('');
  const [eqSubmitted, setEqSubmitted] = useState(false);

  // Production form state
  const [prodSite, setProdSite] = useState(sites[0].id);
  const [prodDate, setProdDate] = useState('2026-08-31');
  const [prodOutput, setProdOutput] = useState('');
  const [prodSubmitted, setProdSubmitted] = useState(false);

  // File upload state
  const [dragActive, setDragActive] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);

  const handleEqSubmit = (e) => {
    e.preventDefault();
    setEqSubmitted(true);
    setTimeout(() => setEqSubmitted(false), 2500);
  };

  const handleProdSubmit = (e) => {
    e.preventDefault();
    setProdSubmitted(true);
    setTimeout(() => setProdSubmitted(false), 2500);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) setUploadedFile(file);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) setUploadedFile(file);
  };

  return (
    <div className="page-container">
      <h2 className="page-title">Data Input</h2>
      <p className="page-subtitle">
        Submit field observations, equipment updates, and geological reports
      </p>

      {/* Two forms side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Equipment Status Form */}
        <Card title="Equipment Status Update" subtitle="Report equipment status changes">
          <form onSubmit={handleEqSubmit} className="space-y-4 mt-1">
            {/* Equipment dropdown */}
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">
                Equipment
              </label>
              <div className="relative">
                <select
                  value={eqId}
                  onChange={e => setEqId(e.target.value)}
                  className="w-full appearance-none bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20"
                >
                  {equipment.map(eq => (
                    <option key={eq.id} value={eq.id}>
                      {eq.name} — {eq.site_id}
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
              </div>
            </div>

            {/* Status radio */}
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-2">
                Status
              </label>
              <div className="flex gap-3">
                {['up', 'down'].map(val => (
                  <label
                    key={val}
                    className={`flex items-center gap-2 flex-1 px-4 py-3 rounded-lg border cursor-pointer transition-all duration-150 ${
                      eqStatus === val
                        ? val === 'up'
                          ? 'bg-success/5 border-success/30 text-success'
                          : 'bg-danger/5 border-danger/30 text-danger'
                        : 'bg-bg border-border text-text-secondary hover:border-teal/30'
                    }`}
                  >
                    <input
                      type="radio"
                      name="eqStatus"
                      value={val}
                      checked={eqStatus === val}
                      onChange={e => setEqStatus(e.target.value)}
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
                    <span className="text-sm font-medium capitalize">{val === 'up' ? 'Operational' : 'Down'}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Reason */}
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">
                Reason / Notes
              </label>
              <textarea
                value={eqReason}
                onChange={e => setEqReason(e.target.value)}
                placeholder="Describe the status change reason..."
                rows={3}
                className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20 resize-none placeholder:text-text-muted"
              />
            </div>

            {/* Submit */}
            <Button type="submit" variant="primary" className="w-full" disabled={eqSubmitted}>
              {eqSubmitted ? (
                <span className="flex items-center gap-2">
                  <CheckCircle size={14} /> Submitted
                </span>
              ) : (
                'Submit Status Update'
              )}
            </Button>
          </form>
        </Card>

        {/* Production Entry Form */}
        <Card title="Production Entry" subtitle="Record daily production output">
          <form onSubmit={handleProdSubmit} className="space-y-4 mt-1">
            {/* Site dropdown */}
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">
                Mine Site
              </label>
              <div className="relative">
                <select
                  value={prodSite}
                  onChange={e => setProdSite(e.target.value)}
                  className="w-full appearance-none bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20"
                >
                  {sites.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
              </div>
            </div>

            {/* Date picker */}
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">
                Date
              </label>
              <input
                type="date"
                value={prodDate}
                onChange={e => setProdDate(e.target.value)}
                className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20"
              />
            </div>

            {/* Actual output */}
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">
                Actual Output (tonnes)
              </label>
              <input
                type="number"
                min={0}
                step={0.1}
                value={prodOutput}
                onChange={e => setProdOutput(e.target.value)}
                placeholder="e.g. 1210.5"
                className="w-full bg-bg border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary outline-none transition-colors duration-150 hover:border-teal/40 focus:border-teal focus:ring-1 focus:ring-teal/20 placeholder:text-text-muted"
              />
            </div>

            {/* Submit */}
            <Button type="submit" variant="primary" className="w-full" disabled={prodSubmitted}>
              {prodSubmitted ? (
                <span className="flex items-center gap-2">
                  <CheckCircle size={14} /> Submitted
                </span>
              ) : (
                'Submit Production Entry'
              )}
            </Button>
          </form>
        </Card>
      </div>

      {/* PDF Upload */}
      <Card title="Geological Report Upload" subtitle="Upload PDF reports for AI-assisted analysis">
        <div
          onDragOver={e => { e.preventDefault(); setDragActive(true); }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('pdf-upload-input').click()}
          className={`relative mt-1 border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200 ${
            dragActive
              ? 'border-orange bg-orange/5'
              : uploadedFile
                ? 'border-success/40 bg-success/5'
                : 'border-border hover:border-teal/40 hover:bg-teal/5'
          }`}
        >
          <input
            id="pdf-upload-input"
            type="file"
            accept=".pdf"
            onChange={handleFileSelect}
            className="sr-only"
          />

          {uploadedFile ? (
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-xl bg-success/10 flex items-center justify-center mb-3">
                <FileText size={24} className="text-success" />
              </div>
              <p className="text-sm font-semibold text-success mb-1">{uploadedFile.name}</p>
              <p className="text-xs text-text-muted">
                {(uploadedFile.size / 1024).toFixed(1)} KB — Ready for processing
              </p>
              <button
                onClick={e => { e.stopPropagation(); setUploadedFile(null); }}
                className="mt-3 text-xs text-text-muted hover:text-danger transition-colors duration-150"
              >
                Remove file
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <div className="w-12 h-12 rounded-xl bg-bg flex items-center justify-center mb-3 border border-border">
                <Upload size={24} className="text-text-muted" />
              </div>
              <p className="text-sm font-medium text-text-primary mb-1">
                Drop geological report PDF here or click to browse
              </p>
              <p className="text-xs text-text-muted">
                Supports PDF files up to 25 MB — reports will be parsed by the AI pipeline
              </p>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
