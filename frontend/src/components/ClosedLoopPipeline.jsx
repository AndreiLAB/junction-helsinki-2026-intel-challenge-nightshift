import React from 'react';
import { ArrowRight, Eye, ShieldAlert, Cpu, Bot, Zap } from 'lucide-react';

function getCellStateStyle(state) {
  const s = (state || 'HOME').toUpperCase();
  if (s === 'FAULT') {
    return 'bg-[#38232c] text-[#f28d95] border-[#f28d95]/40';
  }
  if (s === 'NEXT_VIEW' || s === 'REGRASP' || s === 'CHECK_HELD') {
    return 'bg-[#352e21] text-[#e9bf79] border-[#e9bf79]/40';
  }
  if (s === 'PLACE_DEFECT') {
    return 'bg-[#38232c] text-[#f28d95] border-[#f28d95]/30';
  }
  if (s === 'PLACE_GOOD' || s === 'CONFIRM' || s === 'DONE') {
    return 'bg-[#15352e] text-[#55dbb1] border-[#55dbb1]/30';
  }
  if (s === 'INSPECT' || s === 'DECIDE' || s === 'PICK_PRESENT' || s === 'SNAP_TO_INSPECT') {
    return 'bg-[#18212c] text-[#89b9ef] border-[#89b9ef]/30';
  }
  return 'bg-[#18212c] text-[#b5c0ce] border-[#26313e]';
}

export default function ClosedLoopPipeline({ activeStage, cellState = 'HOME', currentCycle }) {
  const stages = [
    {
      id: 'PERCEIVE',
      step: '01',
      title: 'Perceive',
      sub: 'PICK_PRESENT · Snap',
      icon: Eye,
    },
    {
      id: 'DETECT',
      step: '02',
      title: 'Detect',
      sub: 'PatchCore · NPU INT8',
      icon: ShieldAlert,
    },
    {
      id: 'REASON',
      step: '03',
      title: 'Decide',
      sub: 't_low / t_high · Multi-View',
      icon: Cpu,
    },
    {
      id: 'ACT',
      step: '04',
      title: 'Act',
      sub: 'VLA / ACT · SO-101',
      icon: Bot,
    },
    {
      id: 'OPTIMIZE',
      step: '05',
      title: 'Confirm & Audit',
      sub: 'Nemotron · MariaDB',
      icon: Zap,
    },
  ];

  const getStageIndex = (stageId) => stages.findIndex(s => s.id === stageId);
  const currentIdx = getStageIndex(activeStage);
  const effectiveCellState = (cellState || currentCycle?.cell_state || 'HOME').toUpperCase();

  const getStatusText = () => {
    if (!activeStage || activeStage === 'IDLE') return 'Idle · ready for next cycle';
    const current = stages.find(s => s.id === activeStage);
    return `${current?.title || activeStage} in progress…`;
  };

  return (
    <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 w-full">
      {/* Header bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-semibold text-[#8e9bae] tracking-wider uppercase">
            CLOSED-LOOP PIPELINE
          </span>
          {currentCycle?.run_id && (
            <span className="text-[10px] font-mono text-[#89b9ef] bg-[#18212c] border border-[#26313e] px-2 py-0.5 rounded-[4px]">
              run: {currentCycle.run_id}
              {currentCycle.brick_idx !== undefined && currentCycle.brick_idx !== null
                ? ` · brick #${currentCycle.brick_idx}`
                : ''}
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className={`px-2.5 py-0.5 rounded-[5px] border font-mono text-[10px] font-semibold ${getCellStateStyle(effectiveCellState)}`}>
            STATE: {effectiveCellState}
          </div>
          <div className="bg-[#18212c] px-2.5 py-1 rounded-[5px] border border-[#26313e]/40">
            <span className="text-[11px] font-medium text-[#b5c0ce] flex items-center space-x-1.5">
              {activeStage && activeStage !== 'IDLE' && (
                <span className="w-1.5 h-1.5 rounded-full bg-[#55dbb1] animate-ping" />
              )}
              <span>{getStatusText()}</span>
            </span>
          </div>
        </div>
      </div>

      {/* 5-Stage sequence */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 sm:gap-3 items-center">
        {stages.map((st, idx) => {
          const isActive = activeStage === st.id;
          const isPassed = currentIdx > -1 && idx < currentIdx;

          return (
            <div key={st.id} className="flex items-center space-x-2 sm:space-x-3">
              <div
                className={`flex-1 flex items-center space-x-2.5 p-2 rounded-[6px] transition-all border ${
                  isActive
                    ? 'bg-[#15352e] border-[#55dbb1] shadow-md shadow-[#55dbb1]/20'
                    : isPassed
                    ? 'bg-[#18212c]/60 border-[#55dbb1]/30'
                    : 'bg-[#18212c]/30 border-transparent'
                }`}
              >
                {/* Step number badge */}
                <div
                  className={`w-7 h-7 rounded-[5px] flex items-center justify-center text-[10px] font-medium shrink-0 ${
                    isActive
                      ? 'bg-[#55dbb1] text-[#0b0f14] font-bold'
                      : isPassed
                      ? 'bg-[#15352e] text-[#55dbb1]'
                      : 'bg-[#18212c] text-[#8e9bae]'
                  }`}
                >
                  {st.step}
                </div>

                {/* Title & subtitle */}
                <div className="min-w-0">
                  <div
                    className={`text-[13px] font-semibold truncate leading-tight ${
                      isActive ? 'text-[#55dbb1]' : isPassed ? 'text-[#edf2f7]' : 'text-[#b5c0ce]'
                    }`}
                  >
                    {st.title}
                  </div>
                  <div className="text-[10px] text-[#8e9bae] truncate leading-tight mt-0.5">
                    {st.sub}
                  </div>
                </div>
              </div>

              {/* Arrow connector (hidden on last item) */}
              {idx < stages.length - 1 && (
                <ArrowRight className="hidden sm:block w-3.5 h-3.5 text-[#26313e] shrink-0" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
