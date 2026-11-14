import React from 'react';
import { History, ExternalLink } from 'lucide-react';

export default function NemotronAuditFeed({ cycles, onSelectCycle }) {
  return (
    <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-4 flex flex-col justify-between h-full">
      {/* Top Header */}
      <div>
        <div className="flex items-center justify-between pb-2 border-b border-[#26313e]">
          <div className="flex items-center space-x-2">
            <History className="w-4 h-4 text-[#89b9ef]" />
            <h2 className="text-[16px] font-semibold text-[#edf2f7]">
              Inspection history
            </h2>
          </div>
          <div className="flex items-center space-x-2">
            <div className="bg-[#18212c] px-2.5 py-0.5 rounded-[4px] border border-[#26313e]">
              <span className="text-[10px] font-medium text-[#b5c0ce] tabular-nums">
                {cycles.length} cycles
              </span>
            </div>
            <button
              onClick={() => {
                if (cycles.length > 0) onSelectCycle(cycles[0]);
              }}
              className="text-[11px] font-medium text-[#55dbb1] hover:underline flex items-center space-x-1"
            >
              <span>View visual trail ↗</span>
            </button>
          </div>
        </div>

        <div className="text-[11px] text-[#8e9bae] mt-2 mb-3">
          Nemotron root-cause analysis · Cloudinary visual evidence
        </div>

        {/* Scrollable Feed List */}
        <div className="space-y-3 max-h-[220px] overflow-y-auto pr-1 divide-y divide-[#26313e]/60">
          {cycles.length === 0 ? (
            <div className="text-center py-8 text-[#8e9bae] text-[11px]">
              No cycles recorded yet. Click "Simulate Cycle" to begin inspection.
            </div>
          ) : (
            cycles.map((cyc) => {
              const isDefective = cyc.action === 'DEFECTIVE_BOWL';
              const isRegrasp = cyc.action === 'REGRASP_TRIGGERED';
              const isPerfect = cyc.action === 'PERFECT_BOWL' || (!isDefective && !isRegrasp);

              const colorUpper = (cyc.color || 'green').charAt(0).toUpperCase() + (cyc.color || 'green').slice(1);

              return (
                <div
                  key={cyc.cycle_id}
                  onClick={() => onSelectCycle(cyc)}
                  className="pt-2.5 first:pt-0 flex items-start space-x-3 cursor-pointer group hover:bg-[#18212c]/30 rounded-[5px] p-1.5 transition-colors"
                >
                  {/* Evidence Thumbnail (52x52) with score overlay */}
                  <div className="relative w-[52px] h-[52px] rounded-[5px] overflow-hidden border border-[#26313e] bg-black shrink-0">
                    <img
                      src={cyc.composite_url || cyc.raw_url}
                      alt={cyc.cycle_id}
                      className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                    />
                    <div className={`absolute bottom-0 inset-x-0 h-[17px] flex items-center justify-center text-[10px] font-semibold tabular-nums ${
                      isDefective
                        ? 'bg-[#38232c] text-[#f28d95]'
                        : isRegrasp
                        ? 'bg-[#352e21] text-[#e9bf79]'
                        : 'bg-[#15352e] text-[#55dbb1]'
                    }`}>
                      {cyc.anomaly_score?.toFixed(2)}
                    </div>
                  </div>

                  {/* Details column */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <div className="flex items-center space-x-2">
                        <span className="text-[11px] font-semibold text-[#edf2f7] font-mono">
                          {cyc.cycle_id}
                        </span>
                        <span className="text-[10px] text-[#8e9bae] tabular-nums font-mono">
                          {cyc.timestamp}
                        </span>
                        <span className={`text-[10px] font-medium ${
                          cyc.color === 'yellow' ? 'text-[#e9bf79]' :
                          cyc.color === 'red' ? 'text-[#f28d95]' :
                          cyc.color === 'blue' ? 'text-[#89b9ef]' : 'text-[#55dbb1]'
                        }`}>
                          {colorUpper}
                        </span>
                      </div>

                      {/* Outcome badge */}
                      <div className={`px-2 py-0.5 rounded-[4px] text-[10px] font-medium shrink-0 ${
                        isDefective
                          ? 'bg-[#38232c] text-[#f28d95]'
                          : isRegrasp
                          ? 'bg-[#352e21] text-[#e9bf79]'
                          : 'bg-[#15352e] text-[#55dbb1]'
                      }`}>
                        {isDefective ? 'Defective' : isRegrasp ? 'Re-grasp' : 'Accepted'}
                      </div>
                    </div>

                    {/* Routing */}
                    <div className="text-[11px] font-medium text-[#b5c0ce] truncate">
                      {cyc.defect_label || 'None (Pristine)'} → {
                        isDefective ? 'DEFECTIVE Bowl (Bowl 2)' :
                        isRegrasp ? 'Inspection Camera (Re-orient)' :
                        'GOOD Bowl (Bowl 1)'
                      }
                    </div>

                    {/* Nemotron Root Cause Analysis Quote */}
                    <div className="text-[10px] text-[#8e9bae] truncate mt-0.5 italic">
                      "{cyc.nemotron_reasoning || cyc.root_cause_reasoning || 'No topological variance detected.'}"
                    </div>

                    {/* Latency footnote */}
                    {cyc.latencies && (
                      <div className="text-[9px] font-mono text-[#8e9bae]/70 mt-1 flex items-center space-x-2">
                        <span>NPU: {cyc.latencies.npu_ms ?? cyc.latencies.npu_anomalib_ms ?? 9.4}ms</span>
                        <span>•</span>
                        <span>iGPU: {cyc.latencies.igpu_ms ?? cyc.latencies.igpu_vla_ms ?? 24.1}ms</span>
                        <span>•</span>
                        <span>CPU: {cyc.latencies.cpu_ms ?? cyc.latencies.cpu_control_ms ?? 2.1}ms</span>
                        <span>•</span>
                        <span className="text-[#55dbb1]">Total: {cyc.latencies.total_ms ?? 35.6}ms</span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
