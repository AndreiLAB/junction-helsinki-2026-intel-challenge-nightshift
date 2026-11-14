import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertTriangle, RotateCcw, Terminal, ScanLine } from 'lucide-react';

const VIEW_MODES = [
  { id: 'overlay', label: 'Composite' },
  { id: 'heatmap', label: 'Heatmap' },
  { id: 'raw', label: 'Raw RGB' },
];

export default function DualCameraFeed({ currentCycle, cellState = 'HOME', policyBounds, activeStage = 'IDLE' }) {
  const [viewMode, setViewMode] = useState('overlay');

  const score = Number(currentCycle?.score ?? currentCycle?.anomaly_score ?? 0.14);
  const tLow = Number(currentCycle?.t_low ?? policyBounds?.t_low ?? 0.35);
  const tHigh = Number(currentCycle?.t_high ?? policyBounds?.t_high ?? 0.60);

  const verdict = (
    currentCycle?.verdict ||
    (currentCycle?.action === 'DEFECTIVE_BOWL'
      ? 'DEFECT'
      : currentCycle?.action === 'REGRASP_TRIGGERED'
      ? 'UNCERTAIN'
      : 'GOOD')
  ).toUpperCase();

  const isDefective = verdict === 'DEFECT' || currentCycle?.action === 'DEFECTIVE_BOWL';
  const isRegrasp =
    verdict === 'UNCERTAIN' || verdict === 'NO_BRICK' || currentCycle?.action === 'REGRASP_TRIGGERED';

  const scorePct = Math.min(Math.max(score * 100, 1.5), 98.5);
  const tLowPct = Math.min(Math.max(tLow * 100, 6), 88);
  const tHighPct = Math.min(Math.max(tHigh * 100, tLowPct + 5), 95);

  const views = Array.isArray(currentCycle?.views) ? currentCycle.views : [];
  const brickColor = (currentCycle?.color || 'green').toLowerCase();
  const evidence = (currentCycle?.evidence || 'MOCK').toUpperCase();

  const instruction =
    currentCycle?.instruction ||
    (isDefective
      ? 'Put the brick in the defective bowl.'
      : isRegrasp
      ? 'Pick up a brick and hold it in front of the inspection camera.'
      : 'Put the brick in the good bowl.');

  let activeImage = currentCycle?.composite_url;
  if (viewMode === 'heatmap') activeImage = currentCycle?.heatmap_url || currentCycle?.composite_url;
  if (viewMode === 'raw') activeImage = currentCycle?.raw_url;

  const isScanning = activeStage === 'DETECT' || activeStage === 'PERCEIVE' || cellState === 'INSPECT';

  // Kinematic SVG target coordinates for the SO-101 arm
  const armJointX = isDefective ? 225 : isRegrasp ? 150 : 75;
  const armJointY = isDefective ? 56 : isRegrasp ? 115 : 56;
  const strokeAccent = isDefective ? '#f28d95' : isRegrasp ? '#e9bf79' : '#55dbb1';

  const brickHex =
    brickColor === 'yellow'
      ? '#f59e0b'
      : brickColor === 'red'
      ? '#f43f5e'
      : brickColor === 'blue'
      ? '#3b82f6'
      : '#10b981';

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.16 }}
      className="glass-panel rounded-xl p-4 sm:p-5 flex flex-col justify-between h-full relative overflow-hidden"
    >
      {/* Ambient verdict mood halo */}
      <motion.div
        animate={{
          background: isDefective
            ? 'radial-gradient(circle at 80% 10%, rgba(242,141,149,0.12), transparent 55%)'
            : isRegrasp
            ? 'radial-gradient(circle at 80% 10%, rgba(233,191,121,0.12), transparent 55%)'
            : 'radial-gradient(circle at 80% 10%, rgba(85,219,177,0.12), transparent 55%)',
        }}
        transition={{ duration: 0.6 }}
        className="absolute inset-0 pointer-events-none"
      />

      <div className="relative z-10 space-y-3.5">
        {/* Clean Header */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <h2 className="text-[15px] font-semibold text-[#edf2f7] tracking-tight">
              Dual-Camera Vision &amp; Verdict
            </h2>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold border ${
                evidence === 'REAL'
                  ? 'bg-[#15352e]/70 text-[#55dbb1] border-[#55dbb1]/30'
                  : evidence === 'REPLAY'
                  ? 'bg-[#18212c] text-[#89b9ef] border-[#89b9ef]/30'
                  : 'bg-white/[0.04] text-[#8e9bae] border-white/[0.08]'
              }`}
            >
              {evidence}
            </span>
            {typeof currentCycle?.cycle_s === 'number' && (
              <span className="text-[11px] font-mono text-[#8e9bae] tabular-nums">
                {currentCycle.cycle_s.toFixed(1)}s
              </span>
            )}
          </div>

          {/* Animated Verdict Capsule */}
          <AnimatePresence mode="wait">
            <motion.div
              key={`${currentCycle?.cycle_id}-${verdict}`}
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 360, damping: 24 }}
              className={`px-3 py-1 rounded-full border flex items-center gap-1.5 text-[11px] font-mono font-semibold ${
                isDefective
                  ? 'bg-[#38232c]/80 text-[#f28d95] border-[#f28d95]/35 shadow-[0_0_18px_rgba(242,141,149,0.2)]'
                  : isRegrasp
                  ? 'bg-[#352e21]/80 text-[#e9bf79] border-[#e9bf79]/35 shadow-[0_0_18px_rgba(233,191,121,0.18)]'
                  : 'bg-[#15352e]/80 text-[#55dbb1] border-[#55dbb1]/35 shadow-[0_0_18px_rgba(85,219,177,0.18)]'
              }`}
            >
              {isDefective ? (
                <AlertTriangle className="w-3.5 h-3.5" />
              ) : isRegrasp ? (
                <RotateCcw className="w-3.5 h-3.5" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5" />
              )}
              <span>
                {verdict} → {isDefective ? 'Defect Bowl' : isRegrasp ? 'Multi-View / Re-grasp' : 'Good Bowl'}
              </span>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Dual Camera Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* CAM 01: Kinematic Workspace */}
          <div className="relative aspect-[16/10] w-full rounded-xl overflow-hidden border border-white/[0.08] bg-[#06090f] optical-grid">
            <div className="absolute top-2.5 left-2.5 z-10 flex items-center gap-1.5 bg-[#070a0f]/80 backdrop-blur-md px-2 py-0.5 rounded-md border border-white/[0.08]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#55dbb1] animate-pulse" />
              <span className="text-[10px] font-mono text-[#b5c0ce]">CAM-01 · Overhead Workspace</span>
            </div>

            {currentCycle?.top_url ? (
              <img src={currentCycle.top_url} alt="Overhead workspace" className="w-full h-full object-cover" />
            ) : (
              <svg viewBox="0 0 300 185" className="w-full h-full">
                {/* Plate */}
                <rect x="108" y="96" width="84" height="58" rx="6" fill="#0d1522" stroke="#1e293b" strokeWidth="1" />
                {/* Good Bowl */}
                <motion.circle
                  cx="55"
                  cy="50"
                  r="24"
                  fill={!isDefective && !isRegrasp ? '#15352e' : '#0b121b'}
                  stroke={!isDefective && !isRegrasp ? '#55dbb1' : '#26313e'}
                  strokeWidth={!isDefective && !isRegrasp ? '2' : '1'}
                  animate={!isDefective && !isRegrasp ? { scale: [1, 1.05, 1] } : { scale: 1 }}
                  transition={{ repeat: Infinity, duration: 2.2 }}
                />
                <text x="55" y="54" textAnchor="middle" fill="#55dbb1" fontSize="8" fontFamily="monospace" fontWeight="600">
                  GOOD
                </text>

                {/* Defect Bowl */}
                <motion.circle
                  cx="245"
                  cy="50"
                  r="24"
                  fill={isDefective ? '#38232c' : '#0b121b'}
                  stroke={isDefective ? '#f28d95' : '#26313e'}
                  strokeWidth={isDefective ? '2' : '1'}
                  animate={isDefective ? { scale: [1, 1.06, 1] } : { scale: 1 }}
                  transition={{ repeat: Infinity, duration: 1.8 }}
                />
                <text x="245" y="54" textAnchor="middle" fill="#f28d95" fontSize="8" fontFamily="monospace" fontWeight="600">
                  DEFECT
                </text>

                {/* Trajectory Path */}
                {isDefective ? (
                  <motion.path
                    key={`path-def-${currentCycle?.cycle_id}`}
                    d="M 150 120 Q 198 72 240 52"
                    stroke="#f28d95"
                    strokeWidth="2"
                    strokeDasharray="4 4"
                    fill="none"
                    initial={{ pathLength: 0, opacity: 0.2 }}
                    animate={{ pathLength: 1, opacity: 0.9 }}
                    transition={{ duration: 0.7, ease: 'easeOut' }}
                  />
                ) : isRegrasp ? (
                  <motion.circle
                    cx="150"
                    cy="120"
                    r="23"
                    stroke="#e9bf79"
                    strokeWidth="1.8"
                    strokeDasharray="4 3"
                    fill="none"
                    animate={{ rotate: 360 }}
                    transition={{ repeat: Infinity, duration: 6, ease: 'linear' }}
                    style={{ originX: '150px', originY: '120px' }}
                  />
                ) : (
                  <motion.path
                    key={`path-good-${currentCycle?.cycle_id}`}
                    d="M 150 120 Q 102 72 60 52"
                    stroke="#55dbb1"
                    strokeWidth="2"
                    strokeDasharray="4 4"
                    fill="none"
                    initial={{ pathLength: 0, opacity: 0.2 }}
                    animate={{ pathLength: 1, opacity: 0.9 }}
                    transition={{ duration: 0.7, ease: 'easeOut' }}
                  />
                )}

                {/* Animated SO-101 Robot Arm Linkage */}
                <circle cx="150" cy="172" r="9" fill="#18212c" stroke="#475569" strokeWidth="1.5" />
                <motion.line
                  x1="150"
                  y1="172"
                  animate={{ x2: (150 + armJointX) / 2, y2: 118 }}
                  transition={{ type: 'spring', stiffness: 120, damping: 18 }}
                  stroke="#94a3b8"
                  strokeWidth="4.5"
                  strokeLinecap="round"
                />
                <motion.line
                  animate={{
                    x1: (150 + armJointX) / 2,
                    y1: 118,
                    x2: armJointX,
                    y2: armJointY,
                  }}
                  transition={{ type: 'spring', stiffness: 120, damping: 18 }}
                  stroke="#cbd5e1"
                  strokeWidth="3.5"
                  strokeLinecap="round"
                />
                {/* End effector gripping active brick */}
                <motion.g
                  animate={{ x: armJointX, y: armJointY }}
                  transition={{ type: 'spring', stiffness: 120, damping: 18 }}
                >
                  <circle cx="0" cy="0" r="6" fill={strokeAccent} opacity="0.25" />
                  <rect x="-8" y="-6" width="16" height="12" rx="2.5" fill={brickHex} stroke="#ffffff" strokeWidth="1.1" />
                </motion.g>
              </svg>
            )}
          </div>

          {/* CAM 02: Inspection Backdrop & Heatmap */}
          <div className="relative aspect-[16/10] w-full rounded-xl overflow-hidden border border-white/[0.08] bg-[#06090f] flex items-center justify-center">
            <div className="absolute top-2.5 left-2.5 z-10 flex items-center gap-1.5 bg-[#070a0f]/80 backdrop-blur-md px-2 py-0.5 rounded-md border border-white/[0.08]">
              <ScanLine className="w-3 h-3 text-[#89b9ef]" />
              <span className="text-[10px] font-mono text-[#b5c0ce]">CAM-02 · Inspection ROI</span>
            </div>

            {/* Segmented Mode Toggle (LayoutId animated pill) */}
            <div className="absolute top-2.5 right-2.5 z-10 flex items-center bg-[#070a0f]/85 backdrop-blur-md p-0.5 rounded-md border border-white/[0.08]">
              {VIEW_MODES.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setViewMode(m.id)}
                  className={`relative px-2 py-0.5 text-[10px] font-medium rounded transition-colors ${
                    viewMode === m.id ? 'text-[#070a0f]' : 'text-[#8e9bae] hover:text-[#edf2f7]'
                  }`}
                >
                  {viewMode === m.id && (
                    <motion.span
                      layoutId="camViewModePill"
                      transition={{ type: 'spring', stiffness: 360, damping: 28 }}
                      className="absolute inset-0 bg-[#55dbb1] rounded"
                    />
                  )}
                  <span className="relative z-10">{m.label}</span>
                </button>
              ))}
            </div>

            {/* Animated Laser Scan Sweep */}
            {isScanning && (
              <motion.div
                initial={{ top: '0%' }}
                animate={{ top: ['0%', '96%', '0%'] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
                className="absolute inset-x-0 h-[2px] bg-gradient-to-r from-transparent via-[#55dbb1] to-transparent shadow-[0_0_12px_#55dbb1] z-20 pointer-events-none"
              />
            )}

            <AnimatePresence mode="wait">
              {activeImage ? (
                <motion.img
                  key={`${currentCycle?.cycle_id}-${viewMode}-${activeImage}`}
                  src={activeImage}
                  alt="Inspection camera crop"
                  initial={{ opacity: 0, scale: 1.03 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  className="w-full h-full object-contain"
                />
              ) : (
                <motion.div
                  key={`synth-${currentCycle?.cycle_id}-${viewMode}`}
                  initial={{ opacity: 0, scale: 0.92 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.28 }}
                  className="relative flex items-center justify-center w-full h-full optical-grid"
                >
                  <div
                    className="w-24 h-24 rounded-xl flex items-center justify-center relative shadow-2xl border border-white/15"
                    style={{ backgroundColor: brickHex }}
                  >
                    <div className="grid grid-cols-2 gap-2.5">
                      {[0, 1, 2, 3].map((i) => (
                        <div key={i} className="w-5 h-5 rounded-full bg-white/20 border border-white/30" />
                      ))}
                    </div>
                    {viewMode !== 'raw' && (
                      <motion.div
                        animate={{ opacity: isDefective ? [0.45, 0.85, 0.45] : 0.3 }}
                        transition={{ repeat: Infinity, duration: 2 }}
                        className={`absolute inset-0 rounded-xl pointer-events-none ${
                          isDefective
                            ? 'bg-gradient-to-tr from-transparent via-rose-500/70 to-amber-400/70'
                            : isRegrasp
                            ? 'bg-gradient-to-tr from-transparent via-amber-400/50 to-transparent'
                            : 'bg-emerald-400/20'
                        }`}
                      />
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Score floating chip */}
            <div className="absolute bottom-2.5 right-2.5 z-10 bg-[#070a0f]/85 backdrop-blur-md px-2.5 py-0.5 rounded-md border border-white/[0.08] font-mono text-[10.5px]">
              <span className="text-[#8e9bae]">{currentCycle?.model || 'patchcore_256'} · </span>
              <span className="font-semibold" style={{ color: strokeAccent }}>
                {score.toFixed(3)}
              </span>
            </div>
          </div>
        </div>

        {/* VLA Command + Multi-View Pills */}
        <div className="glass-subtle rounded-lg px-3.5 py-2.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Terminal className="w-3.5 h-3.5 text-[#89b9ef] shrink-0" />
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#8e9bae] shrink-0">
              VLA Instruction
            </span>
            <motion.span
              key={instruction}
              initial={{ opacity: 0, x: 6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25 }}
              className="text-[12px] font-mono font-medium truncate"
              style={{ color: strokeAccent }}
            >
              &ldquo;{instruction}&rdquo;
            </motion.span>
          </div>

          {views.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              {views.map((v, idx) => {
                const vScore = Number(v.score ?? 0);
                const vCol = vScore >= tHigh ? '#f28d95' : vScore >= tLow ? '#e9bf79' : '#55dbb1';
                return (
                  <motion.span
                    key={`${v.view}-${idx}`}
                    initial={{ scale: 0.85, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: idx * 0.06 }}
                    className="px-2 py-0.5 rounded-md bg-white/[0.03] border border-white/[0.08] text-[10.5px] font-mono"
                    style={{ color: vCol }}
                  >
                    {v.view}: <strong>{vScore.toFixed(2)}</strong>
                  </motion.span>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Dual-Threshold Gauge */}
      <div className="relative z-10 pt-3.5 mt-3.5 border-t border-white/[0.06] space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-[11.5px]">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: brickHex }} />
            <span className="font-medium text-[#edf2f7] capitalize">{brickColor} brick</span>
            {currentCycle?.defect_label && currentCycle.defect_label !== 'None (Pristine)' && (
              <span className="text-[#8e9bae] font-mono text-[10.5px]">
                · {currentCycle.defect_label}
              </span>
            )}
          </div>

          <div className="flex items-baseline gap-2 font-mono">
            <span className="text-[10.5px] text-[#8e9bae]">
              t_low {tLow.toFixed(2)} · t_high {tHigh.toFixed(2)}
            </span>
            <motion.span
              key={score}
              initial={{ scale: 1.15 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 300, damping: 18 }}
              className="text-[18px] font-semibold tabular-nums"
              style={{ color: strokeAccent }}
            >
              {score.toFixed(3)}
            </motion.span>
          </div>
        </div>

        {/* Spring-Animated Gauge Track */}
        <div className="relative w-full h-2 bg-white/[0.04] rounded-full overflow-visible">
          <div className="absolute inset-0 flex rounded-full overflow-hidden opacity-35">
            <div style={{ width: `${tLowPct}%` }} className="bg-[#55dbb1]" />
            <div style={{ width: `${tHighPct - tLowPct}%` }} className="bg-[#e9bf79]" />
            <div style={{ width: `${100 - tHighPct}%` }} className="bg-[#f28d95]" />
          </div>

          {/* Threshold markers */}
          <div
            className="absolute -top-1 -bottom-1 w-[2px] bg-[#55dbb1]/80 rounded-full"
            style={{ left: `${tLowPct}%` }}
          />
          <div
            className="absolute -top-1 -bottom-1 w-[2px] bg-[#f28d95]/80 rounded-full"
            style={{ left: `${tHighPct}%` }}
          />

          {/* Glowing Spring Needle */}
          <motion.div
            animate={{ left: `${scorePct}%` }}
            transition={{ type: 'spring', stiffness: 220, damping: 24 }}
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full border-2 border-[#070a0f] shadow-lg z-10"
            style={{
              backgroundColor: strokeAccent,
              boxShadow: `0 0 12px ${strokeAccent}`,
            }}
          />
        </div>
      </div>
    </motion.div>
  );
}
