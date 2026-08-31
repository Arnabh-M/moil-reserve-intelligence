import { useState } from 'react'
import Map, { Marker, Popup } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { MAP_CENTER, MAP_STYLE, MAP_ZOOM, SAMPLE_SITES } from '../../lib/map'

export default function MineMap() {
  const [selectedSiteId, setSelectedSiteId] = useState(null)
  const selectedSite = SAMPLE_SITES.find((site) => site.id === selectedSiteId)

  return (
    <div className="relative min-h-0 flex-1">
      <Map
        initialViewState={{
          longitude: MAP_CENTER.longitude,
          latitude: MAP_CENTER.latitude,
          zoom: MAP_ZOOM,
        }}
        style={{ width: '100%', height: '100%' }}
        mapStyle={MAP_STYLE}
        onClick={() => setSelectedSiteId(null)}
      >
        {SAMPLE_SITES.map((site) => (
          <Marker
            key={site.id}
            longitude={site.longitude}
            latitude={site.latitude}
            anchor="bottom"
            onClick={(event) => {
              event.originalEvent.stopPropagation()
              setSelectedSiteId(site.id)
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
    </div>
  )
}
