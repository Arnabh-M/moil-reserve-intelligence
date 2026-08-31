// Centralized API client for the OreSight FastAPI backend.
// All backend requests should go through the functions exported here
// rather than calling fetch() directly from components.

const BASE_URL = 'http://localhost:8000'

async function request(path) {
  const res = await fetch(`${BASE_URL}${path}`)
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with status ${res.status}`)
  }
  return res.json()
}

export function getSites() {
  return request('/sites')
}

export function getEquipment(siteId) {
  const query = siteId ? `?site_id=${encodeURIComponent(siteId)}` : ''
  return request(`/equipment${query}`)
}

export function getRiskEvents() {
  return request('/risk-events')
}
