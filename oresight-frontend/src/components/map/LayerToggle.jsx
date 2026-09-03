import { useState } from 'react'
import { Layers } from 'lucide-react'
import Card from '../Card'
import { MAP_LAYERS } from '../../lib/map'

export default function LayerToggle({
  prospectivityVisible,
  onProspectivityChange,
  spectralVisible = false,
  onSpectralChange,
  lineamentVisible = false,
  onLineamentChange,
  droneVisible = false,
  onDroneChange,
  ndviVisible = false,
  onNdviChange,
}) {
  const [enabled, setEnabled] = useState(() =>
    Object.fromEntries(
      MAP_LAYERS.filter(
        (layer) => !['prospectivity', 'spectral', 'lineament', 'dsm', 'ndvi'].includes(layer.id)
      ).map((layer) => [layer.id, false])
    )
  )

  function toggleLayer(id) {
    setEnabled((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  function isLayerChecked(id) {
    if (id === 'prospectivity') return Boolean(prospectivityVisible)
    if (id === 'spectral') return Boolean(spectralVisible)
    if (id === 'lineament') return Boolean(lineamentVisible)
    if (id === 'dsm') return Boolean(droneVisible)
    if (id === 'ndvi') return Boolean(ndviVisible)
    return Boolean(enabled[id])
  }

  function handleToggle(id) {
    if (id === 'prospectivity' && onProspectivityChange) {
      onProspectivityChange(!prospectivityVisible)
      return
    }
    if (id === 'spectral' && onSpectralChange) {
      onSpectralChange(!spectralVisible)
      return
    }
    if (id === 'lineament' && onLineamentChange) {
      onLineamentChange(!lineamentVisible)
      return
    }
    if (id === 'dsm' && onDroneChange) {
      onDroneChange(!droneVisible)
      return
    }
    if (id === 'ndvi' && onNdviChange) {
      onNdviChange(!ndviVisible)
      return
    }
    toggleLayer(id)
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-white">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-center gap-2">
          <Layers size={17} className="text-teal" strokeWidth={2} />
          <h2 className="font-heading text-[15px] font-semibold text-navy">Map Layers</h2>
        </div>
        <p className="mt-1 text-xs text-slate-500">Toggle overlay layers on the operational map</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <Card className="space-y-1 p-0" noPadding>
          {MAP_LAYERS.map((layer) => (
            <label
              key={layer.id}
              className="flex cursor-pointer items-center gap-3 border-b border-border px-4 py-3 last:border-b-0 transition-colors duration-150 hover:bg-bg/60"
            >
              <input
                type="checkbox"
                checked={isLayerChecked(layer.id)}
                onChange={() => handleToggle(layer.id)}
                className="h-4 w-4 rounded-sm border-border text-orange focus:ring-orange/40"
              />
              <span className="text-sm font-medium text-navy">{layer.label}</span>
            </label>
          ))}
        </Card>
      </div>
    </aside>
  )
}
