import { useEffect, useMemo, useRef, useState } from 'react'
import { Download, FileBarChart, AlertCircle, Gauge, ShieldAlert, ClipboardCheck } from 'lucide-react'
import jsPDF from 'jspdf'
import html2canvas from 'html2canvas'
import Card from '../components/Card'
import KPIStat from '../components/KPIStat'
import Badge from '../components/Badge'
import Button from '../components/Button'
import { getSites, getRiskEvents, getRecommendations } from '../api/client'
import { estimateReserveConfidence } from '../lib/metrics'

const ENDPOINT_LABELS = {
  sites: 'sites',
  riskEvents: 'risk events',
  recommendations: 'recommendations',
}

function confidenceVariant(value) {
  if (value >= 0.75) return 'success'
  if (value >= 0.55) return 'warning'
  return 'danger'
}

function isRecommendationActioned(rec) {
  const status = (rec.status || '').toLowerCase()
  return rec.actioned === true || ['actioned', 'completed', 'implemented', 'resolved'].includes(status)
}

function recommendationSiteId(rec) {
  return rec.site_id ?? rec.siteId ?? null
}

export default function Reports() {
  const [sites, setSites] = useState([])
  const [riskEvents, setRiskEvents] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [status, setStatus] = useState('loading') // 'loading' | 'ready' | 'error'
  const [failedEndpoints, setFailedEndpoints] = useState([])
  const [exporting, setExporting] = useState(false)
  const reportRef = useRef(null)
  const generatedAt = useMemo(() => new Date(), [])

  useEffect(() => {
    let cancelled = false

    async function load() {
      const [sitesResult, riskResult, recResult] = await Promise.allSettled([
        getSites(),
        getRiskEvents(),
        getRecommendations(),
      ])
      if (cancelled) return

      const failed = []
      if (sitesResult.status === 'fulfilled') setSites(sitesResult.value)
      else failed.push(ENDPOINT_LABELS.sites)

      if (riskResult.status === 'fulfilled') setRiskEvents(riskResult.value)
      else failed.push(ENDPOINT_LABELS.riskEvents)

      if (recResult.status === 'fulfilled') setRecommendations(recResult.value)
      else failed.push(ENDPOINT_LABELS.recommendations)

      setFailedEndpoints(failed)
      setStatus(sitesResult.status === 'fulfilled' ? 'ready' : 'error')
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  const siteSummaries = useMemo(() => {
    return sites.map((site) => {
      const siteId = site.id ?? site.site_id
      const activeRisks = riskEvents.filter((e) => e.site_id === siteId && e.resolved === false)
      const siteRecommendations = recommendations.filter((r) => recommendationSiteId(r) === siteId)
      const actionedRecommendations = siteRecommendations.filter(isRecommendationActioned)

      return {
        id: siteId,
        name: site.name || siteId || 'Unnamed Site',
        confidence: estimateReserveConfidence(site),
        activeRiskCount: activeRisks.length,
        recommendations: siteRecommendations,
        actionedCount: actionedRecommendations.length,
      }
    })
  }, [sites, riskEvents, recommendations])

  const totals = useMemo(() => {
    return {
      siteCount: siteSummaries.length,
      activeRiskCount: siteSummaries.reduce((sum, s) => sum + s.activeRiskCount, 0),
      actionedCount: siteSummaries.reduce((sum, s) => sum + s.actionedCount, 0),
      avgConfidence: siteSummaries.length
        ? siteSummaries.reduce((sum, s) => sum + s.confidence, 0) / siteSummaries.length
        : 0,
    }
  }, [siteSummaries])

  const kpiValue = (value) => (status === 'ready' ? value : '—')

  async function handleExportPdf() {
    const node = reportRef.current
    if (!node) return

    setExporting(true)
    try {
      const canvas = await html2canvas(node, { scale: 2, backgroundColor: '#ffffff' })
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' })
      const pageWidth = pdf.internal.pageSize.getWidth()
      const pageHeight = pdf.internal.pageSize.getHeight()
      const imgWidth = pageWidth
      const pageHeightInCanvasPx = (pageHeight * canvas.width) / imgWidth

      let renderedHeight = 0
      let pageIndex = 0

      while (renderedHeight < canvas.height) {
        const sliceHeight = Math.min(pageHeightInCanvasPx, canvas.height - renderedHeight)
        const pageCanvas = document.createElement('canvas')
        pageCanvas.width = canvas.width
        pageCanvas.height = sliceHeight
        pageCanvas
          .getContext('2d')
          .drawImage(canvas, 0, renderedHeight, canvas.width, sliceHeight, 0, 0, canvas.width, sliceHeight)

        const sliceImgHeight = (sliceHeight * imgWidth) / canvas.width
        if (pageIndex > 0) pdf.addPage()
        pdf.addImage(pageCanvas.toDataURL('image/png'), 'PNG', 0, 0, imgWidth, sliceImgHeight)

        renderedHeight += sliceHeight
        pageIndex += 1
      }

      pdf.save(`oresight-reserve-report-${generatedAt.toISOString().slice(0, 10)}.pdf`)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-heading text-lg font-semibold text-navy">Reserve &amp; Risk Summary</h2>
          <p className="mt-1 text-sm text-slate-500">Aggregated across all sites, generated on demand.</p>
        </div>
        <Button variant="primary" onClick={handleExportPdf} disabled={exporting || status === 'loading'}>
          <Download size={16} />
          {exporting ? 'Exporting…' : 'Export as PDF'}
        </Button>
      </div>

      {failedEndpoints.length > 0 && (
        <div className="flex items-center gap-2 rounded-sm border border-orange/30 bg-orange/5 px-4 py-3 text-xs text-orange">
          <AlertCircle size={14} className="shrink-0" />
          Unable to reach {failedEndpoints.join(', ')} at http://localhost:8000 — this report may be incomplete.
        </div>
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
              <div className="mt-1 text-xs uppercase tracking-wide text-slate-500">
                Reserve &amp; Risk Summary Report
              </div>
            </div>
          </div>
          <div className="text-right text-xs text-slate-500">
            <div className="font-semibold text-navy">Generated</div>
            <div>{generatedAt.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</div>
          </div>
        </div>

        {/* Totals row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <KPIStat
            icon={Gauge}
            value={kpiValue(`${(totals.avgConfidence * 100).toFixed(1)}%`)}
            label="Avg Reserve Confidence"
            accent="teal"
          />
          <KPIStat
            icon={ShieldAlert}
            value={kpiValue(String(totals.activeRiskCount).padStart(2, '0'))}
            label="Active Risk Events"
            accent="orange"
          />
          <KPIStat
            icon={ClipboardCheck}
            value={kpiValue(String(totals.actionedCount).padStart(2, '0'))}
            label="Actioned Recommendations"
            accent="navy"
          />
          <KPIStat
            icon={FileBarChart}
            value={kpiValue(String(totals.siteCount).padStart(2, '0'))}
            label="Sites Covered"
            accent="teal"
          />
        </div>

        {/* Per-site sections */}
        <div className="flex flex-col gap-4">
          {status === 'loading' && <Card className="text-sm text-slate-500">Loading site summaries…</Card>}

          {status !== 'loading' && siteSummaries.length === 0 && (
            <Card className="text-sm text-slate-500">No sites reported.</Card>
          )}

          {siteSummaries.map((site) => (
            <Card key={site.id} padded={false}>
              <div className="flex items-center justify-between p-5 pb-4 border-b border-border">
                <h3 className="font-heading text-[15px] font-semibold text-navy">{site.name}</h3>
                <Badge variant={confidenceVariant(site.confidence)}>
                  {(site.confidence * 100).toFixed(0)}% Confidence
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-5 pb-3 text-sm">
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Active Risks</div>
                  <div className="mt-1 font-heading text-xl font-semibold text-navy">
                    {String(site.activeRiskCount).padStart(2, '0')}
                  </div>
                </div>
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    Recommendations Actioned
                  </div>
                  <div className="mt-1 font-heading text-xl font-semibold text-navy">
                    {site.actionedCount} / {site.recommendations.length}
                  </div>
                </div>
              </div>

              {site.recommendations.length > 0 && (
                <div className="flex flex-col gap-2 p-5 pt-1">
                  {site.recommendations.map((rec, idx) => (
                    <div
                      key={rec.id ?? idx}
                      className="flex items-center justify-between gap-3 rounded-sm border border-border px-3 py-2"
                    >
                      <span className="text-xs text-navy">{rec.title || rec.description || 'Recommendation'}</span>
                      <Badge variant={isRecommendationActioned(rec) ? 'success' : 'neutral'}>
                        {isRecommendationActioned(rec) ? 'Actioned' : 'Pending'}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
