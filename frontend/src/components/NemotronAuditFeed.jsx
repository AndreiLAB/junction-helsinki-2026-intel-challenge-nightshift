import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { History, ArrowUpRight } from 'lucide-react';

export default function NemotronAuditFeed({
  cycles = [],
  onSelectCycle,
  maxItems = 5,
  title = 'Live Inspection Stream',
  onOpenArchiveTab,
}) {
  const visible = maxItems ? cycles.slice(0, maxItems) : cycles;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.24 }}
      className="glass-panel rounded-xl p-4 flex flex-col justify-between flex-1 min-h-0"
    >
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-[#89b9ef]" />
            <h3 className="text-[14px] font-semibold text-[#edf2f7]">{title}</h3>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono text-[#8e9bae] tabular-nums">
              {cycles.length} total
            </span>
            {onOpenArchiveTab && cycles.length > maxItems && (
              <button
                onClick={onOpenArchiveTab}
                className="text-[11px] text-[#55dbb1] hover:underline flex items-center gap-0.5"
              >
                All <ArrowUpRight className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        <div className="space-y-2 overflow-y-auto pr-0.5 max-h-[360px]">
          <AnimatePresence initial={false}>
            {visible.length === 0 ? (
              <div className="py-8 text-center text-[12px] text-[#8e9bae]">
                Waiting for brick inspection events…
              </div>
            ) : (
              visible.map((cyc) => {
                const verdict = (
                  cyc.verdict ||
                  (cyc.action === 'DEFECTIVE_BOWL'
                    ? 'DEFECT'
                    : cyc.action === 'REGRASP_TRIGGERED'
                    ? 'UNCERTAIN'
                    : 'GOOD')
                ).toUpperCase();

                const isDefect = verdict === 'DEFECT';
                const isWarn = verdict === 'UNCERTAIN' || verdict === 'NO_BRICK';
                const scoreVal = Number(cyc.score ?? cyc.anomaly_score ?? 0);
                const viewsCount = Array.isArray(cyc.views) ? cyc.views.length : 0;

                const verdictTone = isDefect
                  ? 'text-[#f28d95] bg-[#38232c]/80'
                  : isWarn
                  ? 'text-[#e9bf79] bg-[#352e21]/80'
                  : 'text-[#55dbb1] bg-[#15352e]/80';

                const brickHex =
                  cyc.color === 'yellow'
                    ? '#f59e0b'
                    : cyc.color === 'red'
                    ? '#f43f5e'
                    : cyc.color === 'blue'
                    ? '#3b82f6'
                    : '#10b981';

                return (
                  <motion.button
                    layout
                    key={cyc.cycle_id}
                    initial={{ opacity: 0, x: 14, scale: 0.97 }}
                    animate={{ opacity: 1, x: 0, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    whileHover={{ x: 2, backgroundColor: 'rgba(255,255,255,0.05)' }}
                    transition={{ type: 'spring', stiffness: 340, damping: 28 }}
                    onClick={() => onSelectCycle(cyc)}
                    className="w-full text-left glass-subtle rounded-lg p-2.5 flex items-center gap-3 transition-colors group"
                  >
                    {/* Crisp Color / Thumbnail Tile */}
                    <div className="relative w-11 h-11 rounded-lg overflow-hidden bg-[#06090f] border border-white/[0.08] shrink-0 flex items-center justify-center">
                      {cyc.composite_url || cyc.raw_url ? (
                        <img
                          src={cyc.composite_url || cyc.raw_url}
                          alt={cyc.cycle_id}
                          className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                        />
                      ) : (
                        <div className="w-5 h-5 rounded" style={{ backgroundColor: brickHex }} />
                      )}
                      <span
                        className={`absolute bottom-0 inset-x-0 text-center text-[9px] font-mono font-semibold py-0.2 ${verdictTone}`}
                      >
                        {scoreVal.toFixed(2)}
                      </span>
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: brickHex }} />
                          <span className="text-[11.5px] font-mono font-semibold text-[#edf2f7] truncate">
                            {cyc.brick_idx != null ? `Brick #${cyc.brick_idx}` : cyc.cycle_id}
                          </span>
                          {viewsCount > 1 && (
                            <span className="text-[9.5px] font-mono text-[#e9bf79]">
                              {viewsCount}v
                            </span>
                          )}
                        </div>
                        <span className={`px-1.5 py-0.5 rounded text-[9.5px] font-mono font-semibold shrink-0 ${verdictTone}`}>
                          {verdict}
                        </span>
                      </div>

                      <div className="text-[11px] text-[#b5c0ce] truncate mt-0.5">
                        {cyc.defect_label && cyc.defect_label !== 'None (Pristine)'
                          ? cyc.defect_label
                          : cyc.instruction || 'Sorted cleanly'}
                      </div>

                      <div className="text-[10px] text-[#8e9bae] font-mono truncate mt-0.5">
                        {cyc.nemotron_reasoning
                          ? cyc.nemotron_reasoning
                          : `${cyc.evidence || 'MOCK'} · ${cyc.timestamp || ''}`}
                      </div>
                    </div>
                  </motion.button>
                );
              })
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
