// Map configuration for the MOIL manganese belt (P4 Day 1).

// THE site definition. `moil_sites.json` is a generated, byte-identical copy of
// the repo-root data/moil_sites.json that geo_utils, generate_datasets,
// app/seed_dev (the DB `sites.geom`) and the GEE/prospectivity pipelines all
// read. Regenerate all copies with `python -m scripts.build_site_aois`;
// `--check` fails if they have drifted. Nothing in the frontend should
// hardcode a site box, centre or the combined extent again.
import moilSites from './moil_sites.json'

export const MOIL_SITES = moilSites

// Muted, low-saturation basemap so semi-transparent data overlays (NDVI,
// spectral alteration, reserve confidence) stay legible against it — a
// bright/colorful basemap competes with the data layers drawn on top of it.
export const BASEMAP_STYLES = {
  light: 'https://tiles.openfreemap.org/styles/positron',
  terrain: 'https://tiles.openfreemap.org/styles/liberty',
}

export const MAP_STYLE = BASEMAP_STYLES.light

// AWS Open Data Terrain Tiles (SRTM / GMTED composite processed by Mapzen/Tilezen)
// Free, unauthenticated global elevation source with native MapLibre 'terrarium' encoding support
export const TERRAIN_DEM_SOURCE = {
  id: 'aws-terrain-dem',
  type: 'raster-dem',
  tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
  encoding: 'terrarium',
  tileSize: 256,
  maxzoom: 15,
}

// Required legal attribution strings
export const MAP_ATTRIBUTION = {
  light: '© OpenStreetMap contributors, OpenFreeMap',
  terrain: 'Map: © OpenStreetMap contributors, OpenFreeMap · Elevation: AWS Open Data (SRTM/Mapzen)',
}

export const MAP_ZOOM = 8.2

// Combined extent of the three AOIs, as [[W, S], [E, N]].
const [COMBINED_W, COMBINED_S, COMBINED_E, COMBINED_N] = MOIL_SITES.combined_bbox

// 3-Area Regional Extent — the real combined bounds of Balaghat, Nagpur and Bhandara
export const REGIONAL_BOUNDS = [
  [COMBINED_W, COMBINED_S], // Southwest [lng, lat]
  [COMBINED_E, COMBINED_N], // Northeast [lng, lat]
]

// Geographic midpoint of the 3 operational areas
export const MAP_CENTER = {
  latitude: (COMBINED_S + COMBINED_N) / 2,
  longitude: (COMBINED_W + COMBINED_E) / 2,
}

// The four corners of the combined extent, in the [NW, NE, SE, SW] order
// MapLibre image sources want. Every raster overlay is rendered over exactly
// this extent (gis/generate_tiles.py uses geo_utils.COMBINED_BBOX, which is
// the same `combined_bbox`), so they share one definition here — a raster
// whose corners disagree with its PNG shifts silently, with no error.
export const RASTER_OVERLAY_COORDINATES = [
  [COMBINED_W, COMBINED_N],
  [COMBINED_E, COMBINED_N],
  [COMBINED_E, COMBINED_S],
  [COMBINED_W, COMBINED_S],
]

// `id` matches the real numeric /sites id (stable across this deployment);
// `slug` is only for the static per-site prospectivity GeoJSON filenames
// (prospectivity/<slug>.geojson), which have no live API equivalent. These
// used to be the same string ('balaghat' etc. as `id`), disconnected from
// the numeric site_id every other API response uses -- callers had to
// dual-check both forms wherever a selected site crossed into map filtering.
//
// latitude/longitude are the AOI centre, matching `sites.centroid` in the DB;
// bounds are the AOI itself, matching `sites.geom`.
export const SAMPLE_SITES = MOIL_SITES.sites.map((site) => ({
  id: site.db_id,
  slug: site.key,
  name: site.name,
  latitude: (site.bbox.min_lat + site.bbox.max_lat) / 2,
  longitude: (site.bbox.min_lon + site.bbox.max_lon) / 2,
  bounds: [
    [site.bbox.min_lon, site.bbox.min_lat],
    [site.bbox.max_lon, site.bbox.max_lat],
  ],
}))

