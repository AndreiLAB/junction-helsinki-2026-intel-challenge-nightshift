import React, { useState } from 'react';
import { Cpu, Zap, Activity, Play, Radio, Gauge, Check, AlertOctagon, RotateCw } from 'lucide-react';

export default function IntelTelemetry({
  metrics,
  simulationRunning,
  onTriggerCycle,
  onToggleContinuousSimulation
}) {
  const [triggering, setTriggering] = useState(false);

  const handleSimulate = async (outcome) => {
    setTriggering(true);
    try {
      await onTriggerCycle(outcome);
    } finally {
      setTimeout(() => setTriggering(false), 400);
    }
  };

  const npu = metrics?.npu || { latency_ms: 9.4, utilization_pct: 74, power_watts: 4.8 };
  const igpu = metrics?.igpu || { latency_ms: 24.1, utilization_pct: 68, throughput_fps: 41.5 };
  const cpu = metrics?.cpu || { latency_ms: 2.1, utilization_pct: 28, jitter_us: 12.4 };
  const totalLatency = metrics?.total_pipeline_latency_ms || 35.6;

  return (
    <div className="bg-obsidian-900 border border-obsidian-border rounded-xl p-3.5 shadow-xl backdrop-blur-md flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between mb-2.5 border-b border-obsidian-border pb-2">
        <div className="flex items-center space-x-2">
          <Cpu className="w-4 h-4 text-intel-light" />
          <h2 className="text-xs font-bold tracking-tight text-white uppercase font-mono">
            Intel Core Ultra X9 388H (50-TOPS NPU • 12 Xe3 iGPU • CPU)
          </h2>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-intel-blue/20 text-intel-light border border-intel-blue/30 font-semibold uppercase">
            180 TOPS PLATFORM
          </span>
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-obsidian-800 text-slate-300 border border-slate-700/60">
            OpenVINO 2026.0
          </span>
        </div>
      </div>

      {/* Hardware Acceleration Cards (NPU, iGPU, CPU) */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 mb-2.5">
        {/* NPU (50 TOPS - Anomalib) */}
        <div className="bg-obsidian-950/80 border border-obsidian-border rounded-lg p-2.5 relative overflow-hidden group hover:border-intel-light/50 transition-colors">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-mono font-bold text-intel-light flex items-center space-x-1">
              <Zap className="w-3.5 h-3.5" />
              <span>NPU (50 TOPS)</span>
            </span>
            <span className="text-[9px] font-mono bg-emerald-500/10 text-emerald-400 px-1 py-0.2 rounded border border-emerald-500/20 whitespace-nowrap">
              {npu.power_watts || 4.8}W Sustained
            </span>
          </div>

          <div className="text-[10px] text-slate-400 font-medium truncate mb-1.5">
            Anomalib v2.7.0 PatchCore
          </div>

          <div className="flex items-baseline justify-between pt-1 border-t border-obsidian-border/70 font-mono">
            <div>
              <div className="text-[9px] text-slate-500 uppercase">Latency</div>
              <div className="flex items-baseline gap-1 whitespace-nowrap">
                <span className="text-base font-bold text-white tabular-nums tracking-tight">
                  {npu.latency_ms?.toFixed(1) || 9.4}
                </span>
                <span className="text-[11px] text-slate-400 font-mono">ms</span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-[9px] text-slate-500 uppercase">Load</div>
              <div className="text-xs font-bold text-intel-light tabular-nums">
                {npu.utilization_pct?.toFixed(0) || 74}%
              </div>
            </div>
          </div>
          <div className="text-[8.5px] text-slate-500 font-mono mt-1 truncate">OpenVINO NPU Plugin • Zero CPU Overhead</div>
        </div>

        {/* iGPU (12 Xe3 Cores - VLA) */}
        <div className="bg-obsidian-950/80 border border-obsidian-border rounded-lg p-2.5 relative overflow-hidden group hover:border-cyan-400/50 transition-colors">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-mono font-bold text-cyan-400 flex items-center space-x-1">
              <Activity className="w-3.5 h-3.5" />
              <span>12 Xe3 Cores</span>
            </span>
            <span className="text-[9px] font-mono bg-cyan-500/10 text-cyan-400 px-1 py-0.2 rounded border border-cyan-500/20 whitespace-nowrap">
              {igpu.throughput_fps || 41.5} FPS
            </span>
          </div>

          <div className="text-[10px] text-slate-400 font-medium truncate mb-1.5">
            SmolVLA / ACT Policy
          </div>

          <div className="flex items-baseline justify-between pt-1 border-t border-obsidian-border/70 font-mono">
            <div>
              <div className="text-[9px] text-slate-500 uppercase">Latency</div>
              <div className="flex items-baseline gap-1 whitespace-nowrap">
                <span className="text-base font-bold text-white tabular-nums tracking-tight">
                  {igpu.latency_ms?.toFixed(1) || 24.1}
                </span>
                <span className="text-[11px] text-slate-400 font-mono">ms</span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-[9px] text-slate-500 uppercase">Precision</div>
              <div className="text-xs font-bold text-cyan-300">
                FP16 / oneAPI
              </div>
            </div>
          </div>
          <div className="text-[8.5px] text-slate-500 font-mono mt-1 truncate">Physical AI Studio Action Chunking</div>
        </div>

        {/* CPU (Deterministic Control) */}
        <div className="bg-obsidian-950/80 border border-obsidian-border rounded-lg p-2.5 relative overflow-hidden group hover:border-purple-400/50 transition-colors">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-mono font-bold text-purple-400 flex items-center space-x-1">
              <Gauge className="w-3.5 h-3.5" />
              <span>Deterministic CPU</span>
            </span>
            <span className="text-[9px] font-mono bg-purple-500/10 text-purple-300 px-1 py-0.2 rounded border border-purple-500/20 whitespace-nowrap">
              Jitter &lt; 15µs
            </span>
          </div>

          <div className="text-[10px] text-slate-400 font-medium truncate mb-1.5">
            Intel TCC + TSN Kinematics
          </div>

          <div className="flex items-baseline justify-between pt-1 border-t border-obsidian-border/70 font-mono">
            <div>
              <div className="text-[9px] text-slate-500 uppercase">Control Loop</div>
              <div className="flex items-baseline gap-1 whitespace-nowrap">
                <span className="text-base font-bold text-white tabular-nums tracking-tight">
                  {cpu.latency_ms?.toFixed(1) || 2.1}
                </span>
                <span className="text-[11px] text-slate-400 font-mono">ms</span>
              </div>
            </div>
            <div className="text-right">
              <div className="text-[9px] text-slate-500 uppercase">Thermals</div>
              <div className="text-xs font-bold text-purple-300 tabular-nums">
                {cpu.temp_c || 52}°C
              </div>
            </div>
          </div>
          <div className="text-[8.5px] text-slate-500 font-mono mt-1 truncate">SO-101 Follower Arm Trajectory Loop</div>
        </div>
      </div>

      {/* Latency Pipeline Bar & Counters with fixed whitespace */}
      <div className="bg-obsidian-950/90 rounded-lg p-2.5 border border-obsidian-border mb-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono mb-1.5">
          <div className="flex items-center gap-1.5 whitespace-nowrap">
            <span className="text-slate-400 text-xs">Total Decision Latency:</span>
            <span className="text-sm font-bold text-intel-light font-mono tabular-nums whitespace-nowrap">
              {totalLatency.toFixed(1)} ms
            </span>
            <span className="text-[10px] text-slate-500 font-mono tabular-nums hidden sm:inline">
              (NPU 9.4 + GPU 24.1 + CPU 2.1)
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs font-mono tabular-nums">
            <span className="text-emerald-400 whitespace-nowrap">Accepted: <b>{metrics?.perfect_count ?? 0}</b></span>
            <span className="text-rose-400 whitespace-nowrap">Defective: <b>{metrics?.defective_count ?? 0}</b></span>
            <span className="text-amber-400 whitespace-nowrap">Re-grasps: <b>{metrics?.regrasp_count ?? 0}</b></span>
          </div>
        </div>

        {/* Proportional Stacked Latency Bar */}
        <div className="w-full h-1.5 rounded-full overflow-hidden flex bg-obsidian-900 border border-obsidian-border">
          <div style={{ width: '26%' }} className="bg-intel-light" title="NPU ~9.4ms (26%)" />
          <div style={{ width: '68%' }} className="bg-cyan-500" title="iGPU ~24.1ms (68%)" />
          <div style={{ width: '6%' }} className="bg-purple-500" title="CPU ~2.1ms (6%)" />
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-obsidian-border">
        <div className="flex items-center space-x-1.5">
          <button
            onClick={() => handleSimulate('PERFECT')}
            disabled={triggering}
            className="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium bg-emerald-600/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-600/30 active:scale-95 transition-all"
          >
            <Check className="w-3.5 h-3.5 text-emerald-400" />
            <span>Simulate Perfect</span>
          </button>

          <button
            onClick={() => handleSimulate('DEFECTIVE')}
            disabled={triggering}
            className="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium bg-rose-600/20 text-rose-300 border border-rose-500/30 hover:bg-rose-600/30 active:scale-95 transition-all"
          >
            <AlertOctagon className="w-3.5 h-3.5 text-rose-400" />
            <span>Simulate Defect</span>
          </button>

          <button
            onClick={() => handleSimulate('REGRASP')}
            disabled={triggering}
            className="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium bg-amber-600/20 text-amber-300 border border-amber-500/30 hover:bg-amber-600/30 active:scale-95 transition-all"
          >
            <RotateCw className="w-3.5 h-3.5 text-amber-400" />
            <span>Simulate Re-grasp</span>
          </button>
        </div>

        {/* Live Auto Pitch Switch */}
        <button
          onClick={onToggleContinuousSimulation}
          className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all border ${
            simulationRunning
              ? 'bg-intel-blue text-white border-intel-light shadow-glow-intel animate-pulse'
              : 'bg-obsidian-800 text-slate-300 border-obsidian-border hover:bg-obsidian-700'
          }`}
        >
          <Radio className={`w-3.5 h-3.5 ${simulationRunning ? 'text-white' : 'text-slate-400'}`} />
          <span>{simulationRunning ? 'Pitch Mode Active' : 'Start Auto-Cycle Stream'}</span>
        </button>
      </div>
    </div>
  );
}
