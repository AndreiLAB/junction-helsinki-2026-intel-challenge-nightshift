import React from 'react';
import { Eye, ShieldAlert, Cpu, Bot, Zap, CheckCircle2 } from 'lucide-react';

export default function ClosedLoopPipeline({ activeStage }) {
  const stages = [
    {
      id: 'PERCEIVE',
      step: '01',
      title: 'PERCEIVE',
      sub: 'Observation & Cameras',
      hw: 'RealSense D415 + QHD',
      icon: Eye,
      desc: 'Dual-camera frame capture & spatial depth alignment',
    },
    {
      id: 'DETECT',
      step: '02',
      title: 'DETECT',
      sub: 'Visual Anomaly',
      hw: 'Intel NPU (50 TOPS)',
      icon: ShieldAlert,
      desc: 'Anomalib v2.7.0 PatchCore (~9.4ms)',
    },
    {
      id: 'REASON',
      step: '03',
      title: 'REASON',
      sub: 'Task Decision & VLA',
      hw: '12 Xe3 Cores (iGPU)',
      icon: Cpu,
      desc: 'SmolVLA / ACT Policy (~24.1ms)',
    },
    {
      id: 'ACT',
      step: '04',
      title: 'ACT',
      sub: 'Physical Manipulation',
      hw: 'LeRobot SO-ARM101',
      icon: Bot,
      desc: 'Deterministic trajectory control (~2.1ms)',
    },
    {
      id: 'OPTIMIZE',
      step: '05',
      title: 'OPTIMIZE',
      sub: 'OpenVINO Acceleration',
      hw: 'Core™ Ultra Series 3',
      icon: Zap,
      desc: 'Heterogeneous NPU + GPU + CPU pipeline',
    },
  ];

  const getStageIndex = (stageId) => stages.findIndex(s => s.id === stageId);
  const currentIdx = getStageIndex(activeStage);

  return (
    <div className="bg-obsidian-900 border border-obsidian-border rounded-xl px-4 py-3 shadow-xl backdrop-blur-md">
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-intel-light animate-ping" />
          <span className="text-xs font-mono uppercase tracking-wider text-intel-light font-bold">
            CLOSED-LOOP AUTONOMOUS PIPELINE
          </span>
          <span className="text-[11px] text-slate-500 font-mono hidden sm:inline">
            [PERCEIVE → DETECT → REASON → ACT → OPTIMIZE]
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-[11px] text-slate-400 font-mono">Pipeline State:</span>
          <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold uppercase transition-all duration-300 ${
            activeStage === 'IDLE' 
              ? 'bg-obsidian-800 text-slate-400 border border-slate-700/60' 
              : 'bg-intel-blue/30 text-intel-light border border-intel-light shadow-glow-intel'
          }`}>
            {activeStage}
          </span>
        </div>
      </div>

      {/* 5-Step Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5">
        {stages.map((st, idx) => {
          const Icon = st.icon;
          const isActive = activeStage === st.id;
          const isPassed = currentIdx > -1 && idx < currentIdx;

          return (
            <div
              key={st.id}
              className={`relative rounded-lg p-2.5 transition-all duration-200 border flex flex-col justify-between ${
                isActive
                  ? 'bg-intel-blue/20 border-intel-light shadow-glow-intel'
                  : isPassed
                  ? 'bg-obsidian-850 border-emerald-500/30 text-slate-300'
                  : 'bg-obsidian-950/70 border-obsidian-border text-slate-400'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded font-bold ${
                    isActive
                      ? 'bg-intel-light text-slate-950'
                      : isPassed
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-obsidian-800 text-slate-400'
                  }`}>
                    STAGE {st.step}
                  </span>
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-intel-light animate-bounce' : isPassed ? 'text-emerald-400' : 'text-slate-500'}`} />
                </div>

                <div className="text-xs font-bold tracking-tight text-white flex items-center space-x-1">
                  <span>{st.title}</span>
                  {isPassed && <CheckCircle2 className="w-3 h-3 text-emerald-400 inline" />}
                </div>
                <div className="text-[10px] text-slate-400 font-medium truncate">{st.sub}</div>
              </div>

              <div className="mt-2 pt-1.5 border-t border-obsidian-border/80">
                <div className="text-[10px] font-mono text-intel-light truncate font-semibold">
                  {st.hw}
                </div>
                <div className="text-[9px] text-slate-500 truncate mt-0.5" title={st.desc}>
                  {st.desc}
                </div>
              </div>

              {/* Glowing active indicator */}
              {isActive && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-intel-light rounded-b-lg overflow-hidden">
                  <div className="h-full bg-white animate-pulse" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
