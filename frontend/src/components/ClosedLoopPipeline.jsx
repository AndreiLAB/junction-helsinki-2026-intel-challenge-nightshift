import React from 'react';
import { motion } from 'framer-motion';
import { Eye, ShieldAlert, Cpu, Bot, Sparkles } from 'lucide-react';

const STAGES = [
  { id: 'PERCEIVE', step: '01', title: 'Perceive', sub: 'ACT v2 Pick (12ms)', icon: Eye },
  { id: 'DETECT', step: '02', title: 'Detect', sub: 'patchcore_v1 NPU', icon: ShieldAlert },
  { id: 'REASON', step: '03', title: 'Decide', sub: '0.45 / 0.60 Band', icon: Cpu },
  { id: 'ACT', step: '04', title: 'Act', sub: 'SmolVLA 104ms GPU', icon: Bot },
  { id: 'OPTIMIZE', step: '05', title: 'Audit', sub: 'B300 · MariaDB', icon: Sparkles },
];

export default function ClosedLoopPipeline({ activeStage = 'IDLE', cellState = 'HOME', currentCycle }) {
  const currentIdx = STAGES.findIndex(s => s.id === activeStage);
  const effectiveCellState = (cellState || currentCycle?.cell_state || 'HOME').toUpperCase();

  const isFault = effectiveCellState === 'FAULT';
  const isRecover =
    effectiveCellState === 'NEXT_VIEW' ||
    effectiveCellState === 'REGRASP' ||
    effectiveCellState === 'CHECK_HELD';
  const isDefect = effectiveCellState === 'PLACE_DEFECT';

  const stateColor = isFault || isDefect
    ? 'text-[#f28d95] bg-[#38232c]/60 border-[#f28d95]/30'
    : isRecover
    ? 'text-[#e9bf79] bg-[#352e21]/60 border-[#e9bf79]/30'
    : 'text-[#55dbb1] bg-[#15352e]/60 border-[#55dbb1]/30';

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.12 }}
      className="glass-panel rounded-xl px-4 py-3 w-full"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-2.5">
          <span className="text-[10.5px] font-semibold tracking-widest uppercase text-[#8e9bae]">
            Closed-Loop Sequence
          </span>
          {currentCycle?.run_id && (
            <span className="text-[11px] font-mono text-[#89b9ef]/90">
              {currentCycle.run_id}
              {currentCycle.brick_idx != null ? ` · #${currentCycle.brick_idx}` : ''}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <motion.span
            key={effectiveCellState}
            initial={{ scale: 0.92, opacity: 0.6 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: 'spring', stiffness: 360, damping: 24 }}
            className={`px-2.5 py-0.5 rounded-full border font-mono text-[10.5px] font-semibold flex items-center gap-1.5 ${stateColor}`}
          >
            {activeStage !== 'IDLE' && (
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-ping" />
            )}
            <span>FSM: {effectiveCellState}</span>
          </motion.span>
        </div>
      </div>

      {/* Horizontal Stepper Track */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 relative">
        {STAGES.map((st, idx) => {
          const Icon = st.icon;
          const isActive = activeStage === st.id;
          const isPassed = currentIdx > -1 && idx < currentIdx;

          return (
            <div
              key={st.id}
              className={`relative rounded-lg px-3 py-2 flex items-center gap-2.5 transition-colors duration-200 border ${
                isActive
                  ? 'border-[#55dbb1]/40 text-[#edf2f7]'
                  : isPassed
                  ? 'bg-white/[0.03] border-[#55dbb1]/20 text-[#edf2f7]'
                  : 'bg-white/[0.015] border-white/[0.04] text-[#8e9bae]'
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="pipelineActiveGlow"
                  transition={{ type: 'spring', stiffness: 300, damping: 28 }}
                  className="absolute inset-0 rounded-lg bg-gradient-to-r from-[#55dbb1]/15 via-[#55dbb1]/10 to-transparent pointer-events-none"
                />
              )}

              <div
                className={`relative z-10 w-6 h-6 rounded-md flex items-center justify-center shrink-0 transition-colors ${
                  isActive
                    ? 'bg-[#55dbb1] text-[#070a0f] shadow-[0_0_16px_rgba(85,219,177,0.45)]'
                    : isPassed
                    ? 'bg-[#15352e] text-[#55dbb1]'
                    : 'bg-white/[0.05] text-[#8e9bae]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
              </div>

              <div className="relative z-10 min-w-0">
                <div className="text-[12px] font-semibold leading-tight truncate flex items-center gap-1.5">
                  <span>{st.title}</span>
                </div>
                <div className="text-[10px] font-mono opacity-75 truncate">{st.sub}</div>
              </div>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}
