import React, { useState } from 'react';
import { Zap, ArrowRight } from 'lucide-react';
import Badge from './Badge';
import Button from './Button';

export default function RecommendationCard({ trigger, options }) {
  const [actioned, setActioned] = useState({});

  return (
    <div className="bg-white rounded-xl border border-border shadow-sm transition-shadow duration-200 hover:shadow-md">
      {/* Trigger description */}
      <div className="flex items-start gap-3 px-5 pt-4 pb-3 border-b border-border">
        <div className="p-2 rounded-lg bg-orange/10 text-orange shrink-0 mt-0.5">
          <Zap size={16} />
        </div>
        <p className="text-sm text-text-primary leading-relaxed">{trigger}</p>
      </div>

      {/* Option blocks */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-4">
        {options.map((opt, idx) => (
          <div
            key={idx}
            className={`rounded-lg border p-4 transition-all duration-200 ${
              actioned[idx]
                ? 'bg-success/5 border-success/20'
                : 'bg-bg border-border hover:border-teal/30 hover:-translate-y-0.5'
            }`}
          >
            <h4 className="text-sm font-semibold text-text-primary mb-1">{opt.title}</h4>
            <p className="text-xs text-text-secondary mb-3 leading-relaxed">{opt.description}</p>
            <div className="mb-3">
              <Badge variant={opt.impactVariant || 'operational'}>{opt.impact}</Badge>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" className="flex-1">
                Simulate
              </Button>
              <Button
                variant={actioned[idx] ? 'secondary' : 'primary'}
                size="sm"
                className="flex-1"
                disabled={actioned[idx]}
                onClick={() => setActioned(prev => ({ ...prev, [idx]: true }))}
              >
                {actioned[idx] ? '✓ Actioned' : 'Action'}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
