import React from 'react';
import { motion } from 'framer-motion';

function StatCard({ label, value, subtext, accent = 'neutral', delay = 0, barPct = null }) {
  const accentColors = {
    neutral: { num: 'text-[#edf2f7]', dot: 'bg-[#89b9ef]', bar: 'bg-[#89b9ef]' },
    good: { num: 'text-[#55dbb1]', dot: 'bg-[#55dbb1]', bar: 'bg-[#55dbb1]' },
    defect: { num: 'text-[#f28d95]', dot: 'bg-[#f28d95]', bar: 'bg-[#f28d95]' },
    warn: { num: 'text-[#e9bf79]', dot: 'bg-[#e9bf79]', bar: 'bg-[#e9bf79]' },
  }[accent];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -2, transition: { duration: 0.18 } }}
      className="glass-panel rounded-xl px-4 py-3.5 flex flex-col justify-between relative overflow-hidden group"
    >
      <div className="flex items-center justify-between">
        <span className="text-[11.5px] font-medium text-[#8e9bae] tracking-wide">{label}</span>
        <span className={`w-1.5 h-1.5 rounded-full ${accentColors.dot} opacity-80`} />
      </div>

      <div className="flex items-baseline justify-between gap-2 mt-2">
        <motion.span
          key={value}
          initial={{ opacity: 0.4, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 320, damping: 24 }}
          className={`text-[28px] font-semibold leading-none tabular-nums tracking-tight ${accentColors.num}`}
        >
          {value}
        </motion.span>
        <span className="text-[11px] font-mono text-[#8e9bae] truncate">{subtext}</span>
      </div>

      {barPct !== null && (
        <div className="mt-2.5 h-[3px] w-full bg-white/[0.06] rounded-full overflow-hidden">
          <motion.div
            className={`h-full rounded-full ${accentColors.bar}`}
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(100, Math.max(0, barPct))}%` }}
            transition={{ type: 'spring', stiffness: 120, damping: 20 }}
          />
        </div>
      )}
    </motion.div>
  );
}

export default function PerformanceOverview({ cycles = [] }) {
  const total = cycles.length;
  const accepted = cycles.filter(c => c.verdict === 'GOOD' || c.action === 'PERFECT_BOWL').length;
  const defective = cycles.filter(c => c.verdict === 'DEFECT' || c.action === 'DEFECTIVE_BOWL').length;
  const regrasps = cycles.filter(
    c =>
      c.verdict === 'UNCERTAIN' ||
      c.verdict === 'NO_BRICK' ||
      c.action === 'REGRASP_TRIGGERED' ||
      (Array.isArray(c.views) && c.views.length > 1)
  ).length;

  const acceptancePct = total > 0 ? Math.round((accepted / total) * 100) : 0;
  const timedCycles = cycles.filter(c => typeof c.cycle_s === 'number' && c.cycle_s > 0);
  const avgCycleS =
    timedCycles.length > 0
      ? timedCycles.reduce((acc, c) => acc + c.cycle_s, 0) / timedCycles.length
      : null;

  const realCount = cycles.filter(c => (c.evidence || '').toUpperCase() === 'REAL').length;
  const replayCount = cycles.filter(c => (c.evidence || '').toUpperCase() === 'REPLAY').length;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 w-full">
      <StatCard
        label="Bricks Inspected"
        value={total}
        subtext={
          avgCycleS !== null
            ? `${avgCycleS.toFixed(1)}s / brick`
            : realCount > 0
            ? `${realCount} REAL`
            : `${replayCount} REPLAY`
        }
        accent="neutral"
        delay={0}
      />
      <StatCard
        label="Good Bowl (< t_low)"
        value={accepted}
        subtext={`${acceptancePct}% pass rate`}
        accent="good"
        delay={0.05}
        barPct={acceptancePct}
      />
      <StatCard
        label="Defect Bowl (> t_high)"
        value={defective}
        subtext="Audited · B300"
        accent="defect"
        delay={0.1}
        barPct={total > 0 ? Math.round((defective / total) * 100) : 0}
      />
      <StatCard
        label="Multi-View Recovery"
        value={regrasps}
        subtext="t_low – t_high band"
        accent="warn"
        delay={0.15}
      />
    </div>
  );
}
