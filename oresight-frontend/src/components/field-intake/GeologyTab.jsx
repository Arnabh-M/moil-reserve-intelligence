import { useRef, useState } from 'react';
import { AlertTriangle, Check, CloudUpload, Download, Eye, FileText, Loader2, RefreshCw, Upload } from 'lucide-react';
import { api } from '../../api/client';

const MAX_BYTES = 25 * 1024 * 1024;
const PROCESSING_MIN_MS = 450;

function formatBytes(bytes) {
  if (bytes == null) return null;
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function relativeUpload(date) {
  if (!date) return 'Uploaded just now';
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return 'Uploaded just now';
  const minutes = Math.round(seconds / 60);
  return `Uploaded ${minutes} min${minutes === 1 ? '' : 's'} ago`;
}

// Real POST /reports/upload response is exactly {filename, text_extracted,
// deposit_count, deposits[], nodes_created[], warnings[]} -- group
// nodes_created by its `type` field (OreZone / StructuralFeature / ...) for
// a slightly more readable list than one flat dump.
function groupNodesByType(nodes) {
  const groups = new Map();
  for (const node of nodes || []) {
    if (!groups.has(node.type)) groups.set(node.type, []);
    groups.get(node.type).push(node);
  }
  return Array.from(groups.entries());
}

export default function GeologyTab() {
  const [stage, setStage] = useState('empty');
  const [result, setResult] = useState(null);
  const [fileMeta, setFileMeta] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const inputRef = useRef(null);
  const dragCounter = useRef(0);

  const handleFile = async (file) => {
    if (!file) return;
    const looksLikePdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    if (!looksLikePdf) { setErrorMessage('Please upload a PDF file.'); setStage('error'); return; }
    if (file.size > MAX_BYTES) { setErrorMessage('File is larger than 25 MB.'); setStage('error'); return; }

    const localUrl = URL.createObjectURL(file);
    setFileMeta({ name: file.name, size: file.size, localUrl, uploadedAt: new Date() });
    setResult(null);
    setStage('uploading');
    try {
      const uploaded = await api.uploadReport(file);
      setStage('processing');
      await new Promise((resolve) => setTimeout(resolve, PROCESSING_MIN_MS));
      setResult(uploaded);
      setStage('success');
    } catch (uploadError) {
      setErrorMessage(uploadError.detail || 'Unable to process document.');
      setStage('error');
    }
  };

  const onInputChange = (event) => { const file = event.target.files?.[0]; event.target.value = ''; handleFile(file); };
  const onDragEnter = (event) => { event.preventDefault(); dragCounter.current += 1; if (stage === 'empty' || stage === 'error') setStage('dragging'); };
  const onDragOver = (event) => { event.preventDefault(); };
  const onDragLeave = (event) => { event.preventDefault(); dragCounter.current -= 1; if (dragCounter.current <= 0) { dragCounter.current = 0; setStage((s) => (s === 'dragging' ? 'empty' : s)); } };
  const onDrop = (event) => {
    event.preventDefault();
    dragCounter.current = 0;
    const file = event.dataTransfer.files?.[0];
    if (file) handleFile(file); else setStage('empty');
  };

  const handleReplace = () => {
    if (fileMeta?.localUrl) URL.revokeObjectURL(fileMeta.localUrl);
    setFileMeta(null);
    setResult(null);
    setStage('empty');
  };

  const handleRetry = () => setStage('empty');

  const zoneClickable = stage === 'empty' || stage === 'dragging' || stage === 'error';
  const ZoneTag = zoneClickable ? 'label' : 'div';
  const zoneClass = `geo-dropzone ${stage === 'dragging' ? 'dragging' : ''} ${stage === 'error' ? 'error' : ''} ${!zoneClickable ? 'busy' : ''}`;

  const hasWarnings = result?.warnings?.length > 0;
  const extractionOk = result && result.text_extracted && !hasWarnings;
  const nodeGroups = groupNodesByType(result?.nodes_created);

  return (
    <section className="card section-card">
      <div className="card-head">
        <div><div className="card-title">Geological document upload</div><div className="card-kicker">Geological information will be extracted automatically after upload.</div></div>
        <CloudUpload size={18} color="hsl(var(--muted-foreground))" />
      </div>

      <ZoneTag
        className={zoneClass}
        onDragEnter={zoneClickable ? onDragEnter : undefined}
        onDragOver={zoneClickable ? onDragOver : undefined}
        onDragLeave={zoneClickable ? onDragLeave : undefined}
        onDrop={zoneClickable ? onDrop : undefined}
        data-testid="geology-dropzone"
      >
        {stage === 'empty' && (
          <>
            <div className="geo-dropzone-icon"><Upload size={22} /></div>
            <div className="geo-dropzone-title">Upload geological PDF</div>
            <div className="geo-dropzone-sub">Drag &amp; drop your PDF here, or <span className="link">Browse files</span></div>
            <div className="geo-dropzone-caption">PDF · Max 25 MB</div>
            <input ref={inputRef} type="file" accept="application/pdf" onChange={onInputChange} data-testid="input-geology-upload" />
          </>
        )}
        {stage === 'dragging' && (
          <>
            <div className="geo-dropzone-icon"><Upload size={22} /></div>
            <div className="geo-dropzone-title">Drop PDF to upload</div>
            <input ref={inputRef} type="file" accept="application/pdf" onChange={onInputChange} data-testid="input-geology-upload" />
          </>
        )}
        {stage === 'uploading' && (
          <>
            <div className="geo-dropzone-icon"><Loader2 size={22} className="spin" /></div>
            <div className="geo-dropzone-title">Uploading…</div>
            <div className="progress indeterminate" style={{ maxWidth: 220, margin: '14px auto 0' }}><span /></div>
          </>
        )}
        {stage === 'processing' && (
          <>
            <div className="geo-dropzone-icon"><Loader2 size={22} className="spin" /></div>
            <div className="geo-dropzone-title">Extracting geological information…</div>
          </>
        )}
        {stage === 'success' && fileMeta && (
          <div className="geo-doc-card" style={{ margin: 0, border: 0, background: 'transparent' }}>
            <div className="geo-doc-meta">
              <div className="geo-doc-icon"><FileText size={18} /></div>
              <div style={{ minWidth: 0 }}>
                <div className="geo-doc-name">✓ {fileMeta.name}</div>
                <div className="geo-doc-sub">{formatBytes(fileMeta.size)} · {relativeUpload(fileMeta.uploadedAt)}</div>
              </div>
            </div>
            <div className="geo-doc-actions">
              <button type="button" className="btn small" onClick={() => window.open(fileMeta.localUrl, '_blank', 'noopener')} data-testid="button-preview-document"><Eye size={12} /> Preview</button>
              <a className="btn small" href={fileMeta.localUrl} download={fileMeta.name} data-testid="link-download-document"><Download size={12} /> Download</a>
              <button type="button" className="btn small" onClick={handleReplace} data-testid="button-replace-document"><RefreshCw size={12} /> Replace document</button>
            </div>
          </div>
        )}
        {stage === 'error' && (
          <>
            <div className="geo-dropzone-icon" style={{ background: 'hsl(var(--destructive) / .12)', color: 'hsl(var(--destructive))' }}><AlertTriangle size={22} /></div>
            <div className="geo-dropzone-title">Unable to process document.</div>
            <div className="geo-dropzone-sub">{errorMessage}</div>
            <button type="button" className="btn small" style={{ marginTop: 12 }} onClick={handleRetry} data-testid="button-retry-upload">Try again</button>
            <input ref={inputRef} type="file" accept="application/pdf" onChange={onInputChange} style={{ display: 'none' }} />
          </>
        )}
      </ZoneTag>

      {stage === 'success' && result && (
        <div className="section-stack" style={{ marginTop: 18 }}>
          <div className="geo-extract-status" data-testid="extraction-status">
            {extractionOk ? <><Check size={13} color="hsl(var(--accent))" /> Document processed</> : result.text_extracted ? <><AlertTriangle size={13} color="hsl(39 85% 56%)" /> Extraction incomplete</> : <><AlertTriangle size={13} color="hsl(var(--destructive))" /> No extractable text found</>}
            {api.isMock && <span className="pill mock" style={{ marginLeft: 10 }}>Preview data</span>}
          </div>

          <div>
            <div className="card-title" style={{ marginBottom: 12 }}>Geological extraction</div>

            <div className="geo-info-grid">
              <div className="geo-info-row"><span className="geo-info-label">Document</span><span>{result.filename}</span></div>
              <div className="geo-info-row"><span className="geo-info-label">Deposits found</span><span>{result.deposit_count}</span></div>
              <div className="geo-info-row"><span className="geo-info-label">Upload date</span><span className="mono">{relativeUpload(fileMeta?.uploadedAt)}</span></div>
            </div>

            {nodeGroups.length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div className="field-label-heading">Causal graph nodes created</div>
                {nodeGroups.map(([type, nodes]) => (
                  <div className="geo-info-row" key={type}><span className="geo-info-label">{type}</span><span>{nodes.map((node) => node.label).join(', ')}</span></div>
                ))}
              </div>
            )}
          </div>

          {result.deposits?.length > 0 && (
            <div>
              <div className="card-kicker" style={{ marginBottom: 8 }}>Extracted deposit records</div>
              <div className="table-wrap"><table><thead><tr><th>Deposit</th><th>Depth</th><th>Grade</th><th>Structure</th><th>Belt zone</th></tr></thead><tbody>
                {result.deposits.map((deposit) => <tr key={deposit.deposit_id}><td className="mono">{deposit.deposit_id}</td><td>{deposit.depth} m</td><td>{deposit.grade}%</td><td>{deposit.structure_type}</td><td>{deposit.belt_zone}</td></tr>)}
              </tbody></table></div>
            </div>
          )}

          {hasWarnings && (
            <div className="alert-strip danger" data-testid="extraction-warnings">
              <AlertTriangle size={15} color="hsl(var(--destructive))" />
              <span>{result.warnings.join(' ')}</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
