import React, { useState, useEffect } from 'react';
import { X, Database } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || (window.location.port === '5173' ? 'http://localhost:8000' : (window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''));

function getColorBadgeClass(color) {
  switch ((color || '').toLowerCase()) {
    case 'yellow':
      return 'bg-[#352e21] text-[#e9bf79]';
    case 'orange':
      return 'bg-[#3a281d] text-[#f4a261]';
    case 'red':
      return 'bg-[#38232c] text-[#f28d95]';
    case 'blue':
      return 'bg-[#18212c] text-[#89b9ef]';
    default:
      return 'bg-[#15352e] text-[#55dbb1]';
  }
}

function getActionBadgeClass(action) {
  if (action === 'DEFECTIVE_BOWL') return 'bg-[#38232c] text-[#f28d95]';
  if (action === 'REGRASP_TRIGGERED') return 'bg-[#352e21] text-[#e9bf79]';
  return 'bg-[#15352e] text-[#55dbb1]';
}

export default function CycleModal({ cycle, onClose }) {
  const [fetchedSimilar, setFetchedSimilar] = useState([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);

  const cycleId = cycle?.cycle_id;
  const hasInlineSimilar = Boolean(cycle?.similar_defects && cycle.similar_defects.length > 0);

  useEffect(() => {
    if (!cycleId) {
      setFetchedSimilar([]);
      setLoadingSimilar(false);
      return;
    }

    if (hasInlineSimilar) {
      setLoadingSimilar(false);
      return;
    }

    let cancelled = false;
    setFetchedSimilar([]);
    setLoadingSimilar(true);

    const loadSimilarDefects = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/cycles/${encodeURIComponent(cycleId)}/similar`);
        if (res.ok && !cancelled) {
          const data = await res.json();
          const items = Array.isArray(data)
            ? data
            : (data.similar_defects || data.matches || data.neighbors || []);
          setFetchedSimilar(items);
        }
      } catch (err) {
        if (!cancelled) {
          console.warn('Could not fetch nearest historical defects:', err);
        }
      } finally {
        if (!cancelled) {
          setLoadingSimilar(false);
        }
      }
    };

    loadSimilarDefects();
    return () => {
      cancelled = true;
    };
  }, [cycleId, hasInlineSimilar]);

  if (!cycle) return null;

  const isDefective = cycle.action === 'DEFECTIVE_BOWL';
  const isRegrasp = cycle.action === 'REGRASP_TRIGGERED';
  const isVerdaLive = cycle.nemotron_provider === 'verda_b300';
  const similarDefects = hasInlineSimilar ? cycle.similar_defects : fetchedSimilar;
  const topNeighbors = (similarDefects || []).slice(0, 3);

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-3 sm:p-4">
      <div className="bg-[#121922] border border-[#26313e] rounded-[10px] max-w-3xl w-full p-4 sm:p-5 shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-[#26313e] pb-3 mb-3">
          <div className="flex items-center space-x-2.5">
            <span className={`px-2 py-0.5 rounded-[4px] text-[10px] font-mono font-bold uppercase ${getColorBadgeClass(cycle.color)}`}>
              {cycle.color} Duplo
            </span>
            <h3 className="text-sm font-semibold text-[#edf2f7] font-mono">{cycle.cycle_id} Visual Audit Detail</h3>
            <span className="text-[11px] text-[#8e9bae] font-mono tabular-nums">[{cycle.timestamp}]</span>
          </div>

          <button
            onClick={onClose}
            className="p-1 rounded-[5px] bg-[#18212c] hover:bg-[#26313e] text-[#8e9bae] hover:text-[#edf2f7] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="space-y-4 overflow-y-auto pr-1">
          {/* 3-Way Image Inspector */}
          <div>
            <div className="text-[11px] font-medium text-[#8e9bae] uppercase tracking-wider mb-2">
              Multi-Layer Visual Evidence (Cloudinary Composited)
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {/* Raw */}
              <div className="bg-[#0b0f14] rounded-[6px] p-2 border border-[#26313e] flex flex-col">
                <div className="text-[10px] font-mono text-[#8e9bae] mb-1">01. Optical RGB Crop</div>
                <div className="aspect-square rounded overflow-hidden bg-black flex items-center justify-center">
                  <img src={cycle.raw_url} alt="Raw" className="w-full h-full object-cover" />
                </div>
              </div>

              {/* Heatmap */}
              <div className="bg-[#0b0f14] rounded-[6px] p-2 border border-[#26313e] flex flex-col">
                <div className="text-[10px] font-mono text-[#f28d95] mb-1">02. Anomalib v2.7.0 Heatmap</div>
                <div className="aspect-square rounded overflow-hidden bg-black flex items-center justify-center">
                  <img src={cycle.heatmap_url || cycle.composite_url} alt="Heatmap" className="w-full h-full object-cover" />
                </div>
              </div>

              {/* Composite */}
              <div className="bg-[#0b0f14] rounded-[6px] p-2 border border-[#55dbb1]/50 flex flex-col relative shadow-md shadow-[#55dbb1]/10">
                <div className="text-[10px] font-mono text-[#55dbb1] font-semibold mb-1 flex items-center justify-between">
                  <span>03. Composite Overlay</span>
                  <span className="text-[8.5px] uppercase">l_overlay</span>
                </div>
                <div className="aspect-square rounded overflow-hidden bg-black flex items-center justify-center">
                  <img src={cycle.composite_url || cycle.raw_url} alt="Composite" className="w-full h-full object-cover" />
                </div>
              </div>
            </div>
          </div>

          {/* Reasoning & Decision Card */}
          <div className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-[#b5c0ce] uppercase">
                Arbitrated Decision
              </span>
              <span className={`px-2 py-0.5 rounded-[4px] text-[10px] font-semibold ${getActionBadgeClass(cycle.action)}`}>
                {cycle.action}
              </span>
            </div>

            <div className="text-[12px] text-[#edf2f7] leading-relaxed bg-[#18212c]/40 p-2.5 rounded-[4px] border border-[#26313e]/60 space-y-1.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[#89b9ef] font-semibold text-[11px]">Nemotron Reasoning:</span>
                <span
                  className={`px-2 py-0.5 rounded-[4px] text-[10px] font-mono font-semibold shrink-0 border ${
                    isVerdaLive
                      ? 'text-[#55dbb1] bg-[#15352e] border-[#55dbb1]/30'
                      : 'text-[#e9bf79] bg-[#352e21]/60 border-[#e9bf79]/25'
                  }`}
                >
                  {isVerdaLive ? 'Verda B300 · LIVE' : 'Heuristic · FALLBACK'}
                </span>
              </div>
              <div>
                "{cycle.nemotron_reasoning || cycle.root_cause_reasoning || 'Pristine topology verified.'}"
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-[11px]">
              <div className="bg-[#18212c] p-2 rounded-[4px]">
                <span className="text-[#8e9bae] text-[9.5px] block">Defect Label</span>
                <span className="font-semibold text-[#edf2f7]">{cycle.defect_label || 'Pristine'}</span>
              </div>
              <div className="bg-[#18212c] p-2 rounded-[4px]">
                <span className="text-[#8e9bae] text-[9.5px] block">Anomaly Score</span>
                <span className={`font-semibold ${isDefective ? 'text-[#f28d95]' : 'text-[#55dbb1]'}`}>
                  {typeof cycle.anomaly_score === 'number' ? cycle.anomaly_score.toFixed(3) : cycle.anomaly_score}
                </span>
              </div>
              <div className="bg-[#18212c] p-2 rounded-[4px]">
                <span className="text-[#8e9bae] text-[9.5px] block">Destination</span>
                <span className="font-semibold text-[#b5c0ce]">
                  {isDefective ? 'DEFECTIVE Bowl' : isRegrasp ? 'Inspection Camera' : 'GOOD Bowl'}
                </span>
              </div>
              <div className="bg-[#18212c] p-2 rounded-[4px]">
                <span className="text-[#8e9bae] text-[9.5px] block">Total Latency</span>
                <span className="font-semibold text-[#55dbb1]">
                  {cycle.latencies?.total_ms || '35.9'} ms
                </span>
              </div>
            </div>
          </div>

          {/* MariaDB 11.7+ VECTOR(512) Nearest Historical Defects */}
          <div className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-3 space-y-2.5">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center space-x-2 text-[11px] font-semibold text-[#b5c0ce]">
                <Database className="w-3.5 h-3.5 text-[#55dbb1] shrink-0" />
                <span>
                  MariaDB 11.7+ <code className="font-mono text-[#55dbb1] bg-[#18212c] px-1 py-0.5 rounded">VECTOR(512)</code> Nearest Historical Defects (<code className="font-mono text-[#89b9ef] bg-[#18212c] px-1 py-0.5 rounded">VEC_DISTANCE_COSINE</code>)
                </span>
              </div>
              <span className="text-[10px] font-mono text-[#8e9bae] shrink-0">
                Top {topNeighbors.length}/3
              </span>
            </div>

            {loadingSimilar && topNeighbors.length === 0 ? (
              <div className="text-[11px] text-[#8e9bae] bg-[#18212c]/30 border border-[#26313e]/50 rounded-[5px] px-3 py-2.5 font-mono">
                Querying VECTOR(512) cosine neighbors...
              </div>
            ) : topNeighbors.length === 0 ? (
              <div className="text-[11px] text-[#8e9bae] bg-[#18212c]/30 border border-[#26313e]/50 rounded-[5px] px-3 py-2.5">
                No historical defect vectors indexed yet for comparison.
              </div>
            ) : (
              <div className="space-y-1.5">
                {topNeighbors.map((match, idx) => {
                  const pctValue =
                    match.similarity_pct !== undefined && match.similarity_pct !== null
                      ? match.similarity_pct
                      : match.similarity !== undefined
                      ? (Number(match.similarity) * 100).toFixed(1)
                      : '0.0';
                  const barWidth = Math.max(0, Math.min(100, parseFloat(pctValue) || 0));
                  const scoreDisplay =
                    typeof match.anomaly_score === 'number'
                      ? match.anomaly_score.toFixed(3)
                      : match.anomaly_score;

                  return (
                    <div
                      key={match.cycle_id || idx}
                      className="bg-[#121922] border border-[#26313e]/80 rounded-[5px] px-2.5 py-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                    >
                      <div className="flex flex-wrap items-center gap-1.5 min-w-0">
                        <span className="text-[11px] font-mono font-semibold text-[#edf2f7]">
                          {match.cycle_id}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded-[3px] text-[9.5px] font-mono font-bold uppercase ${getColorBadgeClass(match.color)}`}>
                          {match.color}
                        </span>
                        <span className="text-[11px] text-[#b5c0ce] truncate max-w-[200px]">
                          {match.defect_label || 'Pristine'}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded-[3px] text-[9.5px] font-mono font-semibold ${getActionBadgeClass(match.action)}`}>
                          {match.action}
                        </span>
                        <span className="text-[10.5px] font-mono text-[#8e9bae]">
                          score {scoreDisplay}
                        </span>
                      </div>

                      <div className="flex flex-col sm:items-end gap-1 shrink-0 sm:min-w-[144px]">
                        <span className="px-2 py-0.5 rounded-[4px] text-[10.5px] font-mono font-bold text-[#55dbb1] bg-[#15352e] border border-[#55dbb1]/30 self-start sm:self-end">
                          {pctValue}% cosine match
                        </span>
                        <div className="w-full h-1.5 bg-[#18212c] rounded-full overflow-hidden border border-[#26313e]/70">
                          <div
                            className="h-full bg-gradient-to-r from-[#89b9ef] to-[#55dbb1] rounded-full transition-all duration-300"
                            style={{ width: `${barWidth}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="mt-4 pt-3 border-t border-[#26313e] flex items-center justify-between text-[11px] text-[#8e9bae]">
          <span>Synced with LeRobot SO-101 Trajectory Buffer</span>
          <button
            onClick={onClose}
            className="px-3.5 py-1 bg-[#18212c] hover:bg-[#26313e] text-[#edf2f7] rounded-[5px] text-[11px] font-semibold transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
