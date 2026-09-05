import React from 'react';
import { useLocation } from 'react-router-dom';
import { Construction, Sliders, Shield, Database, Bell } from 'lucide-react';
import { Card } from '../components';

const pageTitles = {
  '/map': 'Reserve Intelligence Map',
  '/blasting': 'Blast Schedule & Planning',
  '/geology': 'Geological Structure & Cross-Section',
  '/settings': 'System Settings & Controls',
};

export default function ComingSoon() {
  const location = useLocation();
  const title = pageTitles[location.pathname] || 'Module In Development';
  const isSettings = location.pathname === '/settings';

  if (isSettings) {
    return (
      <div className="page-container space-y-8 font-body">
        <div className="pb-4 border-b border-[var(--divider)]">
          <h1 className="page-title">System Settings &amp; Telemetry Controls</h1>
          <p className="page-subtitle mb-0">
            Configure MOIL data synchronization frequencies, vector database thresholds, and alert notifications
          </p>
        </div>

        {/* Clean Un-boxed Control Groups */}
        <div className="space-y-6">
          {/* Section 1: Telemetry & Sync */}
          <Card title="Telemetry Data Synchronization" subtitle="Configure automated mine telemetry refresh rates">
            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between py-2 border-b border-[var(--divider)]">
                <div>
                  <p className="font-semibold text-[var(--text-primary)]">Telemetry Polling Interval</p>
                  <p className="text-[11px] text-[var(--text-muted)] font-normal">Frequency of live pit sensor and haulage polling</p>
                </div>
                <select className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg px-3 py-1.5 font-mono text-xs text-[var(--text-primary)]">
                  <option value="15">15 Seconds (Real-time)</option>
                  <option value="30">30 Seconds</option>
                  <option value="60">60 Seconds</option>
                </select>
              </div>

              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="font-semibold text-[var(--text-primary)]">Mock Data Engine Fallback</p>
                  <p className="text-[11px] text-[var(--text-muted)] font-normal">Use simulated telemetry when backend API is unreachable</p>
                </div>
                <input type="checkbox" defaultChecked className="accent-[var(--forest-primary)] cursor-pointer" />
              </div>
            </div>
          </Card>

          {/* Section 2: Kriging & AI Model Thresholds */}
          <Card title="Geological AI &amp; Spatial Twin Models" subtitle="Configure confidence score thresholds for target prediction">
            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between py-2 border-b border-[var(--divider)]">
                <div>
                  <p className="font-semibold text-[var(--text-primary)]">Minimum Confidence Threshold</p>
                  <p className="text-[11px] text-[var(--text-muted)] font-normal">Filter low-confidence reserve predictions in GIS map</p>
                </div>
                <span className="font-mono font-bold text-[var(--forest-primary)] dark:text-[var(--forest-secondary)]">75% Confidence</span>
              </div>

              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="font-semibold text-[var(--text-primary)]">NDVI Canopy Correlation</p>
                  <p className="text-[11px] text-[var(--text-muted)] font-normal">Weight satellite vegetation anomaly in drill recommendations</p>
                </div>
                <input type="checkbox" defaultChecked className="accent-[var(--forest-primary)] cursor-pointer" />
              </div>
            </div>
          </Card>

          {/* Section 3: Risk Alert Notifications */}
          <Card title="Alert Notification Rules" subtitle="Manage operational disruption severity triggers">
            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="font-semibold text-[var(--text-primary)]">Critical Risk Pop-up Alerts</p>
                  <p className="text-[11px] text-[var(--text-muted)] font-normal">Notify immediately for critical slope instability or pit wall anomalies</p>
                </div>
                <input type="checkbox" defaultChecked className="accent-[var(--forest-primary)] cursor-pointer" />
              </div>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container flex items-center justify-center min-h-[calc(100vh-10rem)]">
      <div className="text-center animate-fade-in bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl p-10 max-w-md">
        <div className="w-12 h-12 mx-auto mb-4 rounded-lg bg-[var(--accent-soft)] flex items-center justify-center text-[var(--forest-primary)] dark:text-[var(--forest-secondary)]">
          <Construction size={22} strokeWidth={2} />
        </div>
        <h2 className="text-lg font-heading font-semibold text-[var(--text-primary)] mb-1.5">{title}</h2>
        <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto leading-relaxed mb-5 font-body">
          This module is being refined for automated spatial telemetry integration in the upcoming MOIL deployment sprint.
        </p>
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[var(--accent-soft)] text-[11px] font-mono font-medium text-[var(--forest-primary)] dark:text-[var(--forest-secondary)]">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--forest-primary)] dark:bg-[var(--forest-secondary)] animate-pulse" />
          Sprint Phase 2 • In Development
        </span>
      </div>
    </div>
  );
}



