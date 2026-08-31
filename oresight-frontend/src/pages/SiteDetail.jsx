import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  MapPin, ShieldAlert, Clock, Network, BarChart3,
} from 'lucide-react';
import { Card, KPIStat, Badge, RecommendationCard, ProductionChart } from '../components';
import { sites, oreZones, equipment } from '../data/mockData';
import { SITE_MAP } from '../api/client';

const siteExtras = {
  balaghat: {
    reserveConfidence: 78,
    activeRisks: 1,
    lastUpdated: 'Aug 30, 2026 14:20',
    recommendations: [
      {
        trigger:
          'Heavy rainfall detected near Balaghat — BlastPlan #14 (bp_bal_01) delayed by 2 days. OreZone oz_bal_01 extraction schedule at risk.',
        options: [
          {
            title: 'Reschedule',
            description: 'Push bp_bal_01 to Sep 1 when weather clears. Extends timeline by 4 days but preserves equipment safety margins.',
            impact: '+12% safety margin',
            impactVariant: 'operational',
          },
          {
            title: 'Redeploy',
            description: 'Move Excavator BAL-1 to Nagpur site for active extraction while Balaghat waits. Recovers 680 t of idle capacity.',
            impact: '+680 t recovered',
            impactVariant: 'info',
          },
          {
            title: 'Adjust Plan',
            description: 'Reduce blast charge and proceed with modified parameters during lighter rain windows. Higher risk, faster turnaround.',
            impact: '-8% confidence',
            impactVariant: 'warning',
          },
        ],
      },
    ],
  },
  nagpur: {
    reserveConfidence: 74,
    activeRisks: 1,
    lastUpdated: 'Aug 30, 2026 11:45',
    recommendations: [
      {
        trigger:
          'Drill NAG-1 (eq_nag_02) at Nagpur went down due to hydraulic failure. BlastPlan bp_nag_01 readiness blocked — estimated 48hr repair.',
        options: [
          {
            title: 'Reschedule',
            description: 'Delay bp_nag_01 by 3 days until eq_nag_02 repair is complete. No additional cost, schedule slips to Sep 5.',
            impact: '-3 day slip',
            impactVariant: 'warning',
          },
          {
            title: 'Redeploy',
            description: 'Transfer idle Drill BHD-1 from Bhandara to Nagpur. Same type, no blast plan dependency. Transport takes 6 hours.',
            impact: '+15% recovery',
            impactVariant: 'operational',
          },
          {
            title: 'Adjust Plan',
            description: 'Use Excavator NAG-1 as interim drilling substitute with modified bit. Slower but avoids full delay.',
            impact: '-22% efficiency',
            impactVariant: 'delayed',
          },
        ],
      },
    ],
  },
  bhandara: {
    reserveConfidence: 69,
    activeRisks: 0,
    lastUpdated: 'Aug 30, 2026 09:30',
    recommendations: [
      {
        trigger:
          'Production shortfall at Bhandara Mine — actual output 720 t/day vs 960 t target (25% below). Conveyor BHD-1 throughput degraded.',
        options: [
          {
            title: 'Reschedule',
            description: 'Schedule conveyor maintenance for next weekend. Accept shortfall this week, full recovery by Monday.',
            impact: '+4 day delay',
            impactVariant: 'warning',
          },
          {
            title: 'Redeploy',
            description: 'Route Bhandara output through Loader BHD-1 bypass path. 85% of conveyor capacity, eliminates bottleneck.',
            impact: '+85% capacity',
            impactVariant: 'operational',
          },
          {
            title: 'Adjust Plan',
            description: 'Increase Balaghat and Nagpur targets by 120 t/day each to offset Bhandara shortfall across the portfolio.',
            impact: '+240 t/day offset',
            impactVariant: 'info',
          },
        ],
      },
    ],
  },
};

const tabs = [
  { id: 'production', label: 'Production History', icon: BarChart3 },
  { id: 'recommendations', label: 'Recommendations', icon: ShieldAlert },
  { id: 'graph', label: 'Graph', icon: Network },
];

