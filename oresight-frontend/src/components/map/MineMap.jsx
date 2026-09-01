import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import Map, { Layer, Marker, Popup, Source } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { getReserveZones } from '../../api/client'
import {
  MAP_CENTER,
  MAP_STYLE,
  MAP_ZOOM,
  RESERVE_ZONES_FILL_LAYER_ID,
  RESERVE_ZONES_SOURCE_ID,
  RESERVE_ZONE_FILL_PAINT,
  SAMPLE_SITES,
} from '../../lib/map'
import ConfidenceLegend from './ConfidenceLegend'

export default function MineMap({ prospectivityVisible, onZoneSelect }) {
  const [selectedSiteId, setSelectedSiteId] = useState(null)
  const [reserveZones, setReserveZones] = useState(null)
  const [zonesStatus, setZonesStatus] = useState('loading')

  const selectedSite = SAMPLE_SITES.find((site) => site.id === selectedSiteId)

  useEffect(() => {
    let cancelled = false

    async function loadReserveZones() {
      try {
        const data = await getReserveZones()
        if (!cancelled) {
          setReserveZones(data)
          setZonesStatus('ready')
        }
      } catch {
        if (!cancelled) setZonesStatus('error')
      }
    }

    loadReserveZones()
    return () => {
      cancelled = true
    }
  }, [])

  function handleMapClick(event) {
    const zoneFeature = event.features?.find(
      (feature) => feature.layer.id === RESERVE_ZONES_FILL_LAYER_ID
    )

    if (zoneFeature && prospectivityVisible) {
      onZoneSelect(zoneFeature.properties)
      setSelectedSiteId(null)
      return
    }

    setSelectedSiteId(null)
    onZoneSelect(null)
  }

  function handleMouseMove(event) {
    const canvas = event.target.getCanvas()
    const overZone =
      prospectivityVisible &&
      event.features?.some((feature) => feature.layer.id === RESERVE_ZONES_FILL_LAYER_ID)
    canvas.style.cursor = overZone ? 'pointer' : ''
  }

  return (
    <div className="relative h-full w-full">
      <Map
        initialViewState={{
          longitude: MAP_CENTER.longitude,
          latitude: MAP_CENTER.latitude,
          zoom: MAP_ZOOM,
        }}
        style={{ width: '100%', height: '100%' }}
        mapStyle={MAP_STYLE}
        interactiveLayerIds={
          prospectivityVisible && reserveZones ? [RESERVE_ZONES_FILL_LAYER_ID] : []
        }
        onClick={handleMapClick}
        onMouseMove={handleMouseMove}
      >
        {reserveZones && (
          <Source id={RESERVE_ZONES_SOURCE_ID} type="geojson" data={reserveZones}>
            <Layer
              id={RESERVE_ZONES_FILL_LAYER_ID}
              type="fill"
              paint={RESERVE_ZONE_FILL_PAINT}
              layout={{
                visibility: prospectivityVisible ? 'visible' : 'none',
              }}
            />
          </Source>
        )}

        {SAMPLE_SITES.map((site) => (
          <Marker
            key={site.id}
            longitude={site.longitude}
            latitude={site.latitude}
            anchor="bottom"
            onClick={(event) => {
              event.originalEvent.stopPropagation()
              setSelectedSiteId(site.id)
              onZoneSelect(null)
            }}
          >
            <button
              type="button"
              aria-label={site.name}
              className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-orange shadow-panel transition-transform hover:scale-110"
            >
              <span className="h-2 w-2 rounded-full bg-white" />
            </button>
          </Marker>
        ))}

        {selectedSite && (
          <Popup
            longitude={selectedSite.longitude}
            latitude={selectedSite.latitude}
            anchor="bottom"
            offset={[0, -12]}
            closeButton
            closeOnClick={false}
            onClose={() => setSelectedSiteId(null)}
          >
            <p className="font-heading text-sm font-semibold text-navy">{selectedSite.name}</p>
          </Popup>
        )}
      </Map>

      <ConfidenceLegend visible={prospectivityVisible} />

      {zonesStatus === 'loading' && (
        <div className="absolute left-4 top-4 z-10 flex items-center gap-2 rounded-sm border border-border bg-white px-3 py-2 text-xs text-text-secondary shadow-lg">
          <Loader2 size={14} className="shrink-0 animate-spin text-teal" />
          Loading reserve zones…
        </div>
      )}

      {zonesStatus === 'error' && (
        <div className="absolute left-4 top-4 z-10 rounded-sm border border-danger/30 bg-white px-3 py-2 text-xs text-danger shadow-lg">
          Unable to load reserve zones from the backend.
        </div>
      )}
    </div>
  )
}
