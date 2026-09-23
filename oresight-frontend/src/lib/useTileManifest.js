import { useEffect, useState } from 'react'
import { TILE_MANIFEST_URL } from './map'

// Loads /tiles/manifest.json once. `manifest` stays null until it arrives (or
// if it fails), which the config builders in map.js treat as "loading".
export function useTileManifest() {
  const [state, setState] = useState({ manifest: null, error: null })

  useEffect(() => {
    let cancelled = false
    fetch(TILE_MANIFEST_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load tile manifest (HTTP ${res.status})`)
        return res.json()
      })
      .then((manifest) => !cancelled && setState({ manifest, error: null }))
      .catch((error) => !cancelled && setState({ manifest: null, error }))
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
