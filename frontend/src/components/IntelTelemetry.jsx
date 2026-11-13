import React, { useState } from 'react';
import { Cpu, Zap, Activity, ShieldCheck, Play } from 'lucide-react';

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
      setTimeout(() => setTriggering(false), 300);
    }
  };

  const npu = metrics?.npu || { latency_ms: 9.7, utilization_pct: 74, power_watts: 4.8 };
  const igpu = metrics?.igpu || { latency_ms: 24.2, utilization_pct: 68, throughput_fps: 41.5 };
  const cpu = metrics?.cpu || { latency_ms: 2.0, utilization_pct: 28, jitter_us: 12.4 };
  const totalLatency = metrics?.total_pipeline_latency_ms || 35.9;

  // Segmented bar calculation
  const totalMs = (npu.latency_ms || 9.7) + (igpu.latency_ms || 24.2) + (cpu.latency_ms || 2.0);
  const npuPct = ((npu.latency_ms || 9.7) / totalMs) * 100;
  const igpuPct = ((igpu.latency_ms || 24.2) / totalMs) * 100;
  const cpuPct = ((cpu.latency_ms || 2.0) / totalMs) * 100;

  return (
    <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-4 flex flex-col justify-between h-full">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-[#26313e]">
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-[#89b9ef]" />
            <div>
              <h2 className="text-[16px] font-semibold text-[#edf2f7] leading-tight">
                Edge performance
              </h2>
              <div className="text-[11px] text-[#8e9bae] leading-tight mt-0.5">
                Intel Core Ultra X9 388H
              </div>
            </div>
          </div>
          <div className="bg-[#18212c] px-2.5 py-1 rounded-[5px] border border-[#89b9ef]/20">
            <span className="text-[10px] font-medium text-[#89b9ef] tracking-wide">
              180 TOPS
            </span>
          </div>
        </div>

        {/* Telemetry Rows */}
        <div className="py-2 divide-y divide-[#26313e]">
          {/* NPU */}
          <div className="py-2.5 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-[47px] h-[27px] rounded-[5px] bg-[#18212c] flex items-center justify-center shrink-0">
                <span className="text-[10px] font-semibold text-[#55dbb1]">NPU</span>
              </div>
              <div>
                <div className="text-[12px] font-medium text-[#b5c0ce] leading-tight">
                  Anomalib PatchCore
                </div>
                <div className="text-[10px] text-[#8e9bae] leading-tight mt-0.5">
                  50 TOPS · {npu.utilization_pct?.toFixed(0) || 74}% load
                </div>
              </div>
            </div>

            <div className="flex items-baseline space-x-1 shrink-0">
              <span className="text-[22px] font-semibold text-[#edf2f7] tabular-nums tracking-tight">
                {npu.latency_ms?.toFixed(1) || '9.7'}
              </span>
              <span className="text-[10px] text-[#8e9bae] font-normal">ms</span>
            </div>
          </div>

          {/* iGPU */}
          <div className="py-2.5 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-[47px] h-[27px] rounded-[5px] bg-[#18212c] flex items-center justify-center shrink-0">
                <span className="text-[10px] font-semibold text-[#89b9ef]">iGPU</span>
              </div>
              <div>
                <div className="text-[12px] font-medium text-[#b5c0ce] leading-tight">
                  SmolVLA / ACT policy
                </div>
                <div className="text-[10px] text-[#8e9bae] leading-tight mt-0.5">
                  12 Xe3 cores · {igpu.throughput_fps?.toFixed(1) || '41.5'} fps
                </div>
              </div>
            </div>

            <div className="flex items-baseline space-x-1 shrink-0">
              <span className="text-[22px] font-semibold text-[#edf2f7] tabular-nums tracking-tight">
                {igpu.latency_ms?.toFixed(1) || '24.2'}
              </span>
              <span className="text-[10px] text-[#8e9bae] font-normal">ms</span>
            </div>
          </div>

          {/* CPU */}
          <div className="py-2.5 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-[47px] h-[27px] rounded-[5px] bg-[#18212c] flex items-center justify-center shrink-0">
                <span className="text-[10px] font-semibold text-[#c4a7ea]">CPU</span>
              </div>
              <div>
                <div className="text-[12px] font-medium text-[#b5c0ce] leading-tight">
                  Deterministic control
                </div>
                <div className="text-[10px] text-[#8e9bae] leading-tight mt-0.5">
                  52°C · jitter &lt; 15 µs
                </div>
              </div>
            </div>

            <div className="flex items-baseline space-x-1 shrink-0">
              <span className="text-[22px] font-semibold text-[#edf2f7] tabular-nums tracking-tight">
                {cpu.latency_ms?.toFixed(1) || '2.0'}
              </span>
              <span className="text-[10px] text-[#8e9bae] font-normal">ms</span>
            </div>
          </div>
        </div>

        {/* Total Decision Latency Card */}
        <div className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-3 my-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-[#8e9bae]">Total decision latency</span>
            <div className="text-right">
              <span className="text-[13px] font-medium text-[#55dbb1]">
                {npu.power_watts || 4.8} W
              </span>
              <span className="text-[10px] text-[#8e9bae] ml-1.5">NPU sustained</span>
            </div>
          </div>

          <div className="flex items-baseline space-x-1 my-1">
            <span className="text-[30px] font-semibold text-[#edf2f7] tabular-nums tracking-tight leading-none">
              {totalLatency.toFixed(1)}
            </span>
            <span className="text-[12px] text-[#8e9bae]">ms</span>
          </div>

          {/* Segmented Latency Bar */}
          <div className="h-[4px] w-full flex rounded-[1px] overflow-hidden gap-[2px] mt-2">
            <div
              style={{ width: `${npuPct}%` }}
              className="bg-[#55dbb1] rounded-[1px] transition-all"
              title={`NPU: ${npu.latency_ms?.toFixed(1)}ms`}
            />
            <div
              style={{ width: `${igpuPct}%` }}
              className="bg-[#89b9ef] rounded-[1px] transition-all"
              title={`iGPU: ${igpu.latency_ms?.toFixed(1)}ms`}
            />
            <div
              style={{ width: `${cpuPct}%` }}
              className="bg-[#c4a7ea] rounded-[1px] transition-all"
              title={`CPU: ${cpu.latency_ms?.toFixed(1)}ms`}
            />
          </div>
        </div>
      </div>

      {/* SIMULATE Action Controls */}
      <div className="pt-2 border-t border-[#26313e]/70 flex items-center justify-between gap-2">
        <span className="text-[9px] font-medium text-[#8e9bae] uppercase tracking-wider shrink-0">
          SIMULATE
        </span>

        <div className="grid grid-cols-3 gap-2 flex-1 max-w-[340px]">
          <button
            onClick={() => handleSimulate('PERFECT_BOWL')}
            disabled={triggering}
            className="h-[32px] rounded-[5px] bg-[#18212c] border border-[#26313e] hover:border-[#55dbb1]/70 text-[#55dbb1] text-[11px] font-medium transition-all active:scale-95 flex items-center justify-center space-x-1"
          >
            <span>Perfect</span>
          </button>

          <button
            onClick={() => handleSimulate('DEFECTIVE_BOWL')}
            disabled={triggering}
            className="h-[32px] rounded-[5px] bg-[#18212c] border border-[#26313e] hover:border-[#f28d95]/70 text-[#f28d95] text-[11px] font-medium transition-all active:scale-95 flex items-center justify-center space-x-1"
          >
            <span>Defect</span>
          </button>

          <button
            onClick={() => handleSimulate('REGRASP_TRIGGERED')}
            disabled={triggering}
            className="h-[32px] rounded-[5px] bg-[#18212c] border border-[#26313e] hover:border-[#e9bf79]/70 text-[#e9bf79] text-[11px] font-medium transition-all active:scale-95 flex items-center justify-center space-x-1"
          >
            <span>Re-grasp</span>
          </button>
        </div>
      </div>
    </div>
  );
}
