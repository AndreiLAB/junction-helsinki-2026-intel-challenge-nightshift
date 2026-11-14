import React, { useState } from 'react';
import { Cpu, Gauge } from 'lucide-react';

function getEvidenceStyle(evidence) {
  const ev = (evidence || 'MOCK').toUpperCase();
  if (ev === 'REAL') return 'bg-[#15352e] text-[#55dbb1] border-[#55dbb1]/35';
  if (ev === 'REPLAY') return 'bg-[#18212c] text-[#89b9ef] border-[#89b9ef]/35';
  return 'bg-[#352e21]/60 text-[#e9bf79] border-[#e9bf79]/30';
}

function getDeviceStyle(device) {
  const d = (device || 'NPU').toUpperCase();
  if (d.includes('NPU')) return 'text-[#55dbb1] bg-[#15352e]/70 border-[#55dbb1]/30';
  if (d.includes('GPU')) return 'text-[#89b9ef] bg-[#18212c] border-[#89b9ef]/30';
  return 'text-[#c4a7ea] bg-[#18212c] border-[#c4a7ea]/30';
}

export default function IntelTelemetry({
  metrics,
  benchmarks = [],
  currentCycle,
  expanded = false,
  simulationRunning,
  onTriggerCycle,
}) {
  const [triggering, setTriggering] = useState(false);
  const [panelTab, setPanelTab] = useState('live'); // 'live' | 'bench'

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
  const totalLatency = Number(metrics?.total_pipeline_latency_ms || 35.9);

  const cycleS =
    typeof currentCycle?.cycle_s === 'number'
      ? currentCycle.cycle_s
      : typeof metrics?.cycle_s === 'number'
      ? metrics.cycle_s
      : null;

  const activeDeviceInfo = [
    currentCycle?.model || 'patchcore_256',
    currentCycle?.precision || 'INT8',
    currentCycle?.device || 'NPU',
  ]
    .filter(Boolean)
    .join(' · ');

  // Segmented bar calculation
  const totalMs = (npu.latency_ms || 9.7) + (igpu.latency_ms || 24.2) + (cpu.latency_ms || 2.0);
  const npuPct = ((npu.latency_ms || 9.7) / totalMs) * 100;
  const igpuPct = ((igpu.latency_ms || 24.2) / totalMs) * 100;
  const cpuPct = ((cpu.latency_ms || 2.0) / totalMs) * 100;

  return (
    <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-4 flex flex-col justify-between h-full">
      {/* Header */}
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#26313e]">
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-[#89b9ef]" />
            <div>
              <h2 className="text-[16px] font-semibold text-[#edf2f7] leading-tight">
                Edge &amp; OpenVINO
              </h2>
              <div className="text-[11px] text-[#8e9bae] leading-tight mt-0.5">
                Core Ultra Series · NPU / iGPU / CPU
              </div>
            </div>
          </div>

          {/* Live Loop vs Bench Matrix Toggle */}
          <div className="bg-[#0b0f14] border border-[#26313e] rounded-[5px] p-0.5 flex items-center space-x-0.5">
            <button
              onClick={() => setPanelTab('live')}
              className={`px-2.5 py-1 rounded-[4px] text-[10px] font-medium transition-colors ${
                panelTab === 'live'
                  ? 'bg-[#18212c] text-[#edf2f7]'
                  : 'text-[#8e9bae] hover:text-[#edf2f7]'
              }`}
            >
              Live Loop
            </button>
            <button
              onClick={() => setPanelTab('bench')}
              className={`px-2.5 py-1 rounded-[4px] text-[10px] font-medium transition-colors flex items-center space-x-1 ${
                panelTab === 'bench'
                  ? 'bg-[#18212c] text-[#edf2f7]'
                  : 'text-[#8e9bae] hover:text-[#edf2f7]'
              }`}
            >
              <span>Bench Matrix</span>
              <span className="font-mono text-[9.5px] text-[#55dbb1]">
                ({benchmarks.length})
              </span>
            </button>
          </div>
        </div>

        {panelTab === 'live' ? (
          <>
            {/* Telemetry Rows */}
            <div className="py-1.5 divide-y divide-[#26313e]">
              {/* NPU */}
              <div className="py-2.5 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-[47px] h-[27px] rounded-[5px] bg-[#18212c] border border-[#55dbb1]/25 flex items-center justify-center shrink-0">
                    <span className="text-[10px] font-semibold text-[#55dbb1]">NPU</span>
                  </div>
                  <div>
                    <div className="text-[12px] font-medium text-[#b5c0ce] leading-tight">
                      Anomalib PatchCore
                    </div>
                    <div className="text-[10px] text-[#8e9bae] leading-tight mt-0.5 font-mono">
                      {activeDeviceInfo} · {npu.utilization_pct?.toFixed(0) || 74}%
                    </div>
                  </div>
                </div>

                <div className="flex items-baseline space-x-1 shrink-0">
                  <span className="text-[21px] font-semibold text-[#edf2f7] tabular-nums tracking-tight">
                    {(currentCycle?.latency_ms ?? npu.latency_ms ?? 9.7).toFixed(1)}
                  </span>
                  <span className="text-[10px] text-[#8e9bae] font-normal">ms</span>
                </div>
              </div>

              {/* iGPU */}
              <div className="py-2.5 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-[47px] h-[27px] rounded-[5px] bg-[#18212c] border border-[#89b9ef]/25 flex items-center justify-center shrink-0">
                    <span className="text-[10px] font-semibold text-[#89b9ef]">iGPU</span>
                  </div>
                  <div>
                    <div className="text-[12px] font-medium text-[#b5c0ce] leading-tight">
                      SmolVLA / ACT policy
                    </div>
                    <div className="text-[10px] text-[#8e9bae] leading-tight mt-0.5 font-mono">
                      FP16 · {igpu.throughput_fps?.toFixed(1) || '41.5'} fps
                    </div>
                  </div>
                </div>

                <div className="flex items-baseline space-x-1 shrink-0">
                  <span className="text-[21px] font-semibold text-[#edf2f7] tabular-nums tracking-tight">
                    {igpu.latency_ms?.toFixed(1) || '24.2'}
                  </span>
                  <span className="text-[10px] text-[#8e9bae] font-normal">ms</span>
                </div>
              </div>

              {/* CPU */}
              <div className="py-2.5 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-[47px] h-[27px] rounded-[5px] bg-[#18212c] border border-[#c4a7ea]/25 flex items-center justify-center shrink-0">
                    <span className="text-[10px] font-semibold text-[#c4a7ea]">CPU</span>
                  </div>
                  <div>
                    <div className="text-[12px] font-medium text-[#b5c0ce] leading-tight">
                      Cell FSM &amp; IK control
                    </div>
                    <div className="text-[10px] text-[#8e9bae] leading-tight mt-0.5 font-mono">
                      30 Hz servo · jitter &lt; 15 µs
                    </div>
                  </div>
                </div>

                <div className="flex items-baseline space-x-1 shrink-0">
                  <span className="text-[21px] font-semibold text-[#edf2f7] tabular-nums tracking-tight">
                    {cpu.latency_ms?.toFixed(1) || '2.0'}
                  </span>
                  <span className="text-[10px] text-[#8e9bae] font-normal">ms</span>
                </div>
              </div>
            </div>

            {/* Total Decision Latency + Seconds/Brick Card */}
            <div className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-3 my-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-[#8e9bae]">Total decision latency</span>
                <div className="text-right flex items-center space-x-2">
                  {cycleS !== null && (
                    <span className="text-[11px] font-mono font-semibold text-[#89b9ef] bg-[#18212c] px-2 py-0.5 rounded">
                      {cycleS.toFixed(1)}s / brick
                    </span>
                  )}
                  <span className="text-[12px] font-medium text-[#55dbb1]">
                    {npu.power_watts || 4.8} W
                  </span>
                </div>
              </div>

              <div className="flex items-baseline space-x-1 my-1">
                <span className="text-[28px] font-semibold text-[#edf2f7] tabular-nums tracking-tight leading-none">
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
          </>
        ) : (
          /* OpenVINO Benchmark Matrix (reports/bench/*.json) */
          <div className="py-2.5 space-y-2">
            <div className="flex items-center justify-between text-[10px] font-mono text-[#8e9bae]">
              <span className="flex items-center space-x-1">
                <Gauge className="w-3 h-3 text-[#55dbb1]" />
                <span>~/duplo-cell/reports/bench/*.json</span>
              </span>
              <span>p50 / p95 · FPS · cache</span>
            </div>

            {benchmarks.length === 0 ? (
              <div className="text-[11px] text-[#8e9bae] bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-4 text-center">
                No OpenVINO benchmark records ingested yet.
              </div>
            ) : (
              <div
                className={`space-y-1.5 overflow-y-auto pr-1 ${
                  expanded ? 'max-h-[420px]' : 'max-h-[250px]'
                }`}
              >
                {benchmarks.map((b, idx) => {
                  const key = b.bench_key || `${b.model}-${b.device}-${b.precision}-${idx}`;
                  const p50 = Number(b.latency_ms_p50 ?? 0);
                  const p95 = Number(b.latency_ms_p95 ?? 0);
                  const fps = Number(b.fps ?? 0);
                  const compileS = b.compile_s !== undefined && b.compile_s !== null ? Number(b.compile_s) : null;
                  const cachedS =
                    b.cached_compile_s !== undefined && b.cached_compile_s !== null
                      ? Number(b.cached_compile_s)
                      : null;

                  return (
                    <div
                      key={key}
                      className="bg-[#0b0f14] border border-[#26313e]/90 rounded-[6px] px-2.5 py-2 space-y-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center space-x-1.5 min-w-0">
                          <span className="text-[11px] font-mono font-semibold text-[#edf2f7] truncate">
                            {b.model}
                          </span>
                          <span
                            className={`px-1.5 py-0.5 rounded-[3px] border text-[9.5px] font-mono font-semibold shrink-0 ${getDeviceStyle(
                              b.device
                            )}`}
                          >
                            {b.device} · {b.precision}
                          </span>
                        </div>

                        <span
                          className={`px-1.5 py-0.5 rounded-[3px] border text-[9px] font-mono font-semibold shrink-0 ${getEvidenceStyle(
                            b.evidence
                          )}`}
                        >
                          {(b.evidence || 'MOCK').toUpperCase()}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-[#8e9bae]">
                        <span>
                          p50 <strong className="text-[#55dbb1]">{p50.toFixed(1)}ms</strong> / p95{' '}
                          <span className="text-[#b5c0ce]">{p95.toFixed(1)}ms</span>
                        </span>
                        <span>
                          <strong className="text-[#89b9ef]">{fps.toFixed(1)}</strong> fps
                        </span>
                        {compileS !== null && cachedS !== null && (
                          <span title="Cold compile -> OpenVINO cached compile">
                            cache {compileS.toFixed(2)}s→
                            <strong className="text-[#55dbb1]">{cachedS.toFixed(2)}s</strong>
                          </span>
                        )}
                        {b.quality !== undefined && b.quality !== null && (
                          <span className="text-[#e9bf79]">
                            {b.quality_metric || 'AUROC'} {Number(b.quality).toFixed(3)}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
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