export default function SiteDetail() {
  const { id } = useParams();
  const [activeTab, setActiveTab] = useState('production');

  const site = sites.find(s => s.id === id || String(SITE_MAP[s.id]) === String(id));
  const normalizedSiteId = site?.id || id;
  const numericSiteId = SITE_MAP[normalizedSiteId] || 1;
  const extras = siteExtras[normalizedSiteId] || siteExtras.balaghat;
  const siteEquipment = equipment.filter(e => e.site_id === normalizedSiteId);
  const siteZones = oreZones.filter(z => z.site_id === normalizedSiteId);

  if (!site) {
    return (
      <div className="page-container">
        <div className="flex flex-col items-center justify-center py-20 text-center animate-fade-in">
          <p className="text-lg font-semibold text-text-primary mb-2">Site Not Found</p>
          <p className="text-sm text-text-secondary">No site found with ID "{id}". Available sites: balaghat, nagpur, bhandara.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-start justify-between mb-1">
        <div>
          <h2 className="page-title">{site.name}</h2>
          <div className="flex items-center gap-2 mt-0.5">
            <MapPin size={13} className="text-text-muted" />
            <span className="text-sm text-text-secondary">{site.belt} — {site.state}</span>
          </div>
        </div>
        <Badge variant={extras.activeRisks > 0 ? 'warning' : 'operational'} dot>
          {extras.activeRisks > 0 ? `${extras.activeRisks} Active Risk` : 'All Clear'}
        </Badge>
      </div>

      {/* KPI Stats */}
      <div className="grid-kpi stagger-children mt-4">
        <KPIStat
          label="Reserve Confidence"
          value={`${extras.reserveConfidence}%`}
          delta={null}
          deltaLabel={`${siteZones.length} ore zones mapped`}
          icon={MapPin}
          color="teal"
        />
        <KPIStat
          label="Active Risks"
          value={extras.activeRisks}
          delta={null}
          deltaLabel={extras.activeRisks > 0 ? 'requires attention' : 'no active risks'}
          icon={ShieldAlert}
          color={extras.activeRisks > 0 ? 'danger' : 'success'}
        />
        <KPIStat
          label="Equipment Online"
          value={`${siteEquipment.filter(e => e.status === 'up').length}/${siteEquipment.length}`}
          delta={null}
          deltaLabel={`${Math.round((siteEquipment.filter(e => e.status === 'up').length / siteEquipment.length) * 100)}% uptime`}
          icon={Clock}
          color="orange"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mt-6 mb-4 p-1 bg-white rounded-lg border border-border w-fit">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                activeTab === tab.id
                  ? 'bg-orange text-white shadow-sm'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg'
              }`}
            >
              <Icon size={14} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content: Production History */}
      {activeTab === 'production' && (
        <Card
          title="Production History"
          subtitle={`30-day extraction telemetry for ${site.name} (Solid: Actual, Dashed: Target)`}
        >
          <ProductionChart site_id={numericSiteId} days={30} className="mt-2" />
        </Card>
      )}

      {/* Tab Content: Recommendations */}
      {activeTab === 'recommendations' && (
        <div className="space-y-5 stagger-children">
          {extras.recommendations.map((rec, idx) => (
            <RecommendationCard key={idx} trigger={rec.trigger} options={rec.options} />
          ))}
        </div>
      )}

      {/* Tab Content: Graph */}
      {activeTab === 'graph' && (
        <Card title="Knowledge Graph" subtitle={`Neo4j subgraph for ${site.name}`}>
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-14 h-14 rounded-2xl bg-teal/10 flex items-center justify-center mb-3">
              <Network size={24} className="text-teal" />
            </div>
            <p className="text-sm font-medium text-text-secondary mb-1">
              Graph Visualization
            </p>
            <p className="text-xs text-text-muted max-w-sm">
              This panel will display the Neo4j subgraph for {site.name} — showing
              equipment, blast plans, ore zones, weather events, and their causal relationships.
            </p>
            <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg border border-border text-[10px] text-text-muted">
              <span className="w-1.5 h-1.5 rounded-full bg-teal animate-pulse" />
              Pending Day 3-4 API integration
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