export const MAP_LAYERS = [
  { id: 'prospectivity', label: 'Prospectivity Heatmap' },
  { id: 'spectral', label: 'Spectral Alteration' },
  { id: 'lineament', label: 'Structural Lineament' },
  { id: 'ndvi', label: 'NDVI Time-Series' },
  { id: 'mines', label: 'MOIL Mines' },
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

// ---------------------------------------------------------------------------
// MOIL mines point layer — the actual pits each AOI was built around.
// /moil_mines.geojson is generated from data/moil_sites.json by
// `python -m scripts.build_site_aois`; do not edit it by hand.
// ---------------------------------------------------------------------------
export const MOIL_MINES_URL = '/moil_mines.geojson'
export const MOIL_MINES_SOURCE_ID = 'moil-mines'
export const MOIL_MINES_LAYER_ID = 'moil-mines-points'
export const MOIL_MINES_LABEL_LAYER_ID = 'moil-mines-labels'

// Positional confidence of each mine's coordinates. Extends the existing
// CONFIDENCE_COLOR_RAMP semantic (red = least certain, green = most) so the
// mine dots read as the same system as the reserve-zone fill.
export const MINE_CONFIDENCE_COLORS = {
  high: '#1a6b3c',
  'medium-high': CONFIDENCE_COLOR_RAMP.high,
  medium: CONFIDENCE_COLOR_RAMP.mid,
  'low-medium': '#d4923f',
  low: CONFIDENCE_COLOR_RAMP.low,
}

export const MOIL_MINES_CIRCLE_PAINT = {
  'circle-color': [
    'match',
    ['get', 'confidence'],
    'high', MINE_CONFIDENCE_COLORS.high,
    'medium-high', MINE_CONFIDENCE_COLORS['medium-high'],
    'medium', MINE_CONFIDENCE_COLORS.medium,
    'low-medium', MINE_CONFIDENCE_COLORS['low-medium'],
    'low', MINE_CONFIDENCE_COLORS.low,
    MINE_CONFIDENCE_COLORS.low,
  ],
  'circle-radius': [
    'interpolate', ['linear'], ['zoom'],
    7, ['match', ['get', 'confidence'], 'high', 4.5, 'medium-high', 4, 'medium', 3.5, 3],
    12, ['match', ['get', 'confidence'], 'high', 9, 'medium-high', 8.5, 'medium', 8, 7],
  ],
  // Lower-confidence coordinates render softer, so a dot you should not trust
  // to the metre does not look as solid as an OSM-verified pit.
  'circle-opacity': [
    'match', ['get', 'confidence'],
    'high', 1, 'medium-high', 0.95, 'medium', 0.9, 'low-medium', 0.8, 0.7,
  ],
  // Stroke carries inclusion, not confidence: a white ring means the mine is
  // inside its site's AOI, a pale dashed-looking thin ring means it was left
  // out (Gumgaon, Tirodi) and is shown for reference only.
  'circle-stroke-color': ['case', ['get', 'in_aoi'], '#ffffff', '#1a1815'],
  'circle-stroke-width': ['case', ['get', 'in_aoi'], 1.5, 1],
  'circle-stroke-opacity': ['case', ['get', 'in_aoi'], 1, 0.45],
}

export const MOIL_MINES_LABEL_LAYOUT = {
  'text-field': ['get', 'name'],
  'text-size': ['interpolate', ['linear'], ['zoom'], 8, 10, 12, 13],
  'text-offset': [0, 1.1],
  'text-anchor': 'top',
  'text-allow-overlap': false,
}

export const MOIL_MINES_LABEL_PAINT = {
  'text-color': '#1a1815',
  'text-halo-color': 'rgba(255,255,255,0.9)',
  'text-halo-width': 1.4,
  'text-opacity': ['case', ['get', 'in_aoi'], 1, 0.6],
}

// Below this zoom the belt-wide view puts the Nagpur cluster's three mines
// within a few pixels of each other; labels are unreadable and the dots merge.
export const MOIL_MINES_MIN_ZOOM = 7

// P4 Day 4: Structural Lineament Layer Configuration
export const STRUCTURAL_LINES_SOURCE_ID = 'structural-lines'
export const STRUCTURAL_LINES_LAYER_ID = 'structural-lines-layer'

export const STRUCTURAL_LINE_COLORS = {
  fault: '#ef4444',       // vibrant red
  shear_zone: '#f59e0b',  // warm amber
  fold_axis: '#8b5cf6',   // deep violet
  default: '#3b82f6',     // operational blue
}

// Structural lineaments span the whole mining belt, so at a zoomed-out view
// their short segments render as an illegible scatter of tiny marks. Fade
// them in and thicken them as the user zooms in, rather than showing
// everything at once regardless of scale.
export const STRUCTURAL_LINE_PAINT = {
  'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1, 10, 1.75, 13, 3],
  'line-color': [
    'match',
    ['get', 'structure_type'],
    'fault', STRUCTURAL_LINE_COLORS.fault,
    'shear_zone', STRUCTURAL_LINE_COLORS.shear_zone,
    'fold_axis', STRUCTURAL_LINE_COLORS.fold_axis,
    STRUCTURAL_LINE_COLORS.default,
  ],
  'line-opacity': ['interpolate', ['linear'], ['zoom'], 7.5, 0, 9, 0.9],
}

// Below this zoom the lineament layer is fully faded out (see line-opacity
// above); skipping rendering entirely below it avoids paying for a layer
// nobody can read yet.
export const STRUCTURAL_LINES_MIN_ZOOM = 7.5

// P4 Day 4: Site Clustering Configuration
export const SITES_SOURCE_ID = 'sites-source'
export const CLUSTERS_LAYER_ID = 'clusters'
export const CLUSTER_COUNT_LAYER_ID = 'cluster-count'
export const UNCLUSTERED_POINT_LAYER_ID = 'unclustered-point'
export const SITE_MARKER_SHADOW_LAYER_ID = 'site-marker-shadow'
export const SITE_MARKER_COLOR = '#e0793a'

// Soft blurred halo drawn beneath the site markers so they read clearly
// against both light basemap and dark overlay colors underneath them.
export const SITE_MARKER_SHADOW_PAINT = {
  'circle-color': '#000000',
  'circle-opacity': 0.22,
  'circle-radius': 11,
  'circle-blur': 0.9,
  'circle-translate': [0, 1.5],
}

// Raster overlays default to a partial opacity so basemap roads/labels stay
// visible underneath the data layer, rather than fully obscuring it.
export const DEFAULT_RASTER_OPACITY = 0.6

// ---------------------------------------------------------------------------
// PART 7 — Per-site prospectivity surface (from prospectivity/classify_export.py)
// ---------------------------------------------------------------------------
export const PROSPECTIVITY_SOURCE_ID = 'prospectivity-source'
export const PROSPECTIVITY_FILL_LAYER_ID = 'prospectivity-fill'
export const PROSPECTIVITY_BOUNDARY_LAYER_ID = 'prospectivity-band-boundary'
export const PROSPECTIVITY_EDGE_LAYER_ID = 'prospectivity-edge-feather'

export const CONFIDENCE_BANDS = ['Very Low', 'Low', 'Moderate', 'High', 'Very High']

// Part 7.3 — five DISCRETE flat colors, no gradient. These follow the semantic
// already established by CONFIDENCE_COLOR_RAMP (red = low confidence, green =
// high) and are interpolated from those same three anchors, so the app's
// existing palette is extended rather than replaced.
export const CONFIDENCE_BAND_COLORS = {
  'Very Low': '#8c2f22',
  'Low': '#c0392b',
  'Moderate': '#e0793a',
  'High': '#7a9a52',
  'Very High': '#3f8f5f',
}

// Continuous scientific color ramp communicating low → high prospectivity/confidence,
// consistent with CONFIDENCE_COLOR_RAMP (#c0392b -> #e0793a -> #3f8f5f) and ConfidenceLegend.
export const PROSPECTIVITY_FILL_PAINT = {
  'fill-color': [
    'interpolate',
    ['linear'],
    ['coalesce', ['get', 'ensemble_confidence_score'], ['get', 'confidence_score'], 0],
    0.0, '#8c2f22',
    0.15, '#c0392b',
    0.30, '#e0793a',
    0.45, '#7a9a52',
    0.60, '#3f8f5f',
  ],
  'fill-opacity': 1,
  // MapLibre defaults `fill-outline-color` to `fill-color`, which strokes EVERY
  // cell and renders the surface as a graph-paper mesh (confirmed in-browser).
  // Force it transparent so adjacent same-band cells merge into one flat area
  // and the only visible boundary is the dissolved band outline drawn above.
  'fill-outline-color': 'rgba(0,0,0,0)',
}

// Part 7.3 — subtle hairline drawn ONLY where two bands meet. This is applied
// to the dissolved band polygons (*_bands.geojson), never per-cell: stroking
// every 300 m cell produces a graph-paper mesh across the whole surface
// (confirmed in-browser) rather than a band boundary.
export const PROSPECTIVITY_BOUNDARY_PAINT = {
  'line-color': 'rgba(26,24,21,0.35)',
  'line-width': 0.8,
}

// Part 7.4 — the ONLY place softness is correct: a blurred stroke following the
// dissolved surface's outer ring, so it fades into the basemap instead of
// terminating on a hard rectangular cut. Interior band colors stay crisp.
export const PROSPECTIVITY_EDGE_PAINT = {
  'line-color': 'rgba(26,24,21,0.22)',
  'line-width': 14,
  'line-blur': 16,
}

export const PROSPECTIVITY_BANDS_SOURCE_ID = 'prospectivity-bands-source'

export function prospectivityUrl(siteId) {
  return `/prospectivity/${siteId}.geojson`
}

export function prospectivityBandsUrl(siteId) {
  return `/prospectivity/${siteId}_bands.geojson`
}
export const MIN_RASTER_OPACITY = 0.25
export const MAX_RASTER_OPACITY = 0.95

export const SITES_GEOJSON = {
  type: 'FeatureCollection',
  features: SAMPLE_SITES.map((site) => ({
    type: 'Feature',
    properties: {
      id: site.id,
      name: site.name,
    },
    geometry: {
      type: 'Point',
      coordinates: [site.longitude, site.latitude],
    },
  })),
}


// P6 Raster Layer Configurations (from gis/tiles/manifest.json)
export const SPECTRAL_LAYER_CONFIG = {
  sourceId: 'spectral-alteration-source',
  layerId: 'spectral-alteration-layer',
  url: '/tiles/iron_oxide_latest.png',
  date: '2026-09-22',
  coordinates: RASTER_OVERLAY_COORDINATES,
}

export const NDVI_TIMESERIES_CONFIG = [
  {
    week_index: 1,
    id: 'ndvi-week-1',
    name: 'NDVI Week 1',
    date: '2026-09-01',
    window_start: '2026-08-25',
    window_end: '2026-09-01',
    url: '/tiles/ndvi_week_1.png',
    coordinates: RASTER_OVERLAY_COORDINATES,
  },
  {
    week_index: 2,
    id: 'ndvi-week-2',
    name: 'NDVI Week 2',
    date: '2026-09-08',
    window_start: '2026-09-01',
    window_end: '2026-09-08',
    url: '/tiles/ndvi_week_2.png',
    coordinates: RASTER_OVERLAY_COORDINATES,
  },
  {
    week_index: 3,
    id: 'ndvi-week-3',
    name: 'NDVI Week 3',
    date: '2026-09-15',
    window_start: '2026-09-08',
    window_end: '2026-09-15',
    url: '/tiles/ndvi_week_3.png',
    coordinates: RASTER_OVERLAY_COORDINATES,
  },
  {
    week_index: 4,
    id: 'ndvi-week-4',
    name: 'NDVI Week 4',
    date: '2026-09-22',
    window_start: '2026-09-15',
    window_end: '2026-09-22',
    url: '/tiles/ndvi_week_4.png',
    coordinates: RASTER_OVERLAY_COORDINATES,
  },
]
