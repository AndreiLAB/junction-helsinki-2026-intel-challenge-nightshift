import React from 'react';

export default function PerformanceOverview({ cycles }) {
  const total = cycles.length > 0 ? cycles.length : 5;
  const accepted = cycles.length > 0 
    ? cycles.filter(c => c.action === 'PERFECT_BOWL').length 
    : 3;
  const defective = cycles.length > 0 
    ? cycles.filter(c => c.action === 'DEFECTIVE_BOWL').length 
    : 1;
  const regrasps = cycles.length > 0 
    ? cycles.filter(c => c.action === 'REGRASP_TRIGGERED').length 
    : 1;

  const acceptancePct = Math.round((accepted / (total || 1)) * 100);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 w-full">
      {/* 1. Total Inspected */}
      <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 flex flex-col justify-between h-[82px] hover:border-[#26313e]/80 transition-all">
        <div className="text-[12px] font-medium text-[#8e9bae]">
          Total inspected
        </div>
        <div className="flex items-baseline space-x-2">
          <span className="text-[28px] font-semibold text-[#edf2f7] leading-none tabular-nums tracking-tight">
            {total}
          </span>
          <span className="text-[11px] text-[#8e9bae]">
            Recorded cycles
          </span>
        </div>
      </div>

      {/* 2. Accepted */}
      <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 flex flex-col justify-between h-[82px] hover:border-[#55dbb1]/40 transition-all">
        <div className="text-[12px] font-medium text-[#8e9bae]">
          Accepted
        </div>
        <div className="flex items-baseline space-x-2">
          <span className="text-[28px] font-semibold text-[#55dbb1] leading-none tabular-nums tracking-tight">
            {accepted}
          </span>
          <span className="text-[11px] text-[#8e9bae]">
            {acceptancePct}% acceptance rate
          </span>
        </div>
      </div>

      {/* 3. Defective */}
      <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 flex flex-col justify-between h-[82px] hover:border-[#f28d95]/40 transition-all">
        <div className="text-[12px] font-medium text-[#8e9bae]">
          Defective
        </div>
        <div className="flex items-baseline space-x-2">
          <span className="text-[28px] font-semibold text-[#f28d95] leading-none tabular-nums tracking-tight">
            {defective}
          </span>
          <span className="text-[11px] text-[#8e9bae]">
            Routed to Bowl 2
          </span>
        </div>
      </div>

      {/* 4. Re-grasps */}
      <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 flex flex-col justify-between h-[82px] hover:border-[#e9bf79]/40 transition-all">
        <div className="text-[12px] font-medium text-[#8e9bae]">
          Re-grasps
        </div>
        <div className="flex items-baseline space-x-2">
          <span className="text-[28px] font-semibold text-[#e9bf79] leading-none tabular-nums tracking-tight">
            {regrasps}
          </span>
          <span className="text-[11px] text-[#8e9bae]">
            Sent for re-inspection
          </span>
        </div>
      </div>
    </div>
  );
}
