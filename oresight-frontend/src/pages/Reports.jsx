import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, FileBarChart, Gauge, ShieldAlert, ClipboardCheck, FileQuestion } from 'lucide-react';
import jsPDF from 'jspdf';
// html2canvas 1.4.x can't parse the oklab()/oklch() colors Tailwind v4
// emits, and throws instead of rendering — html2canvas-pro is a drop-in
// fork that adds support for the modern CSS color syntax.
import html2canvas from 'html2canvas-pro';
import { Card, KPIStat, Badge, Button, SkeletonKPIRow, SkeletonCard, EmptyState, InlineError } from '../components';
import { getSites, getRiskEvents, getAllRecommendations, SITE_MAP } from '../api/client';

// Mock getSites() returns string site ids ('balaghat'); mock getRiskEvents()
// returns numeric ones (1). Compare through SITE_MAP's numeric ids so both
// shapes match — a strict === here always misses and reports 0 risks.
function toNumericSiteId(id) {
  return SITE_MAP[id] ?? Number(id);
}
import { estimateReserveConfidence } from '../lib/metrics';

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
  const [status, setStatus] = useState('loading'); // 'loading' | 'ready' | 'error'
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
      if (sitesResult.status === 'fulfilled') setSites(sitesResult.value);
      else failed.push(ENDPOINT_LABELS.sites);

      if (riskResult.status === 'fulfilled') setRiskEvents(riskResult.value);
      else failed.push(ENDPOINT_LABELS.riskEvents);

      if (recResult.status === 'fulfilled') setRecommendations(recResult.value);
      else failed.push(ENDPOINT_LABELS.recommendations);

      setFailedEndpoints(failed);
      setStatus(sitesResult.status === 'fulfilled' ? 'ready' : 'error');
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // Recommendations from the real API (RecommendationOut: {trigger,
  // risk_event_id, options: [{type, description, projected_impact,
  // confidence}]}) carry no site_id or actioned/status field directly —
  // there's no persisted "recommendation" row in the backend at all, the
  // Planner computes these on the fly. Site grouping goes through the risk
  // event they're attached to, and "actioned" is reinterpreted as "the
  // underlying risk this recommended has since been resolved" — the
  // closest real signal to what the original mock-shaped report wanted.
  const siteSummaries = useMemo(() => {
    return sites.map((site) => {
      const siteId = site.id ?? site.site_id;
      const numericSiteId = toNumericSiteId(siteId);
      const siteRiskEvents = riskEvents.filter((e) => toNumericSiteId(e.site_id) === numericSiteId);
      const activeRisks = siteRiskEvents.filter((e) => e.resolved === false);
      const siteRiskIds = new Set(siteRiskEvents.map((e) => e.id));
      const siteRecommendations = recommendations.filter((r) => siteRiskIds.has(r.risk_event_id));
      const resolvedCount = siteRecommendations.filter((r) => {
        const risk = riskEvents.find((e) => e.id === r.risk_event_id);
        return risk?.resolved === true;
      }).length;

      return {
        id: siteId,
        name: site.name || siteId || 'Unnamed Site',
        confidence: estimateReserveConfidence(site),
        activeRiskCount: activeRisks.length,
        recommendations: siteRecommendations,
        resolvedCount,
      };
    });
  }, [sites, riskEvents, recommendations]);

  const totals = useMemo(() => {
    return {
      siteCount: siteSummaries.length,
      activeRiskCount: siteSummaries.reduce((sum, s) => sum + s.activeRiskCount, 0),
      resolvedCount: siteSummaries.reduce((sum, s) => sum + s.resolvedCount, 0),
      avgConfidence: siteSummaries.length
        ? siteSummaries.reduce((sum, s) => sum + s.confidence, 0) / siteSummaries.length
        : 0,
    };
  }, [siteSummaries]);

  const kpiValue = (value) => (status === 'ready' ? value : '—');

  async function handleExportPdf() {
    const node = reportRef.current;
    if (!node) return;

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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-heading text-lg font-semibold text-navy">Reserve &amp; Risk Summary</h2>
          <p className="mt-1 text-sm text-text-secondary">Aggregated across all sites, generated on demand.</p>
        </div>
        <Button variant="primary" onClick={handleExportPdf} disabled={exporting || status === 'loading'}>
          <Download size={16} />
          {exporting ? 'Exporting…' : 'Export as PDF'}
        </Button>
      </div>

      {failedEndpoints.length > 0 && (
        <InlineError
          message={`Unable to reach ${failedEndpoints.join(', ')} at http://localhost:8000 — this report may be incomplete.`}
        />
      )}

      <div ref={reportRef} className="flex flex-col gap-6 bg-white p-8">
        {/* Report header */}
        <div className="flex items-center justify-between border-b border-border pb-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-sm bg-orange text-white">
              <FileBarChart size={20} strokeWidth={2.25} />
            </div>
            <div>
              <div className="font-heading text-lg font-semibold text-navy leading-none">
                OreSight — MOIL Reserve Intelligence
              </div>
              <div className="mt-1 text-xs uppercase tracking-wide text-text-secondary">
                Reserve &amp; Risk Summary Report
              </div>
            </div>
          </div>
          <div className="text-right text-xs text-text-secondary">
            <div className="font-semibold text-navy">Generated</div>
            <div>{generatedAt.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</div>
          </div>
        </div>

        {/* Totals row */}
        {status === 'loading' ? (
          <SkeletonKPIRow count={4} />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <KPIStat
              icon={Gauge}
              value={kpiValue(`${(totals.avgConfidence * 100).toFixed(1)}%`)}
              label="Avg Reserve Confidence"
              color="teal"
            />
            <KPIStat
              icon={ShieldAlert}
              value={kpiValue(String(totals.activeRiskCount).padStart(2, '0'))}
              label="Active Risk Events"
              color="orange"
            />
            <KPIStat
              icon={ClipboardCheck}
              value={kpiValue(String(totals.resolvedCount).padStart(2, '0'))}
              label="Recommendations on Resolved Risks"
              color="navy"
            />
            <KPIStat
              icon={FileBarChart}
              value={kpiValue(String(totals.siteCount).padStart(2, '0'))}
              label="Sites Covered"
              color="teal"
            />
          </div>
        )}

        {/* Per-site sections */}
        <div className="flex flex-col gap-4">
          {status === 'loading' && (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          )}

          {status !== 'loading' && siteSummaries.length === 0 && (
            <Card>
              <EmptyState
                icon={FileQuestion}
                title="No sites reported"
                message="No site data is available for this report yet."
                tone="neutral"
              />
            </Card>
          )}

          {siteSummaries.map((site) => (
            <Card key={site.id} noPadding>
              <div className="flex items-center justify-between p-5 pb-4 border-b border-border">
                <h3 className="font-heading text-[15px] font-semibold text-navy">{site.name}</h3>
                <Badge variant={confidenceVariant(site.confidence)}>
                  {(site.confidence * 100).toFixed(0)}% Confidence
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-5 pb-3 text-sm">
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-text-secondary">Active Risks</div>
                  <div className="mt-1 font-heading text-xl font-semibold text-navy">
                    {String(site.activeRiskCount).padStart(2, '0')}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-text-secondary">
                    Recommendations on Resolved Risks
                  </div>
                  <div className="mt-1 font-heading text-xl font-semibold text-navy">
                    {site.resolvedCount} / {site.recommendations.length}
                  </div>
                </div>
              </div>

              {site.recommendations.length > 0 && (
                <div className="flex flex-col gap-2 p-5 pt-1">
                  {site.recommendations.map((rec, idx) => {
                    const risk = riskEvents.find((e) => e.id === rec.risk_event_id);
                    const resolved = risk?.resolved === true;
                    return (
                      <div
                        key={rec.risk_event_id ?? idx}
                        className="flex items-center justify-between gap-3 rounded-sm border border-border px-3 py-2"
                      >
                        <span className="text-xs text-navy">
                          {rec.trigger}
                          <span className="text-text-muted"> ({rec.options?.length ?? 0} option{rec.options?.length === 1 ? '' : 's'})</span>
                        </span>
                        <Badge variant={resolved ? 'confirmed' : 'unconfirmed'}>
                          {resolved ? 'Resolved' : 'Open'}
                        </Badge>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
