import React from 'react';
import { X, Layers, Cpu, Zap, Activity, ShieldAlert, CheckCircle, RotateCcw, ArrowRight } from 'lucide-react';

export default function CycleModal({ cycle, onClose }) {
  if (!cycle) return null;

  const isDefective = cycle.action === 'DEFECTIVE_BOWL';
  const isRegrasp = cycle.action === 'REGRASP_TRIGGERED';

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-4">
      <div className="bg-[#121922] border border-[#26313e] rounded-[10px] max-w-3xl w-full p-4 sm:p-5 shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-[#26313e] pb-3 mb-3">
          <div className="flex items-center space-x-2.5">
            <span className={`px-2 py-0.5 rounded-[4px] text-[10px] font-mono font-bold uppercase ${
              cycle.color === 'yellow' ? 'bg-[#352e21] text-[#e9bf79]' :
              cycle.color === 'red' ? 'bg-[#38232c] text-[#f28d95]' :
              cycle.color === 'blue' ? 'bg-[#18212c] text-[#89b9ef]' :
              'bg-[#15352e] text-[#55dbb1]'
            }`}>
              {cycle.color} Duplo
            </span>
            <h3 className="text-sm font-semibold text-[#edf2f7] font-mono">{cycle.cycle_id} Visual Audit Detail</h3>
            <span className="text-[11px] text-[#8e9bae] font-mono tabular-nums">[{cycle.timestamp}]</span>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-[5px] bg-[#18212c] hover:bg-[#26313e] text-[#8e9bae] hover:text-[#edf2f7] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="space-y-4 overflow-y-auto pr-1">
          {/* 3-Way Image Inspector */}
          <div>
            <div className="text-[11px] font-medium text-[#8e9bae] uppercase tracking-wider mb-2">
              Multi-Layer Visual Evidence (Cloudinary Composited)
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {/* Raw */}
              <div className="bg-[#0b0f14] rounded-[6px] p-2 border border-[#26313e] flex flex-col">
                <div className="text-[10px] font-mono text-[#8e9bae] mb-1">01. Optical RGB Crop</div>
                <div className="aspect-square rounded overflow-hidden bg-black flex items-center justify-center">
                  <img src={cycle.raw_url} alt="Raw" className="w-full h-full object-cover" />
                </div>
              </div>

              {/* Heatmap */}
              <div className="bg-[#0b0f14] rounded-[6px] p-2 border border-[#26313e] flex flex-col">
                <div className="text-[10px] font-mono text-[#f28d95] mb-1">02. Anomalib v2.7.0 Heatmap</div>
                <div className="aspect-square rounded overflow-hidden bg-black flex items-center justify-center">
                  <img src={cycle.heatmap_url || cycle.composite_url} alt="Heatmap" className="w-full h-full object-cover" />
                </div>
              </div>

              {/* Composite */}
              <div className="bg-[#0b0f14] rounded-[6px] p-2 border border-[#55dbb1]/50 flex flex-col relative shadow-md shadow-[#55dbb1]/10">
                <div className="text-[10px] font-mono text-[#55dbb1] font-semibold mb-1 flex items-center justify-between">
                  <span>03. Composite Overlay</span>
                  <span className="text-[8.5px] uppercase">l_overlay</span>
                </div>
                <div className="aspect-square rounded overflow-hidden bg-black flex items-center justify-center">
                  <img src={cycle.composite_url || cycle.raw_url} alt="Composite" className="w-full h-full object-cover" />
                </div>
              </div>
            </div>
          </div>

          {/* Reasoning & Decision Card */}
          <div className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-[#b5c0ce] uppercase">
                Arbitrated Decision
              </span>
              <span className={`px-2 py-0.5 rounded-[4px] text-[10px] font-semibold ${
                isDefective ? 'bg-[#38232c] text-[#f28d95]' : isRegrasp ? 'bg-[#352e21] text-[#e9bf79]' : 'bg-[#15352e] text-[#55dbb1]'
              }`}>
                {cycle.action}
              </span>
            </div>

            <div className="text-[12px] text-[#edf2f7] leading-relaxed bg-[#18212c]/40 p-2.5 rounded-[4px] border border-[#26313e]/60">
              <span className="text-[#89b9ef] font-semibold mr-1.5">Nemotron Reasoning:</span>
              "{cycle.nemotron_reasoning}"
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-[11px]">
              <div className="bg-[#18212c] p-2 rounded-[4px]">
                <span className="text-[#8e9bae] text-[9.5px] block">Defect Label</span>
                <span className="font-semibold text-[#edf2f7]">{cycle.defect_label || 'Pristine'}</span>
              </div>
              <div className="bg-[#18212c] p-2 rounded-[4px]">
                <span className="text-[#8e9bae] text-[9.5px] block">Anomaly Score</span>
                <span className={`font-semibold ${isDefective ? 'text-[#f28d95]' : 'text-[#55dbb1]'}`}>
                  {cycle.anomaly_score?.toFixed(3)}
                </span>
              </div>
              <div className="bg-[#18212c] p-2 rounded-[4px]">
                <span className="text-[#8e9bae] text-[9.5px] block">Destination</span>
                <span className="font-semibold text-[#b5c0ce]">
                  {isDefective ? 'Bowl #2 (Reject)' : isRegrasp ? 'Turntable' : 'Bowl #1 (Accept)'}
                </span>
              </div>
              <div className="bg-[#18212c] p-2 rounded-[4px]">
                <span className="text-[#8e9bae] text-[9.5px] block">Total Latency</span>
                <span className="font-semibold text-[#55dbb1]">
                  {cycle.latencies?.total_ms || '35.9'} ms
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="mt-4 pt-3 border-t border-[#26313e] flex items-center justify-between text-[11px] text-[#8e9bae]">
          <span>Synced with LeRobot SO-101 Trajectory Buffer</span>
          <button
            onClick={onClose}
            className="px-3.5 py-1 bg-[#18212c] hover:bg-[#26313e] text-[#edf2f7] rounded-[5px] text-[11px] font-semibold transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
