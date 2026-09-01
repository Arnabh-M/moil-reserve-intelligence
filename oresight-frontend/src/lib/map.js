// Map configuration for the MOIL manganese belt (P4 Day 1).

export const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'

export const MAP_ZOOM = 7

// Centered on the Balaghat / Nagpur / Bhandara belt
export const MAP_CENTER = {
  latitude: 21.367,
  longitude: 79.633,
}

export const SAMPLE_SITES = [
  { id: 'balaghat', name: 'Balaghat', latitude: 21.8, longitude: 80.2 },
  { id: 'nagpur', name: 'Nagpur', latitude: 21.1, longitude: 79.1 },
  { id: 'bhandara', name: 'Bhandara', latitude: 21.2, longitude: 79.6 },
]

export const MAP_LAYERS = [
  { id: 'prospectivity', label: 'Prospectivity Heatmap' },
  { id: 'spectral', label: 'Spectral Alteration' },
  { id: 'lineament', label: 'Structural Lineament' },
  { id: 'dsm', label: 'Drone DSM' },
]

export const RESERVE_ZONES_SOURCE_ID = 'reserve-zones'
export const RESERVE_ZONES_FILL_LAYER_ID = 'reserve-zones-fill'

export const CONFIDENCE_COLOR_RAMP = {
  low: '#c0392b',
  mid: '#e0793a',
  high: '#3f8f5f',
}

export const RESERVE_ZONE_FILL_PAINT = {
  'fill-color': [
    'interpolate',
    ['linear'],
    ['get', 'confidence_score'],
    0,
    CONFIDENCE_COLOR_RAMP.low,
    0.5,
    CONFIDENCE_COLOR_RAMP.mid,
    1,
    CONFIDENCE_COLOR_RAMP.high,
  ],
  'fill-opacity': 0.65,
}
