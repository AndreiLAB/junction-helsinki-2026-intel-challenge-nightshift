import React from 'react';

export default function PerformanceOverview({ cycles = [] }) {
  const hasCycles = cycles.length > 0;
  const total = hasCycles ? cycles.length : 5;

  const accepted = hasCycles
    ? cycles.filter(c => c.verdict === 'GOOD' || c.action === 'PERFECT_BOWL').length
    : 3;
  const defective = hasCycles
    ? cycles.filter(c => c.verdict === 'DEFECT' || c.action === 'DEFECTIVE_BOWL').length
    : 1;
  const regrasps = hasCycles
    ? cycles.filter(
        c =>
          c.verdict === 'UNCERTAIN' ||
          c.verdict === 'NO_BRICK' ||
          c.action === 'REGRASP_TRIGGERED' ||
          (Array.isArray(c.views) && c.views.length > 1)
      ).length
    : 1;

  const acceptancePct = Math.round((accepted / (total || 1)) * 100);

  const realCount = cycles.filter(c => (c.evidence || '').toUpperCase() === 'REAL').length;
  const replayCount = cycles.filter(c => (c.evidence || '').toUpperCase() === 'REPLAY').length;
  const mockCount = cycles.filter(c => !c.evidence || (c.evidence || '').toUpperCase() === 'MOCK').length;

  const timedCycles = cycles.filter(c => typeof c.cycle_s === 'number' && c.cycle_s > 0);
  const avgCycleS =
    timedCycles.length > 0
      ? timedCycles.reduce((acc, c) => acc + c.cycle_s, 0) / timedCycles.length
      : null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 w-full">
      {/* 1. Total Inspected */}
      <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 flex flex-col justify-between min-h-[82px] hover:border-[#26313e]/80 transition-all">
        <div className="flex items-center justify-between gap-1">
          <span className="text-[12px] font-medium text-[#8e9bae]">
            Bricks inspected
          </span>
          {avgCycleS !== null && (
            <span className="text-[10px] font-mono font-semibold text-[#89b9ef] bg-[#18212c] px-1.5 py-0.5 rounded">
              {avgCycleS.toFixed(1)}s / brick
            </span>
          )}
        </div>
        <div className="flex items-baseline justify-between gap-2 mt-1">
          <span className="text-[28px] font-semibold text-[#edf2f7] leading-none tabular-nums tracking-tight">
            {total}
          </span>
          <span className="text-[10px] font-mono text-[#8e9bae] truncate">
            {realCount > 0 || replayCount > 0
              ? `${realCount} REAL · ${replayCount} REPLAY · ${mockCount} MOCK`
              : `${mockCount || total} MOCK cycles`}
          </span>
        </div>
      </div>

      {/* 2. Accepted (GOOD) */}
      <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 flex flex-col justify-between min-h-[82px] hover:border-[#55dbb1]/40 transition-all">
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-medium text-[#8e9bae]">
            GOOD (&lt; t_low)
          </span>
          <span className="text-[10px] font-mono text-[#55dbb1]/80">Bowl #1</span>
        </div>
        <div className="flex items-baseline space-x-2 mt-1">
          <span className="text-[28px] font-semibold text-[#55dbb1] leading-none tabular-nums tracking-tight">
            {accepted}
          </span>
          <span className="text-[11px] text-[#8e9bae]">
            {acceptancePct}% good bowl
          </span>
        </div>
      </div>

      {/* 3. Defective (DEFECT) */}
      <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 flex flex-col justify-between min-h-[82px] hover:border-[#f28d95]/40 transition-all">
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-medium text-[#8e9bae]">
            DEFECT (&gt; t_high)
          </span>
          <span className="text-[10px] font-mono text-[#f28d95]/80">Bowl #2</span>
        </div>
        <div className="flex items-baseline space-x-2 mt-1">
          <span className="text-[28px] font-semibold text-[#f28d95] leading-none tabular-nums tracking-tight">
            {defective}
          </span>
          <span className="text-[11px] text-[#8e9bae]">
            Defective bowl · Audited
          </span>
        </div>
      </div>

      {/* 4. Multi-View & Re-grasps */}
      <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 flex flex-col justify-between min-h-[82px] hover:border-[#e9bf79]/40 transition-all">
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-medium text-[#8e9bae]">
            Multi-view / Recovery
          </span>
          <span className="text-[10px] font-mono text-[#e9bf79]/80">t_low–t_high</span>
        </div>
        <div className="flex items-baseline space-x-2 mt-1">
          <span className="text-[28px] font-semibold text-[#e9bf79] leading-none tabular-nums tracking-tight">
            {regrasps}
          </span>
          <span className="text-[11px] text-[#8e9bae] truncate">
            Wrist rotation / re-grasp
          </span>
        </div>
      </div>
    </div>
  );
}
