import { useEffect, useMemo, useState } from 'react'
import { getSites } from '../api/client'
import LayerToggle from '../components/map/LayerToggle'
import MineMap from '../components/map/MineMap'
import ZoneDetailPanel from '../components/map/ZoneDetailPanel'

export default function MapPage() {
  const [prospectivityVisible, setProspectivityVisible] = useState(false)
  const [spectralVisible, setSpectralVisible] = useState(false)
  const [droneVisible, setDroneVisible] = useState(false)
  const [ndviVisible, setNdviVisible] = useState(false)
  const [selectedWeek, setSelectedWeek] = useState(4)
  const [selectedZone, setSelectedZone] = useState(null)
  const [sites, setSites] = useState([])

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

  return (
    <div className="-m-6 flex h-[calc(100vh-4rem)] overflow-hidden">
      <LayerToggle
        prospectivityVisible={prospectivityVisible}
        onProspectivityChange={setProspectivityVisible}
        spectralVisible={spectralVisible}
        onSpectralChange={setSpectralVisible}
        droneVisible={droneVisible}
        onDroneChange={setDroneVisible}
        ndviVisible={ndviVisible}
        onNdviChange={setNdviVisible}
      />
      <div className="relative min-h-0 flex-1 h-full">
        <MineMap
          prospectivityVisible={prospectivityVisible}
          spectralVisible={spectralVisible}
          droneVisible={droneVisible}
          ndviVisible={ndviVisible}
          selectedWeek={selectedWeek}
          onWeekChange={setSelectedWeek}
          onZoneSelect={setSelectedZone}
        />
        <ZoneDetailPanel
          zone={selectedZone}
          siteName={selectedSiteName}
          onClose={() => setSelectedZone(null)}
        />
      </div>
    </div>
  )
}
