import React from 'react';
import { ArrowRight, Eye, ShieldAlert, Cpu, Bot, Zap } from 'lucide-react';

export default function ClosedLoopPipeline({ activeStage }) {
  const stages = [
    {
      id: 'PERCEIVE',
      step: '01',
      title: 'Perceive',
      sub: 'RealSense + QHD',
      icon: Eye,
    },
    {
      id: 'DETECT',
      step: '02',
      title: 'Detect',
      sub: 'Anomalib · NPU',
      icon: ShieldAlert,
    },
    {
      id: 'REASON',
      step: '03',
      title: 'Reason',
      sub: 'SmolVLA / ACT · iGPU',
      icon: Cpu,
    },
    {
      id: 'ACT',
      step: '04',
      title: 'Act',
      sub: 'SO-101 robotic arm',
      icon: Bot,
    },
    {
      id: 'OPTIMIZE',
      step: '05',
      title: 'Optimize',
      sub: 'OpenVINO acceleration',
      icon: Zap,
    },
  ];

  const getStageIndex = (stageId) => stages.findIndex(s => s.id === stageId);
  const currentIdx = getStageIndex(activeStage);

  const getStatusText = () => {
    if (!activeStage || activeStage === 'IDLE') return 'Idle · ready for next cycle';
    const current = stages.find(s => s.id === activeStage);
    return `${current?.title || activeStage} in progress…`;
  };

  return (
    <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-3.5 w-full">
      {/* Header bar */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-semibold text-[#8e9bae] tracking-wider uppercase">
          CLOSED-LOOP PIPELINE
        </span>
        <div className="bg-[#18212c] px-2.5 py-1 rounded-[5px] border border-[#26313e]/40">
          <span className="text-[11px] font-medium text-[#b5c0ce] flex items-center space-x-1.5">
            {activeStage && activeStage !== 'IDLE' && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#55dbb1] animate-ping" />
            )}
            <span>{getStatusText()}</span>
          </span>
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
