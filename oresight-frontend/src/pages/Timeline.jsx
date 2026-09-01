import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ExternalLink, Clock } from 'lucide-react';
import { Badge, EmptyState } from '../components';

const events = [
  {
    id: 1,
    timestamp: '2 hrs ago',
    severity: 'critical',
    title: 'Conveyor BAL-1 down — weather delay',
    description:
      'eq_bal_03 went offline due to sustained heavy rain at Balaghat. Estimated downtime 44.6 hrs. Blast plan bp_bal_01 impacted.',
    site: 'Balaghat',
    dotColor: 'bg-danger',
  },
  {
    id: 2,
    timestamp: '5 hrs ago',
    severity: 'critical',
    title: 'Risk event re_bal_01 escalated to Critical',
    description:
      'Weather delay risk score increased from 0.65 to 0.78. Heavy rain severity 5 continues at Balaghat, threatening OreZone oz_bal_01 extraction.',
    site: 'Balaghat',
    dotColor: 'bg-danger',
  },
  {
    id: 3,
    timestamp: '1 day ago',
    severity: 'warning',
    title: 'Drill NAG-1 failure — hydraulic leak',
    description:
      'eq_nag_02 went down at Nagpur site. BlastPlan bp_nag_01 readiness now blocked. Spare drill available at Bhandara (eq_bhd_02).',
    site: 'Nagpur',
    dotColor: 'bg-warning',
  },
  {
    id: 4,
    timestamp: '2 days ago',
    severity: 'warning',
    title: 'Loader BAL-1 mechanical failure resolved',
    description:
      'eq_bal_04 repaired after 8.19 hrs downtime at Balaghat. Back online and operational. No blast plan impact.',
    site: 'Balaghat',
    dotColor: 'bg-warning',
  },
  {
    id: 5,
    timestamp: '4 days ago',
    severity: 'operational',
    title: 'BlastPlan bp_bhd_02 completed successfully',
    description:
      'Bhandara blasting operation completed on schedule (Aug 12). OreZone oz_bhd_01 ready for extraction. No incidents reported.',
    site: 'Bhandara',
    dotColor: 'bg-success',
  },
  {
    id: 6,
    timestamp: '7 days ago',
    severity: 'operational',
    title: 'Heavy rain at Bhandara concluded',
    description:
      'WeatherEvent we_bhd_01 (severity 3) ended Aug 17. Operations resumed at full capacity. Equipment inspections cleared.',
    site: 'Bhandara',
    dotColor: 'bg-success',
  },
];

export default function Timeline() {
  const navigate = useNavigate();

  if (events.length === 0) {
    return (
      <div className="page-container">
        <h2 className="page-title">Event Timeline</h2>
        <p className="page-subtitle">
          Chronological record of disruptions, resolutions, and milestones across all mine sites
        </p>
        <EmptyState
          icon={Clock}
          title="No events recorded"
          message="Disruptions, resolutions, and milestones will appear here as they happen."
          tone="neutral"
        />
      </div>
    );
  }

  return (
    <div className="page-container">
      <h2 className="page-title">Event Timeline</h2>
      <p className="page-subtitle">
        Chronological record of disruptions, resolutions, and milestones across all mine sites
      </p>

      {/* Timeline */}
      <div className="relative ml-4 mt-2">
        {/* Vertical connecting line */}
        <div
          className="absolute left-[7px] top-3 bottom-3 w-[2px] bg-border"
          aria-hidden="true"
        />

        <div className="space-y-0">
          {events.map((event, idx) => (
            <div
              key={event.id}
              className="relative flex items-start gap-5 pb-8 group animate-fade-in"
              style={{ animationDelay: `${idx * 0.08}s` }}
            >
              {/* Dot */}
              <div className="relative z-10 shrink-0">
                <span
                  className={`block w-4 h-4 rounded-full border-[3px] border-white shadow-sm ${event.dotColor}`}
                />
              </div>

              {/* Event content */}
              <div className="flex-1 bg-white rounded-xl border border-border p-4 transition-all duration-200 hover:shadow-md hover:border-teal/20 -mt-1">
                <div className="flex items-start justify-between gap-3 mb-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="text-sm font-semibold text-text-primary">{event.title}</h4>
                    <Badge variant={event.severity} dot>{event.severity}</Badge>
                  </div>
                  <span className="text-[11px] text-text-muted whitespace-nowrap shrink-0">
                    {event.timestamp}
                  </span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed mb-2">
                  {event.description}
                </p>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-medium text-text-muted uppercase tracking-wide">
                    {event.site}
                  </span>
                  <button
                    type="button"
                    onClick={() => navigate(`/site/${event.site.toLowerCase()}`)}
                    className="flex items-center gap-1 text-xs text-teal font-medium hover:text-teal/80 transition-colors duration-150 cursor-pointer"
                  >
                    View Details
                    <ExternalLink size={11} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
