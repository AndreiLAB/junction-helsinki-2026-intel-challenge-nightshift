import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { X, Database, Terminal, CloudLightning } from 'lucide-react';

const API_BASE =
  import.meta.env.VITE_API_URL ||
  (window.location.port === '5173'
    ? 'http://localhost:8000'
    : window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : '');

export default function CycleModal({ cycle, policyBounds, onClose }) {
  const [fetchedSimilar, setFetchedSimilar] = useState([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);

  const cycleId = cycle?.cycle_id;
  const hasInlineSimilar = Boolean(cycle?.similar_defects && cycle.similar_defects.length > 0);

  useEffect(() => {
    if (!cycleId || hasInlineSimilar) {
      setLoadingSimilar(false);
      return;
    }
    let cancelled = false;
    setLoadingSimilar(true);
    fetch(`${API_BASE}/api/cycles/${encodeURIComponent(cycleId)}/similar`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) {
          setFetchedSimilar(Array.isArray(data) ? data : data.similar_defects || []);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingSimilar(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cycleId, hasInlineSimilar]);

  if (!cycle) return null;

  const verdict = (
    cycle.verdict ||
    (cycle.action === 'DEFECTIVE_BOWL'
      ? 'DEFECT'
      : cycle.action === 'REGRASP_TRIGGERED'
      ? 'UNCERTAIN'
      : 'GOOD')
  ).toUpperCase();

  const isDefective = verdict === 'DEFECT';
  const isRegrasp = verdict === 'UNCERTAIN' || verdict === 'NO_BRICK';
  const similarDefects = hasInlineSimilar ? cycle.similar_defects : fetchedSimilar;
  const topNeighbors = (similarDefects || []).slice(0, 3);
  const tLow = Number(cycle.t_low ?? policyBounds?.t_low ?? 0.45);
  const tHigh = Number(cycle.t_high ?? policyBounds?.t_high ?? 0.60);
  const scoreVal = Number(cycle.score ?? cycle.anomaly_score ?? 0);
  const views = Array.isArray(cycle.views) ? cycle.views : [];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-4"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.94, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ type: 'spring', stiffness: 320, damping: 26 }}
        onClick={(e) => e.stopPropagation()}
        className="glass-panel rounded-2xl max-w-3xl w-full p-5 max-h-[88vh] flex flex-col overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-3 pb-3.5 border-b border-white/[0.07]">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[14px] font-mono font-semibold text-[#edf2f7]">{cycle.cycle_id}</span>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold ${
                isDefective
                  ? 'bg-[#38232c] text-[#f28d95]'
                  : isRegrasp
                  ? 'bg-[#352e21] text-[#e9bf79]'
                  : 'bg-[#15352e] text-[#55dbb1]'
              }`}
            >
              {verdict} · {scoreVal.toFixed(3)}
            </span>
            <span className="text-[11px] font-mono text-[#8e9bae] capitalize">{cycle.color} brick</span>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-[#8e9bae] hover:text-[#edf2f7] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="overflow-y-auto space-y-4 pt-4 pr-1">
          {/* Cloudinary 3-Way Gallery */}
          {(cycle.raw_url || cycle.heatmap_url || cycle.composite_url) && (
            <div className="grid grid-cols-3 gap-2.5">
              {[
                { label: '01 · Optical RGB', url: cycle.raw_url, accent: 'text-[#8e9bae]' },
                { label: '02 · PatchCore Map', url: cycle.heatmap_url || cycle.composite_url, accent: 'text-[#f28d95]' },
                { label: '03 · Cloudinary Overlay', url: cycle.composite_url || cycle.raw_url, accent: 'text-[#55dbb1]' },
              ].map((img) => (
                <div key={img.label} className="glass-subtle rounded-xl p-2 space-y-1.5">
                  <div className={`text-[10px] font-mono ${img.accent}`}>{img.label}</div>
                  <div className="aspect-square rounded-lg overflow-hidden bg-black">
                    {img.url && <img src={img.url} alt={img.label} className="w-full h-full object-cover" />}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* VLA + Nemotron Reasoning */}
          <div className="glass-subtle rounded-xl p-3.5 space-y-2.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-[11.5px] font-mono">
                <Terminal className="w-3.5 h-3.5 text-[#89b9ef]" />
                <span className="text-[#edf2f7]">&ldquo;{cycle.instruction || 'Put the brick in the bowl.'}&rdquo;</span>
              </div>
              {views.length > 0 && (
                <div className="flex items-center gap-1.5">
                  {views.map((v, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-white/[0.05] text-[10px] font-mono text-[#89b9ef]">
                      {v.view}: {Number(v.score ?? 0).toFixed(2)}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div className="p-3 rounded-lg bg-[#06090f] border border-white/[0.06] space-y-1">
              <div className="flex items-center justify-between text-[10.5px] font-mono">
                <span className="text-[#89b9ef]">Nemotron 3.5 Super VL Diagnosis</span>
                <span className="text-[#55dbb1]">
                  {cycle.nemotron_provider === 'verda_b300' ? 'Verda B300 · LIVE' : 'Fallback'}
                </span>
              </div>
              <p className="text-[12.5px] text-[#edf2f7] leading-relaxed">
                &ldquo;{cycle.nemotron_reasoning || cycle.root_cause_reasoning || 'Pristine stud topology.'}&rdquo;
              </p>
            </div>

            {cycle.modal_escalation?.triggered && (
              <div className="flex items-center justify-between text-[11px] font-mono text-[#c4a7ea] px-1">
                <span className="flex items-center gap-1.5">
                  <CloudLightning className="w-3.5 h-3.5" /> Modal Serverless Archive
                </span>
                <span>{cycle.modal_escalation.archive_path || cycle.modal_escalation.provider}</span>
              </div>
            )}
          </div>

          {/* MariaDB VECTOR(512) Defect Twins */}
          <div className="glass-subtle rounded-xl p-3.5 space-y-2.5">
            <div className="flex items-center justify-between text-[11.5px]">
              <span className="flex items-center gap-2 font-semibold text-[#edf2f7]">
                <Database className="w-3.5 h-3.5 text-[#55dbb1]" />
                MariaDB 11.8 VECTOR(512) Cosine Defect Twins
              </span>
              <span className="font-mono text-[10.5px] text-[#8e9bae]">
                t_low {tLow.toFixed(2)} · t_high {tHigh.toFixed(2)}
              </span>
            </div>

            {loadingSimilar ? (
              <div className="text-[11px] font-mono text-[#8e9bae] py-2">Querying VEC_DISTANCE_COSINE…</div>
            ) : topNeighbors.length === 0 ? (
              <div className="text-[11px] text-[#8e9bae] py-1">No historical defect vectors matched yet.</div>
            ) : (
              <div className="space-y-2">
                {topNeighbors.map((m, idx) => {
                  const pct = parseFloat(m.similarity_pct ?? (m.similarity ? m.similarity * 100 : 0)) || 0;
                  return (
                    <div key={m.cycle_id || idx} className="bg-[#06090f] rounded-lg p-2.5 border border-white/[0.05] space-y-1.5">
                      <div className="flex items-center justify-between text-[11px] font-mono">
                        <span className="text-[#edf2f7]">
                          {m.cycle_id} · <span className="text-[#8e9bae]">{m.defect_label || m.action}</span>
                        </span>
                        <span className="text-[#55dbb1] font-semibold">{pct.toFixed(1)}% match</span>
                      </div>
                      <div className="h-1.5 w-full bg-white/[0.05] rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.min(100, pct)}%` }}
                          transition={{ duration: 0.5, delay: idx * 0.08 }}
                          className="h-full rounded-full bg-gradient-to-r from-[#89b9ef] to-[#55dbb1]"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}
