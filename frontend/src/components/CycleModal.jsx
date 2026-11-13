import React from 'react';
import { X, Layers, Cpu, Zap, Activity, ShieldAlert, CheckCircle, RotateCcw, ArrowRight } from 'lucide-react';

export default function CycleModal({ cycle, onClose }) {
  if (!cycle) return null;

  const isDefective = cycle.action === 'DEFECTIVE_BOWL';
  const isRegrasp = cycle.action === 'REGRASP_TRIGGERED';

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-4">
      <div className="bg-obsidian-900 border border-slate-700/80 rounded-2xl max-w-3xl w-full p-4 sm:p-5 shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-obsidian-border pb-3 mb-3">
          <div className="flex items-center space-x-2.5">
            <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
              cycle.color === 'yellow' ? 'bg-amber-500/20 text-amber-300' :
              cycle.color === 'red' ? 'bg-rose-500/20 text-rose-300' :
              cycle.color === 'blue' ? 'bg-blue-500/20 text-blue-300' :
              'bg-obsidian-800 text-slate-300'
            }`}>
              {cycle.color} Duplo
            </span>
            <h3 className="text-sm font-bold text-white font-mono">{cycle.cycle_id} Visual Audit Detail</h3>
            <span className="text-[11px] text-slate-400 font-mono tabular-nums">[{cycle.timestamp}]</span>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-lg bg-obsidian-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="space-y-4 overflow-y-auto pr-1">
          {/* 3-Way Image Inspector */}
          <div>
            <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-1.5">
              Multi-Layer Visual Evidence (Cloudinary Composited)
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {/* Raw */}
              <div className="bg-obsidian-950 rounded-lg p-2 border border-obsidian-border flex flex-col">
                <div className="text-[9.5px] font-mono text-slate-400 mb-1">01. Optical RGB Crop</div>
                <div className="aspect-square rounded overflow-hidden bg-black flex items-center justify-center">
                  <img src={cycle.raw_url} alt="Raw" className="w-full h-full object-cover" />
                </div>
              </div>

              {/* Heatmap */}
              <div className="bg-obsidian-950 rounded-lg p-2 border border-obsidian-border flex flex-col">
                <div className="text-[9.5px] font-mono text-rose-400 mb-1">02. Anomalib v2.7.0 Heatmap</div>
                <div className="aspect-square rounded overflow-hidden bg-black flex items-center justify-center">
                  <img src={cycle.heatmap_url || cycle.composite_url} alt="Heatmap" className="w-full h-full object-cover" />
                </div>
              </div>

              {/* Composite */}
              <div className="bg-obsidian-950 rounded-lg p-2 border border-obsidian-border flex flex-col">
                <div className="text-[9.5px] font-mono text-intel-light mb-1">03. Cloudinary Composite (o_45)</div>
                <div className="aspect-square rounded overflow-hidden bg-black flex items-center justify-center">
                  <img src={cycle.composite_url || cycle.raw_url} alt="Composite" className="w-full h-full object-cover" />
                </div>
              </div>
            </div>
          </div>

          {/* Decision & Root Cause Reasoning */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="bg-obsidian-950/80 rounded-lg p-3 border border-obsidian-border">
              <div className="text-[11px] font-mono text-slate-400 uppercase mb-1.5">Robotic Manipulation Decision</div>
              <div className="space-y-1.5 text-xs font-mono">
                <div className="flex justify-between border-b border-obsidian-border/60 pb-1">
                  <span className="text-slate-500">Defect Classification:</span>
                  <span className="text-white font-bold">{cycle.defect_label}</span>
                </div>
                <div className="flex justify-between border-b border-obsidian-border/60 pb-1">
                  <span className="text-slate-500">Anomalib Score:</span>
                  <span className={`font-bold tabular-nums ${isDefective ? 'text-rose-400' : isRegrasp ? 'text-amber-400' : 'text-emerald-400'}`}>
                    {cycle.anomaly_score?.toFixed(3)}
                  </span>
                </div>
                <div className="flex justify-between border-b border-obsidian-border/60 pb-1">
                  <span className="text-slate-500">Target Destination:</span>
                  <span className="text-intel-light font-bold">{cycle.destination}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Action Committed:</span>
                  <span className="text-white font-bold">{cycle.action}</span>
                </div>
              </div>
            </div>

            <div className="bg-obsidian-950/80 rounded-lg p-3 border border-obsidian-border">
              <div className="text-[11px] font-mono text-slate-400 uppercase mb-1.5">Nemotron Root-Cause Analysis</div>
              <p className="text-xs text-slate-300 italic leading-relaxed font-sans">
                "{cycle.root_cause_reasoning}"
              </p>
            </div>
          </div>

          {/* OpenVINO Heterogeneous Execution Trace */}
          <div className="bg-obsidian-950/80 rounded-lg p-3 border border-obsidian-border">
            <div className="text-[11px] font-mono text-slate-400 uppercase mb-1.5">
              OpenVINO™ Heterogeneous Compute Dispatch
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs font-mono">
              <div className="p-2 rounded bg-obsidian-900 border border-obsidian-border">
                <div className="text-slate-500 text-[9.5px]">Anomalib Inference</div>
                <div className="text-intel-light font-bold text-[11px] mt-0.5">Intel NPU (50 TOPS)</div>
                <div className="text-slate-300 text-[10px] mt-0.5 tabular-nums">{cycle.latencies?.npu_anomalib_ms || 9.4} ms</div>
              </div>
              <div className="p-2 rounded bg-obsidian-900 border border-obsidian-border">
                <div className="text-slate-500 text-[9.5px]">SmolVLA Task Policy</div>
                <div className="text-cyan-400 font-bold text-[11px] mt-0.5">12 Xe3 Cores (iGPU)</div>
                <div className="text-slate-300 text-[10px] mt-0.5 tabular-nums">{cycle.latencies?.igpu_vla_ms || 24.1} ms</div>
              </div>
              <div className="p-2 rounded bg-obsidian-900 border border-obsidian-border">
                <div className="text-slate-500 text-[9.5px]">Deterministic Kinematics</div>
                <div className="text-purple-400 font-bold text-[11px] mt-0.5">Intel TCC (CPU)</div>
                <div className="text-slate-300 text-[10px] mt-0.5 tabular-nums">{cycle.latencies?.cpu_control_ms || 2.1} ms</div>
              </div>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="border-t border-obsidian-border pt-2.5 mt-3 flex justify-end">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-lg bg-obsidian-800 hover:bg-slate-700 text-white font-mono text-xs font-medium"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
