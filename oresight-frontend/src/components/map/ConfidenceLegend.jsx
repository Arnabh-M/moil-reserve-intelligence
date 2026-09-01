import React from 'react';
import { CONFIDENCE_COLOR_RAMP } from '../../lib/map';

export default function ConfidenceLegend({ visible }) {
  if (!visible) return null;

  return (
    <div className="absolute bottom-6 right-6 z-10 w-64 rounded-xl border border-border bg-white/95 p-4 shadow-lg backdrop-blur-md transition-all">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-heading text-xs font-bold text-navy uppercase tracking-wider">
          Reserve Confidence
        </h4>
        <span className="text-[10px] text-slate-500 font-medium">Kriging Surface</span>
      </div>

      <div
        className="h-3 w-full rounded-md shadow-inner mb-2"
        style={{
          background: `linear-gradient(to right, ${CONFIDENCE_COLOR_RAMP.low}, ${CONFIDENCE_COLOR_RAMP.mid}, ${CONFIDENCE_COLOR_RAMP.high})`,
        }}
      />

      <div className="flex justify-between text-[11px] font-semibold text-slate-600">
        <span>0.0 (Low)</span>
        <span>0.5 (Mid)</span>
        <span>1.0 (High)</span>
      </div>
    </div>
  );
}
