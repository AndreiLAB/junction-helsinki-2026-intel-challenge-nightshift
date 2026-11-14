import React from 'react';
import { motion } from 'framer-motion';
import { Cpu, ArrowUpRight, Gauge } from 'lucide-react';

export default function IntelTelemetry({
  metrics,
  benchmarks = [],
  currentCycle,
  expanded = false,
  onOpenBenchTab,
}) {
  const npu = metrics?.npu || { latency_ms: 9.3, utilization_pct: 74, power_watts: 4.8 };
  const igpu = metrics?.igpu || { latency_ms: 24.0, utilization_pct: 68, throughput_fps: 41.7 };
  const cpu = metrics?.cpu || { latency_ms: 1.9, utilization_pct: 28, jitter_us: 12.4 };

  const npuMs = Number(currentCycle?.latency_ms ?? npu.latency_ms ?? 9.3);
  const igpuMs = Number(igpu.latency_ms ?? 24.0);
  const cpuMs = Number(cpu.latency_ms ?? 1.9);
  const totalMs = npuMs + igpuMs + cpuMs;

  const maxBenchMs = Math.max(40, ...benchmarks.map((b) => Number(b.latency_ms_p50 || 0)));

  if (expanded) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="glass-panel rounded-xl p-5 space-y-5"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#15352e]/80 border border-[#55dbb1]/30 flex items-center justify-center text-[#55dbb1]">
              <Gauge className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-[16px] font-semibold text-[#edf2f7]">
                OpenVINO Device &amp; Precision Benchmarks
              </h2>
              <p className="text-[12px] text-[#8e9bae]">
                Core Ultra Series 3 · Auto-synced from ~/duplo-cell/reports/bench/*.json
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 font-mono text-[11px] text-[#8e9bae]">
            <span>NPU {npuMs.toFixed(1)}ms</span>
            <span>·</span>
            <span>iGPU {igpuMs.toFixed(1)}ms</span>
            <span>·</span>
            <span>CPU {cpuMs.toFixed(1)}ms</span>
          </div>
        </div>

        {benchmarks.length === 0 ? (
          <div className="py-12 text-center text-[13px] text-[#8e9bae]">
            No OpenVINO benchmark records synced yet.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {benchmarks.map((b, idx) => {
              const p50 = Number(b.latency_ms_p50 ?? 0);
              const p95 = Number(b.latency_ms_p95 ?? 0);
              const fps = Number(b.fps ?? 0);
              const barPct = Math.min(100, Math.max(8, (p50 / maxBenchMs) * 100));
              const dev = (b.device || 'NPU').toUpperCase();
              const barColor = dev.includes('NPU')
                ? '#55dbb1'
                : dev.includes('GPU')
                ? '#89b9ef'
                : '#c4a7ea';
              const ev = (b.evidence || 'MOCK').toUpperCase();

              return (
                <motion.div
                  key={b.bench_key || `${b.model}-${dev}-${b.precision}-${idx}`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  className="glass-subtle rounded-xl p-4 space-y-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-[13px] font-mono font-semibold text-[#edf2f7] truncate">
                        {b.model}
                      </span>
                      <span
                        className="px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold border border-white/[0.08]"
                        style={{ color: barColor }}
                      >
                        {dev} · {b.precision}
                      </span>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[9.5px] font-mono font-semibold border ${
                        ev === 'REAL'
                          ? 'bg-[#15352e]/70 text-[#55dbb1] border-[#55dbb1]/30'
                          : ev === 'REPLAY'
                          ? 'bg-[#18212c] text-[#89b9ef] border-[#89b9ef]/30'
                          : 'bg-white/[0.04] text-[#8e9bae] border-white/[0.08]'
                      }`}
                    >
                      {ev}
                    </span>
                  </div>

                  {/* Animated Latency Race Bar */}
                  <div className="space-y-1">
                    <div className="flex justify-between font-mono text-[11px]">
                      <span className="text-[#8e9bae]">
                        p50 <strong className="text-[#edf2f7]">{p50.toFixed(1)} ms</strong> · p95{' '}
                        {p95.toFixed(1)} ms
                      </span>
                      <span style={{ color: barColor }} className="font-semibold">
                        {fps.toFixed(1)} FPS
                      </span>
                    </div>
                    <div className="h-2 w-full bg-white/[0.05] rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${barPct}%` }}
                        transition={{ type: 'spring', stiffness: 110, damping: 18, delay: 0.1 + idx * 0.05 }}
                        className="h-full rounded-full"
                        style={{ backgroundColor: barColor }}
                      />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 text-[10.5px] font-mono text-[#8e9bae]">
                    {b.compile_s != null && b.cached_compile_s != null && (
                      <span>
                        Compile: {Number(b.compile_s).toFixed(2)}s →{' '}
                        <strong className="text-[#55dbb1]">{Number(b.cached_compile_s).toFixed(2)}s</strong>{' '}
                        cached
                      </span>
                    )}
                    {b.quality != null && (
                      <span className="text-[#e9bf79]">
                        {b.quality_metric || 'quality'}: {Number(b.quality).toFixed(3)}
                      </span>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </motion.div>
    );
  }

  // Compact Cockpit Card
  const lanes = [
    { label: 'NPU', sub: `${currentCycle?.model || 'patchcore_256'} · ${currentCycle?.precision || 'INT8'}`, ms: npuMs, color: '#55dbb1' },
    { label: 'iGPU', sub: `SmolVLA · FP16 (${igpu.throughput_fps?.toFixed(0) || 42} fps)`, ms: igpuMs, color: '#89b9ef' },
    { label: 'CPU', sub: 'FSM · 30 Hz IK loop', ms: cpuMs, color: '#c4a7ea' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="glass-panel rounded-xl p-4 space-y-3"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-[#89b9ef]" />
          <h3 className="text-[14px] font-semibold text-[#edf2f7]">Edge Silicon Pulse</h3>
        </div>
        <div className="font-mono text-[13px] font-semibold text-[#55dbb1] tabular-nums">
          {totalMs.toFixed(1)} ms
        </div>
      </div>

      {/* Stacked Segmented Bar */}
      <div className="h-1.5 w-full flex rounded-full overflow-hidden gap-0.5 bg-white/[0.04]">
        {lanes.map((l) => (
          <motion.div
            key={l.label}
            animate={{ width: `${(l.ms / totalMs) * 100}%` }}
            transition={{ type: 'spring', stiffness: 180, damping: 24 }}
            className="h-full rounded-full"
            style={{ backgroundColor: l.color }}
          />
        ))}
      </div>

      <div className="space-y-2 pt-0.5">
        {lanes.map((l) => (
          <div key={l.label} className="flex items-center justify-between text-[11.5px]">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: l.color }} />
              <span className="font-mono font-semibold text-[#edf2f7] w-9">{l.label}</span>
              <span className="text-[#8e9bae] font-mono text-[10.5px] truncate">{l.sub}</span>
            </div>
            <span className="font-mono font-semibold text-[#edf2f7] tabular-nums shrink-0">
              {l.ms.toFixed(1)} ms
            </span>
          </div>
        ))}
      </div>

      {onOpenBenchTab && (
        <button
          onClick={onOpenBenchTab}
          className="w-full mt-1 py-1.5 px-3 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] border border-white/[0.06] text-[11px] font-medium text-[#b5c0ce] hover:text-[#edf2f7] flex items-center justify-between transition-colors"
        >
          <span>OpenVINO Bench Matrix</span>
          <span className="flex items-center gap-1 font-mono text-[#55dbb1]">
            {benchmarks.length} profiles <ArrowUpRight className="w-3.5 h-3.5" />
          </span>
        </button>
      )}
    </motion.div>
  );
}
