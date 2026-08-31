// ─────────────────────────────────────────────────────────────────────
// API Configuration & Mode Switcher
// Default USE_MOCK is true for development without a running backend.
// Switch to false (or set VITE_USE_MOCK=false in .env) to connect to live FastAPI.
// ─────────────────────────────────────────────────────────────────────

const ENV_MOCK = import.meta.env?.VITE_USE_MOCK;
const INITIAL_MOCK_STATE = ENV_MOCK !== undefined ? ENV_MOCK === 'true' : true;

// In-memory runtime state that allows dynamic toggling without restarting Vite
let runtimeMockState = INITIAL_MOCK_STATE;
const listeners = new Set();

export const API_BASE_URL = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

export function isMockEnabled() {
  return runtimeMockState;
}

export function setMockEnabled(enabled) {
  runtimeMockState = Boolean(enabled);
  listeners.forEach(cb => cb(runtimeMockState));
}

export function subscribeMockState(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

// Export default toggle value for easy import
export const USE_MOCK = runtimeMockState;
