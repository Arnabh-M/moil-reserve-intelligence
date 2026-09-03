import { useEffect, useMemo, useState } from 'react'
import { MapPin } from 'lucide-react'
import { getSites } from '../api/client'
import { SAMPLE_SITES } from '../lib/map'
import LayerToggle from '../components/map/LayerToggle'
import MineMap from '../components/map/MineMap'
import ZoneDetailPanel from '../components/map/ZoneDetailPanel'
import CrossSectionDrawer from '../components/map/CrossSectionDrawer'

export default function MapPage() {
  const [prospectivityVisible, setProspectivityVisible] = useState(false)
  const [spectralVisible, setSpectralVisible] = useState(false)
  const [droneVisible, setDroneVisible] = useState(false)
  const [ndviVisible, setNdviVisible] = useState(false)
  const [lineamentVisible, setLineamentVisible] = useState(false)

  const [selectedWeek, setSelectedWeek] = useState(4)
  const [selectedZone, setSelectedZone] = useState(null)
  const [sites, setSites] = useState([])

  // P4 Day 4: Fly-To navigation state
  const [flyToTarget, setFlyToTarget] = useState(null)
  const [selectedSiteIdForFlyTo, setSelectedSiteIdForFlyTo] = useState('')

  // P4 Day 4: Cross-section tool & drawer state
  const [crossSectionActive, setCrossSectionActive] = useState(false)
  const [crossSectionPoint, setCrossSectionPoint] = useState(null)
  const [crossSectionDrawerOpen, setCrossSectionDrawerOpen] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function loadSites() {
      try {
        const data = await getSites()
        if (!cancelled) setSites(data)
      } catch {
        // Site names are optional for the zone panel fallback.
      }
    }

    loadSites()
    return () => {
      cancelled = true
    }
  }, [])

  const siteNameById = useMemo(
    () => Object.fromEntries(sites.map((site) => [site.id, site.name])),
    [sites]
  )

  const selectedSiteName = useMemo(() => {
    if (!selectedZone) return null
    const siteId = selectedZone.site_id
    if (siteNameById[siteId]) return siteNameById[siteId]
    if (siteId === 'balaghat' || siteId === 1) return 'Balaghat Mine'
    if (siteId === 'nagpur' || siteId === 2) return 'Nagpur Mine'
    if (siteId === 'bhandara' || siteId === 3) return 'Bhandara Mine'
    return siteId ? String(siteId) : null
  }, [selectedZone, siteNameById])

  // Handle site selection from dropdown/search to smoothly flyTo
  function handleSiteSelect(siteId) {
    setSelectedSiteIdForFlyTo(siteId)
    if (!siteId) return
    const site = SAMPLE_SITES.find((s) => s.id === siteId)
    if (site) {
      setFlyToTarget({
        id: site.id,
        name: site.name,
        latitude: site.latitude,
        longitude: site.longitude,
        zoom: 11,
      })
    }
  }

  // Handle map cross-section point click
  function handleSelectCrossSectionPoint(point) {
    setCrossSectionPoint(point)
    setCrossSectionDrawerOpen(true)
  }

  // Handle Inspect Cross-Section action from ZoneDetailPanel
  function handleInspectZoneCrossSection() {
    if (!selectedZone) return
    // Approximate or direct coordinate for the zone
    const lat = selectedZone.latitude ?? (selectedZone.site_id === 'balaghat' ? 21.8 : selectedZone.site_id === 'nagpur' ? 21.1 : 21.2)
    const lng = selectedZone.longitude ?? (selectedZone.site_id === 'balaghat' ? 80.2 : selectedZone.site_id === 'nagpur' ? 79.1 : 79.6)
    setCrossSectionPoint({
      lat,
      lng,
      zoneName: selectedZone.zone_name,
      site_id: selectedZone.site_id,
      siteName: selectedSiteName,
    })
    setCrossSectionDrawerOpen(true)
  }

  return (
    <div className="-m-6 flex h-[calc(100vh-4rem)] overflow-hidden relative">
      {/* Sidebar Layer Toggle */}
      <LayerToggle
        prospectivityVisible={prospectivityVisible}
        onProspectivityChange={setProspectivityVisible}
        spectralVisible={spectralVisible}
        onSpectralChange={setSpectralVisible}
        lineamentVisible={lineamentVisible}
        onLineamentChange={setLineamentVisible}
        droneVisible={droneVisible}
        onDroneChange={setDroneVisible}
        ndviVisible={ndviVisible}
        onNdviChange={setNdviVisible}
      />

      <div className="relative min-h-0 flex-1 h-full">
        {/* Compact Site Selector / Fly-To Navigation Header */}
        <div className="absolute top-4 right-4 z-20 flex items-center gap-2 bg-white/95 border border-border px-3 py-1.5 rounded-xl shadow-lg backdrop-blur-md">
          <MapPin size={14} className="text-teal shrink-0" />
          <select
            aria-label="Jump to Mine Site"
            value={selectedSiteIdForFlyTo}
            onChange={(e) => handleSiteSelect(e.target.value)}
            className="bg-transparent text-xs font-semibold text-navy outline-none cursor-pointer pr-1"
          >
            <option value="">Jump to Mine Site…</option>
            {SAMPLE_SITES.map((site) => (
              <option key={site.id} value={site.id}>
                {site.name} Mine ({site.latitude.toFixed(1)}°N, {site.longitude.toFixed(1)}°E)
              </option>
            ))}
          </select>
        </div>

        {/* Map Engine */}
        <MineMap
          prospectivityVisible={prospectivityVisible}
          spectralVisible={spectralVisible}
          droneVisible={droneVisible}
          ndviVisible={ndviVisible}
          lineamentVisible={lineamentVisible}
          selectedWeek={selectedWeek}
          onWeekChange={setSelectedWeek}
          onZoneSelect={setSelectedZone}
          flyToTarget={flyToTarget}
          crossSectionActive={crossSectionActive}
          onToggleCrossSection={() => setCrossSectionActive(!crossSectionActive)}
          onSelectCrossSectionPoint={handleSelectCrossSectionPoint}
          crossSectionPoint={crossSectionPoint}
        />

        {/* Right Feature Detail Panel */}
        <ZoneDetailPanel
          zone={selectedZone}
          siteName={selectedSiteName}
          onClose={() => setSelectedZone(null)}
          onInspectCrossSection={handleInspectZoneCrossSection}
        />

        {/* Bottom Cross-Section Profile Drawer (Day 4) */}
        <CrossSectionDrawer
          isOpen={crossSectionDrawerOpen}
          onClose={() => {
            setCrossSectionDrawerOpen(false)
            setCrossSectionPoint(null)
            setCrossSectionActive(false)
          }}
          point={crossSectionPoint}
        />
      </div>
    </div>
  )
}
