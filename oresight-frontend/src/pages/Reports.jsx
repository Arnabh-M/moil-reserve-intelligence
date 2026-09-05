import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, FileBarChart, Gauge, ShieldAlert, ClipboardCheck, FileQuestion } from 'lucide-react';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas-pro';
import { Card, KPIStat, Badge, Button, SkeletonKPIRow, SkeletonCard, EmptyState, InlineError, SectionDivider } from '../components';
import { getSites, getRiskEvents, getAllRecommendations, SITE_MAP, BASE_URL } from '../api/client';
import { estimateReserveConfidence } from '../lib/metrics';

function toNumericSiteId(id) {
  return SITE_MAP[id] ?? Number(id);
}

const ENDPOINT_LABELS = {
  sites: 'sites',
  riskEvents: 'risk events',
  recommendations: 'recommendations',
};

function confidenceVariant(value) {
  if (value >= 0.75) return 'confirmed';
  if (value >= 0.55) return 'warning';
  return 'critical';
}

export default function Reports() {
  const [sites, setSites] = useState([]);
  const [riskEvents, setRiskEvents] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [status, setStatus] = useState('loading');
  const [failedEndpoints, setFailedEndpoints] = useState([]);
  const [exporting, setExporting] = useState(false);
  const reportRef = useRef(null);
  const generatedAt = useMemo(() => new Date(), []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [sitesResult, riskResult, recResult] = await Promise.allSettled([
        getSites(),
        getRiskEvents(),
        getAllRecommendations(),
      ]);
      if (cancelled) return;

      const failed = [];
      if (sitesResult.status === 'fulfilled') setSites(sitesResult.value || []);
      else failed.push(ENDPOINT_LABELS.sites);

      if (riskResult.status === 'fulfilled') setRiskEvents(riskResult.value || []);
      else failed.push(ENDPOINT_LABELS.riskEvents);

      if (recResult.status === 'fulfilled') setRecommendations(recResult.value || []);
      else failed.push(ENDPOINT_LABELS.recommendations);

      setFailedEndpoints(failed);
      setStatus(failed.length === 3 ? 'error' : 'ready');
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const siteSummaries = useMemo(() => {
    return sites.map((site) => {
      const numericId = toNumericSiteId(site.id);
      const siteRisks = riskEvents.filter((e) => toNumericSiteId(e.site_id) === numericId);
      const activeRiskCount = siteRisks.filter((e) => e.resolved === false).length;
      const siteRiskIds = new Set(siteRisks.map((e) => e.id));
      const resolvedRiskIds = new Set(siteRisks.filter((e) => e.resolved === true).map((e) => e.id));
      const confidence = estimateReserveConfidence(site);

      const siteRecommendations = recommendations
        .filter((r) => siteRiskIds.has(r.risk_event_id))
        .map((r) => ({
          riskEventId: r.risk_event_id,
          trigger: r.trigger,
          optionCount: r.options?.length ?? 0,
          resolved: resolvedRiskIds.has(r.risk_event_id),
        }));

      return {
        id: site.id,
        name: site.name,
        confidence,
        activeRiskCount,
        recommendations: siteRecommendations,
        recCount: siteRecommendations.filter((r) => r.resolved).length,
      };
    });
  }, [sites, riskEvents, recommendations]);

  const totals = useMemo(() => {
    return {
      siteCount: siteSummaries.length,
      activeRiskCount: siteSummaries.reduce((sum, s) => sum + s.activeRiskCount, 0),
      resolvedRecCount: siteSummaries.reduce((sum, s) => sum + s.recCount, 0),
      avgConfidence: siteSummaries.length
        ? siteSummaries.reduce((sum, s) => sum + s.confidence, 0) / siteSummaries.length
        : 0,
    };
  }, [siteSummaries]);

  const kpiValue = (value) => (status === 'ready' ? value : '—');

  async function handleExportPdf() {
    const node = reportRef.current;
    if (!node || exporting) return;

    setExporting(true);
    try {
      const canvas = await html2canvas(node, { scale: 2, backgroundColor: '#ffffff' });
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = pageWidth;
      const pageHeightInCanvasPx = (pageHeight * canvas.width) / imgWidth;

      let renderedHeight = 0;
      let pageIndex = 0;

      while (renderedHeight < canvas.height) {
        const sliceHeight = Math.min(pageHeightInCanvasPx, canvas.height - renderedHeight);
        const pageCanvas = document.createElement('canvas');
        pageCanvas.width = canvas.width;
        pageCanvas.height = sliceHeight;
        pageCanvas
          .getContext('2d')
          .drawImage(canvas, 0, renderedHeight, canvas.width, sliceHeight, 0, 0, canvas.width, sliceHeight);

        const sliceImgHeight = (sliceHeight * imgWidth) / canvas.width;
        if (pageIndex > 0) pdf.addPage();
        pdf.addImage(pageCanvas.toDataURL('image/png'), 'PNG', 0, 0, imgWidth, sliceImgHeight);

        renderedHeight += sliceHeight;
        pageIndex += 1;
      }

      pdf.save(`oresight-reserve-report-${generatedAt.toISOString().slice(0, 10)}.pdf`);
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="page-container flex flex-col gap-6">
      {/* Page Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap mb-2">
        <div>
          <h1 className="page-title">Reports &amp; Executive Export</h1>
          <p className="page-subtitle">Aggregated reserve intelligence and audit sheets across all sites, generated on demand.</p>
        </div>
        <Button variant="primary" onClick={handleExportPdf} disabled={exporting || status === 'loading'}>
          <Download size={15} />
          <span>{exporting ? 'Exporting…' : 'Export as PDF'}</span>
        </Button>
      </div>

      {failedEndpoints.length > 0 && (
        <InlineError
          message={`Unable to reach ${failedEndpoints.join(', ')} at ${BASE_URL} — this report may be incomplete.`}
        />
      )}

      {/* Printable Report Canvas */}
      <div ref={reportRef} className="flex flex-col gap-8 bg-[var(--bg-primary)] p-4 sm:p-6">
        {/* Report Header */}
        <div className="flex items-center justify-between border-b border-[var(--divider)] pb-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--accent-primary)] text-white">
              <FileBarChart size={20} strokeWidth={2.25} />
            </div>
            <div>
              <div className="text-base font-semibold text-[var(--text-primary)]">
                OreSight — MOIL Reserve Intelligence
              </div>
              <div className="text-xs text-[var(--text-muted)]">
                Reserve &amp; Risk Summary Report
              </div>
            </div>
          </div>
          <div className="text-right text-xs text-[var(--text-muted)]">
            <div className="font-semibold text-[var(--text-primary)]">Generated</div>
            <div>{generatedAt.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</div>
          </div>
        </div>

        {/* Totals Stacked KPI Row */}
        {status === 'loading' ? (
          <SkeletonKPIRow count={4} />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <KPIStat
              icon={Gauge}
              value={kpiValue(`${(totals.avgConfidence * 100).toFixed(1)}%`)}
              label="Avg Reserve Confidence"
            />
            <KPIStat
              icon={ShieldAlert}
              value={kpiValue(String(totals.activeRiskCount).padStart(2, '0'))}
              label="Active Risk Events"
            />
            <KPIStat
              icon={ClipboardCheck}
              value={kpiValue(String(totals.resolvedRecCount).padStart(2, '0'))}
              label="Resolved Actions"
            />
            <KPIStat
              icon={FileBarChart}
              value={kpiValue(String(totals.siteCount).padStart(2, '0'))}
              label="Sites Covered"
            />
          </div>
        )}

        <SectionDivider label="SITE-BY-SITE AUDIT" />

        {/* Per-site sections */}
        <div className="space-y-6">
          {status === 'loading' && (
            <div className="space-y-4">
              <SkeletonCard />
              <SkeletonCard />
            </div>
          )}

          {status !== 'loading' && siteSummaries.length === 0 && (
            <EmptyState
              icon={FileQuestion}
              title="No sites reported"
              message="No site data is available for this report yet."
              tone="neutral"
            />
          )}

          {siteSummaries.map((site) => (
            <div key={site.id} className="bg-[var(--bg-elevated)]/50 rounded-xl p-5 border border-[var(--divider)]">
              <div className="flex items-center justify-between pb-3 mb-4 border-b border-[var(--divider)]">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">{site.name}</h3>
                <Badge variant={confidenceVariant(site.confidence)}>
                  {(site.confidence * 100).toFixed(0)}% Confidence
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-6 text-xs mb-4">
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">Active Risks</div>
                  <div className="text-xl font-semibold text-[var(--text-primary)] mt-0.5">
                    {String(site.activeRiskCount).padStart(2, '0')}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Resolved Mitigations
                  </div>
                  <div className="text-xl font-semibold text-[var(--text-primary)] mt-0.5">
                    {String(site.recCount).padStart(2, '0')} / {String(site.recommendations.length).padStart(2, '0')}
                  </div>
                </div>
              </div>

              {site.recommendations.length > 0 && (
                <div className="space-y-2 pt-3 border-t border-[var(--divider)]">
                  {site.recommendations.map((rec, idx) => (
                    <div
                      key={rec.riskEventId ?? idx}
                      className="flex items-center justify-between gap-3 text-xs p-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--divider)]"
                    >
                      <span className="text-[var(--text-primary)]">
                        {rec.trigger}
                        <span className="text-[var(--text-muted)]">
                          {' '}
                          ({rec.optionCount} option{rec.optionCount === 1 ? '' : 's'})
                        </span>
                      </span>
                      <Badge variant={rec.resolved ? 'confirmed' : 'unconfirmed'}>
                        {rec.resolved ? 'Resolved' : 'Open'}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


