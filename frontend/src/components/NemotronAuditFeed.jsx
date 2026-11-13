import React from 'react';
import { History, ExternalLink, ArrowRight } from 'lucide-react';

export default function NemotronAuditFeed({ cycles, onSelectCycle }) {
  return (
    <div className="bg-obsidian-900 border border-obsidian-border rounded-xl p-3.5 shadow-xl backdrop-blur-md flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between mb-2.5 border-b border-obsidian-border pb-2">
        <div className="flex items-center space-x-2">
          <History className="w-4 h-4 text-intel-light" />
          <h2 className="text-xs font-bold tracking-tight text-white uppercase font-mono">
            Nemotron Root-Cause & Visual Audit Trail
          </h2>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-obsidian-800 text-slate-400 tabular-nums">
            {cycles.length} Recorded Cycles
          </span>
          <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-intel-blue/20 text-intel-light border border-intel-blue/30 font-semibold uppercase">
            Cloudinary Visual Trail
          </span>
        </div>
      </div>

      {/* Scrollable Feed */}
      <div className="space-y-2 max-h-[340px] overflow-y-auto pr-1">
        {cycles.length === 0 ? (
          <div className="text-center py-12 text-slate-500 font-mono text-xs">
            No inspection cycles recorded yet. Click "Simulate Cycle" to begin.
          </div>
        ) : (
          cycles.map((cyc) => {
            const isDefective = cyc.action === 'DEFECTIVE_BOWL';
            const isRegrasp = cyc.action === 'REGRASP_TRIGGERED';
            const isPerfect = cyc.action === 'PERFECT_BOWL';

            return (
              <div
                key={cyc.cycle_id}
                onClick={() => onSelectCycle(cyc)}
                className="p-2 rounded-lg bg-obsidian-950/80 border border-obsidian-border hover:border-intel-light/60 cursor-pointer transition-all flex items-start space-x-2.5 group relative overflow-hidden"
              >
                {/* Cloudinary Composite Thumbnail */}
                <div className="relative w-14 h-14 rounded overflow-hidden bg-black shrink-0 border border-obsidian-border">
                  <img
                    src={cyc.composite_url || cyc.raw_url}
                    alt={cyc.cycle_id}
                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                  />
                  <div className={`absolute bottom-0 inset-x-0 text-[8px] font-mono text-center py-0.2 font-bold tabular-nums ${
                    isDefective ? 'bg-rose-600/90 text-white' : isRegrasp ? 'bg-amber-600/90 text-white' : 'bg-emerald-600/90 text-white'
                  }`}>
                    {cyc.anomaly_score?.toFixed(2)}
                  </div>
                </div>

                {/* Details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <div className="flex items-center space-x-1.5 font-mono">
                      <span className="text-xs font-bold text-white tracking-tight">{cyc.cycle_id}</span>
                      <span className="text-[10px] text-slate-500 tabular-nums">{cyc.timestamp}</span>
                      <span className={`text-[8.5px] px-1.5 py-0.2 rounded font-mono uppercase font-bold ${
                        cyc.color === 'yellow' ? 'bg-amber-500/20 text-amber-300' :
                        cyc.color === 'red' ? 'bg-rose-500/20 text-rose-300' :
                        cyc.color === 'blue' ? 'bg-blue-500/20 text-blue-300' :
                        cyc.color === 'green' ? 'bg-emerald-500/20 text-emerald-300' :
                        'bg-obsidian-800 text-slate-300'
                      }`}>
                        {cyc.color}
                      </span>
                    </div>

                    <div className="flex items-center space-x-1">
                      <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded font-bold ${
                        isDefective
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                          : isRegrasp
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                          : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      }`}>
                        {isDefective ? 'DEFECTIVE' : isRegrasp ? 'UNCERTAIN' : 'PERFECT'}
                      </span>
                    </div>
                  </div>

                  {/* Defect label & Destination */}
                  <div className="flex items-center space-x-2 text-[11px] mb-0.5 text-slate-300">
                    <span className="text-white font-medium truncate font-sans">{cyc.defect_label}</span>
                    <span className="text-slate-600 font-mono">•</span>
                    <span className="text-intel-light flex items-center space-x-0.5 shrink-0 font-mono text-[10px]">
                      <ArrowRight className="w-2.5 h-2.5 inline" />
                      <span>{cyc.destination}</span>
                    </span>
                  </div>

                  {/* Nemotron Root Cause reasoning quote */}
                  <div className="text-[10.5px] text-slate-400 italic line-clamp-2 bg-obsidian-900/60 p-1 rounded border border-obsidian-border/70 font-sans">
                    "{cyc.root_cause_reasoning}"
                  </div>

                  {/* Telemetry footer with non-wrapping tabular numbers */}
                  <div className="mt-1 flex flex-wrap items-center gap-x-2.5 text-[9px] font-mono text-slate-500 tabular-nums">
                    <span>NPU: <span className="text-slate-300 font-medium">{cyc.latencies?.npu_anomalib_ms || 9.4}ms</span></span>
                    <span>iGPU: <span className="text-slate-300 font-medium">{cyc.latencies?.igpu_vla_ms || 24.1}ms</span></span>
                    <span>CPU: <span className="text-slate-300 font-medium">{cyc.latencies?.cpu_control_ms || 2.1}ms</span></span>
                    <span>Total: <span className="text-intel-light font-bold">{cyc.latencies?.total_ms || 35.6}ms</span></span>
                  </div>
                </div>

                <div className="shrink-0 self-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <ExternalLink className="w-3.5 h-3.5 text-intel-light" />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
