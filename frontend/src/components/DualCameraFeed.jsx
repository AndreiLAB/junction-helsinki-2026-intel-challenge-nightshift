import React, { useState } from 'react';
import { CheckCircle, AlertTriangle, RotateCcw, Terminal } from 'lucide-react';

function getEvidenceBadge(evidence) {
  const ev = (evidence || 'MOCK').toUpperCase();
  if (ev === 'REAL') {
    return {
      label: 'REAL',
      cls: 'bg-[#15352e] text-[#55dbb1] border-[#55dbb1]/40',
    };
  }
  if (ev === 'REPLAY') {
    return {
      label: 'REPLAY',
      cls: 'bg-[#18212c] text-[#89b9ef] border-[#89b9ef]/40',
    };
  }
  return {
    label: 'MOCK',
    cls: 'bg-[#352e21]/60 text-[#e9bf79] border-[#e9bf79]/30',
  };
}

export default function DualCameraFeed({ currentCycle, cellState = 'HOME', policyBounds }) {
  const [viewMode, setViewMode] = useState('overlay'); // 'overlay' | 'heatmap' | 'raw'

  const score = Number(currentCycle?.score ?? currentCycle?.anomaly_score ?? 0.104);
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
    verdict === 'UNCERTAIN' ||
    verdict === 'NO_BRICK' ||
    currentCycle?.action === 'REGRASP_TRIGGERED';

  const scorePct = Math.min(Math.max(score * 100, 1.5), 100);
  const tLowPct = Math.min(Math.max(tLow * 100, 5), 90);
  const tHighPct = Math.min(Math.max(tHigh * 100, tLowPct + 4), 96);

  const views = Array.isArray(currentCycle?.views) ? currentCycle.views : [];
  const activeCellState = (currentCycle?.cell_state || cellState || 'HOME').toUpperCase();
  const cycleS = typeof currentCycle?.cycle_s === 'number' ? currentCycle.cycle_s : null;
  const evidenceBadge = getEvidenceBadge(currentCycle?.evidence);

  const defaultInstruction = isDefective
    ? 'Put the brick in the defective bowl.'
    : isRegrasp
    ? 'Pick up a brick and hold it in front of the inspection camera.'
    : 'Put the brick in the good bowl.';
  const instruction = currentCycle?.instruction || defaultInstruction;

  const modelBadgeText = [
    currentCycle?.model || 'patchcore_256',
    currentCycle?.precision || 'INT8',
    currentCycle?.device || 'NPU',
  ]
    .filter(Boolean)
    .join(' · ');

  // Status Badge in Header
  let statusBadge = (
    <div className="bg-[#15352e] border border-[#55dbb1]/30 px-2.5 py-1 rounded-[5px] flex items-center space-x-1.5">
      <CheckCircle className="w-3.5 h-3.5 text-[#55dbb1]" />
      <span className="text-[11px] font-semibold font-mono text-[#55dbb1]">GOOD · Bowl #1</span>
    </div>
  );

  if (isDefective) {
    statusBadge = (
      <div className="bg-[#38232c] border border-[#f28d95]/30 px-2.5 py-1 rounded-[5px] flex items-center space-x-1.5">
        <AlertTriangle className="w-3.5 h-3.5 text-[#f28d95]" />
        <span className="text-[11px] font-semibold font-mono text-[#f28d95]">DEFECT · Bowl #2</span>
      </div>
    );
  } else if (isRegrasp) {
    statusBadge = (
      <div className="bg-[#352e21] border border-[#e9bf79]/30 px-2.5 py-1 rounded-[5px] flex items-center space-x-1.5">
        <RotateCcw className="w-3.5 h-3.5 text-[#e9bf79]" />
        <span className="text-[11px] font-semibold font-mono text-[#e9bf79]">
          {verdict === 'NO_BRICK' ? 'NO_BRICK · Recovery' : 'UNCERTAIN · Multi-View / Re-grasp'}
        </span>
      </div>
    );
  }

  // Active Image
  let activeImage = currentCycle?.composite_url;
  if (viewMode === 'heatmap') {
    activeImage = currentCycle?.heatmap_url || currentCycle?.composite_url;
  } else if (viewMode === 'raw') {
    activeImage = currentCycle?.raw_url;
  }

  const brickColor = currentCycle?.color || 'green';
  const colorDisplay = `${brickColor.charAt(0).toUpperCase() + brickColor.slice(1)} brick`;

  const barFillColor =
    score >= tHigh || isDefective
      ? 'bg-[#f28d95]'
      : score >= tLow || isRegrasp
      ? 'bg-[#e9bf79]'
      : 'bg-[#55dbb1]';

  return (
    <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-4 flex flex-col justify-between h-full">
      {/* Top Header */}
      <div>
        <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#26313e]">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[16px] font-semibold text-[#edf2f7]">
              Live inspection
            </h2>
            <span className={`px-2 py-0.5 rounded-[4px] border font-mono text-[10px] font-semibold ${evidenceBadge.cls}`}>
              {evidenceBadge.label}
            </span>
            <span className="px-2 py-0.5 rounded-[4px] border border-[#26313e] bg-[#18212c] font-mono text-[10px] text-[#b5c0ce]">
              {activeCellState}
            </span>
            {cycleS !== null && (
              <span className="px-2 py-0.5 rounded-[4px] border border-[#89b9ef]/25 bg-[#18212c] font-mono text-[10px] text-[#89b9ef]">
                {cycleS.toFixed(1)}s / brick
              </span>
            )}
          </div>
          <div>{statusBadge}</div>
        </div>

        {/* Subheaders & Mode Switcher */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2.5 items-center">
          {/* Overhead camera label */}
          <div className="flex items-center space-x-2">
            <div className="w-1.5 h-1.5 rounded-full bg-[#55dbb1] animate-pulse" />
            <div>
              <div className="text-[12px] font-medium text-[#b5c0ce] leading-tight font-mono">
                CAM-01 // Top-View Workspace (Duplo Plate &amp; Bowls)
              </div>
              <div className="text-[10px] text-[#8e9bae] leading-tight mt-0.5">
                Overhead RGB · VLA / ACT Workspace Context
              </div>
            </div>
          </div>

          {/* Inspection Camera label & Switcher */}
          <div className="flex items-center justify-between sm:justify-end space-x-3">
            <div className="flex items-center space-x-2">
              <div className="w-1.5 h-1.5 rounded-full bg-[#89b9ef]" />
              <div className="text-[12px] font-medium text-[#b5c0ce] font-mono">
                CAM-02 // Inspection Backdrop ROI
              </div>
            </div>

            {/* Mode Pills Switcher */}
            <div className="bg-[#0b0f14] border border-[#26313e] rounded-[5px] p-0.5 flex items-center space-x-0.5">
              <button
                onClick={() => setViewMode('overlay')}
                className={`px-2.5 py-0.5 rounded-[3px] text-[10px] font-medium transition-colors ${
                  viewMode === 'overlay'
                    ? 'bg-[#18212c] text-[#edf2f7]'
                    : 'text-[#8e9bae] hover:text-[#edf2f7]'
                }`}
              >
                Overlay
              </button>
              <button
                onClick={() => setViewMode('heatmap')}
                className={`px-2.5 py-0.5 rounded-[3px] text-[10px] font-medium transition-colors ${
                  viewMode === 'heatmap'
                    ? 'bg-[#18212c] text-[#edf2f7]'
                    : 'text-[#8e9bae] hover:text-[#edf2f7]'
                }`}
              >
                Heatmap
              </button>
              <button
                onClick={() => setViewMode('raw')}
                className={`px-2.5 py-0.5 rounded-[3px] text-[10px] font-medium transition-colors ${
                  viewMode === 'raw'
                    ? 'bg-[#18212c] text-[#edf2f7]'
                    : 'text-[#8e9bae] hover:text-[#edf2f7]'
                }`}
              >
                Raw
              </button>
            </div>
          </div>
        </div>

        {/* Video / Camera Feeds Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 my-2">
          {/* CAM 01: Overhead Feed or Workspace Trajectory */}
          <div className="relative aspect-[409/218] w-full rounded-[6px] overflow-hidden border border-[#26313e] bg-[#0c1520] flex items-center justify-center">
            <div className="absolute left-2.5 top-2.5 bg-[#121922]/90 border border-[#26313e]/60 px-2 py-0.5 rounded-[4px] z-10">
              <span className="text-[10px] font-mono font-medium text-[#b5c0ce]">CAM 01 // TOP-VIEW</span>
            </div>
            <div className="absolute left-2.5 bottom-2.5 bg-[#121922]/90 border border-[#26313e]/60 px-2 py-0.5 rounded-[4px] z-10">
              <span className="text-[10px] font-mono font-medium text-[#b5c0ce]">SO-ARM101 CELL</span>
            </div>

            {currentCycle?.top_url ? (
              <img
                src={currentCycle.top_url}
                alt="Top workspace camera"
                className="w-full h-full object-cover"
              />
            ) : (
              <svg className="w-full h-full p-2" viewBox="0 0 300 180" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="10" y="10" width="280" height="160" rx="8" stroke="#1e293b" strokeWidth="1" strokeDasharray="3 3" />

                {/* GOOD Bowl */}
                <circle cx="55" cy="50" r="28" fill="#15352e" stroke="#55dbb1" strokeWidth="1.2" />
                <text x="55" y="48" textAnchor="middle" fill="#55dbb1" fontSize="7.5" fontFamily="monospace" fontWeight="600">GOOD BOWL</text>
                <text x="55" y="58" textAnchor="middle" fill="#8e9bae" fontSize="6.5" fontFamily="monospace">Bowl #1</text>

                {/* DEFECTIVE Bowl */}
                <circle cx="245" cy="50" r="28" fill="#38232c" stroke="#f28d95" strokeWidth="1.2" />
                <text x="245" y="48" textAnchor="middle" fill="#f28d95" fontSize="7.5" fontFamily="monospace" fontWeight="600">DEFECTIVE BOWL</text>
                <text x="245" y="58" textAnchor="middle" fill="#8e9bae" fontSize="6.5" fontFamily="monospace">Bowl #2</text>

                {/* Central Source Duplo Plate */}
                <circle cx="150" cy="115" r="42" fill="#0b0f14" stroke="#89b9ef" strokeWidth="1.2" strokeDasharray="2 2" />
                <circle cx="150" cy="115" r="2.5" fill="#89b9ef" />
                <text x="150" y="85" textAnchor="middle" fill="#8e9bae" fontSize="6.5" fontFamily="monospace">SOURCE DUPLO PLATE</text>

                {/* Duplo Brick */}
                <rect
                  x="138"
                  y="103"
                  width="24"
                  height="24"
                  rx="3"
                  fill={
                    brickColor === 'yellow'
                      ? '#f59e0b'
                      : brickColor === 'red'
                      ? '#ef4444'
                      : brickColor === 'blue'
                      ? '#3b82f6'
                      : '#55dbb1'
                  }
                  stroke="#ffffff"
                  strokeWidth="1.2"
                />

                {/* Arm Trajectory line */}
                {isDefective ? (
                  <path d="M 150 115 Q 195 70 245 50" stroke="#f28d95" strokeWidth="1.6" strokeDasharray="3 3" fill="none" />
                ) : isRegrasp ? (
                  <circle cx="150" cy="115" r="22" stroke="#e9bf79" strokeWidth="1.5" strokeDasharray="3 2" fill="none" />
                ) : (
                  <path d="M 150 115 Q 105 70 55 50" stroke="#55dbb1" strokeWidth="1.6" strokeDasharray="3 3" fill="none" />
                )}
              </svg>
            )}
          </div>

          {/* CAM 02: Close-Up Inspection ROI */}
          <div className="relative aspect-[409/218] w-full rounded-[6px] overflow-hidden border border-[#26313e] bg-[#070c1c] flex items-center justify-center">
            <div className="absolute left-2.5 top-2.5 bg-[#121922]/90 border border-[#26313e]/60 px-2 py-0.5 rounded-[4px] z-10">
              <span className="text-[10px] font-mono font-medium text-[#b5c0ce]">CAM 02 // BACKDROP ROI</span>
            </div>

            <div className="absolute right-2.5 top-2.5 bg-[#121922]/90 border border-[#26313e]/80 px-2 py-0.5 rounded-[4px] z-10">
              <span className="text-[9.5px] font-mono text-[#89b9ef]">{modelBadgeText}</span>
            </div>

            <div
              className={`absolute right-2.5 bottom-2.5 px-2.5 py-0.5 rounded-[4px] z-10 border ${
                isDefective
                  ? 'bg-[#38232c] text-[#f28d95] border-[#f28d95]/30'
                  : isRegrasp
                  ? 'bg-[#352e21] text-[#e9bf79] border-[#e9bf79]/30'
                  : 'bg-[#15352e] text-[#55dbb1] border-[#55dbb1]/30'
              }`}
            >
              <span className="text-[10px] font-mono font-semibold">
                {verdict} ({score.toFixed(3)})
              </span>
            </div>

            {/* Display Image or Synthesized Duplo visual */}
            {activeImage ? (
              <img
                src={activeImage}
                alt="Inspection camera crop"
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="relative w-full h-full flex items-center justify-center">
                <div
                  className={`w-32 h-32 rounded-lg flex items-center justify-center relative shadow-lg ${
                    brickColor === 'yellow'
                      ? 'bg-amber-500'
                      : brickColor === 'red'
                      ? 'bg-rose-600'
                      : brickColor === 'blue'
                      ? 'bg-blue-600'
                      : 'bg-emerald-600'
                  }`}
                >
                  <div className="grid grid-cols-2 gap-3">
                    <div className="w-7 h-7 rounded-full bg-white/20 border border-white/30" />
                    <div className="w-7 h-7 rounded-full bg-white/20 border border-white/30" />
                    <div className="w-7 h-7 rounded-full bg-white/20 border border-white/30" />
                    <div className="w-7 h-7 rounded-full bg-white/20 border border-white/30" />
                  </div>
                  {viewMode !== 'raw' && (
                    <div
                      className={`absolute inset-0 rounded-lg pointer-events-none ${
                        isDefective
                          ? 'bg-gradient-to-tr from-transparent via-rose-500/50 to-amber-500/60 mix-blend-color-dodge'
                          : 'bg-emerald-400/20 mix-blend-overlay'
                      }`}
                    />
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* VLA Language Instruction + Multi-View Wrist Scores Strip */}
        <div className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] px-3 py-2 my-1.5 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center space-x-2 min-w-0">
            <Terminal className="w-3.5 h-3.5 text-[#89b9ef] shrink-0" />
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#8e9bae] shrink-0">
              VLA Prompt:
            </span>
            <span
              className={`text-[11.5px] font-mono font-medium truncate ${
                isDefective ? 'text-[#f28d95]' : isRegrasp ? 'text-[#e9bf79]' : 'text-[#55dbb1]'
              }`}
            >
              &ldquo;{instruction}&rdquo;
            </span>
          </div>

          {views.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              {views.map((v, idx) => {
                const vScore = Number(v.score ?? 0);
                const vCls =
                  vScore >= tHigh
                    ? 'border-[#f28d95]/40 text-[#f28d95] bg-[#38232c]/60'
                    : vScore >= tLow
                    ? 'border-[#e9bf79]/40 text-[#e9bf79] bg-[#352e21]/60'
                    : 'border-[#55dbb1]/40 text-[#55dbb1] bg-[#15352e]/60';
                return (
                  <span
                    key={`${v.view || idx}-${idx}`}
                    className={`px-2 py-0.5 rounded-[4px] border text-[10px] font-mono ${vCls}`}
                  >
                    {v.view || `view${idx + 1}`}: {vScore.toFixed(2)}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Dual-Threshold Telemetry Bar (t_low / t_high) */}
      <div className="pt-2 border-t border-[#26313e]/70 space-y-2">
        <div className="flex flex-wrap items-center justify-between text-[11px] gap-2">
          {/* Target */}
          <div className="flex items-center space-x-2">
            <span className="text-[#8e9bae]">Target</span>
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                brickColor === 'yellow'
                  ? 'bg-amber-400'
                  : brickColor === 'red'
                  ? 'bg-rose-400'
                  : brickColor === 'blue'
                  ? 'bg-blue-400'
                  : 'bg-[#55dbb1]'
              }`}
            />
            <span className="font-medium text-[#b5c0ce]">{colorDisplay}</span>
            {currentCycle?.defect_label && currentCycle.defect_label !== 'None (Pristine)' && (
              <span className="text-[10px] font-mono text-[#8e9bae]">
                · {currentCycle.defect_label}
              </span>
            )}
          </div>

          {/* Anomaly Score Readout */}
          <div className="flex items-baseline space-x-2">
            <span className="text-[#8e9bae]">PatchCore score</span>
            <span
              className={`text-[19px] font-semibold tabular-nums leading-none ${
                isDefective ? 'text-[#f28d95]' : isRegrasp ? 'text-[#e9bf79]' : 'text-[#55dbb1]'
              }`}
            >
              {score.toFixed(3)}
            </span>
            <span className="text-[10px] font-mono text-[#8e9bae]">
              t_low {tLow.toFixed(2)} · t_high {tHigh.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Dual-Threshold Progress Track (GOOD < t_low | UNCERTAIN t_low..t_high | DEFECT > t_high) */}
        <div className="relative w-full h-[7px] bg-[#18212c] rounded-[3px] overflow-visible">
          {/* Subtle zone background tint */}
          <div className="absolute inset-0 flex rounded-[3px] overflow-hidden opacity-25 pointer-events-none">
            <div style={{ width: `${tLowPct}%` }} className="bg-[#55dbb1]" />
            <div style={{ width: `${tHighPct - tLowPct}%` }} className="bg-[#e9bf79]" />
            <div style={{ width: `${100 - tHighPct}%` }} className="bg-[#f28d95]" />
          </div>

          {/* Active Score Bar */}
          <div
            className={`relative h-full rounded-[3px] transition-all duration-300 ${barFillColor}`}
            style={{ width: `${Math.min(scorePct, 100)}%` }}
          />

          {/* t_low Marker (0.35) */}
          <div
            className="absolute top-[-4px] bottom-[-4px] w-[2px] bg-[#55dbb1] rounded-[1px] shadow-sm z-10"
            style={{ left: `${tLowPct}%` }}
            title={`t_low (${tLow.toFixed(2)}) — GOOD / UNCERTAIN boundary`}
          />

          {/* t_high Marker (0.60) */}
          <div
            className="absolute top-[-4px] bottom-[-4px] w-[2px] bg-[#f28d95] rounded-[1px] shadow-sm z-10"
            style={{ left: `${tHighPct}%` }}
            title={`t_high (${tHigh.toFixed(2)}) — UNCERTAIN / DEFECT boundary`}
          />
        </div>

        {/* Footer Zone Labels */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-[#8e9bae] font-mono">
          <div className="flex items-center space-x-2">
            <span>SO-101 follower</span>
            <span>•</span>
            <span className={`font-semibold ${isDefective ? 'text-[#f28d95]' : isRegrasp ? 'text-[#e9bf79]' : 'text-[#55dbb1]'}`}>
              {isDefective ? 'DEFECTIVE Bowl' : isRegrasp ? 'Wrist Multi-View / Re-grasp' : 'GOOD Bowl'}
            </span>
          </div>
          <div className="flex items-center space-x-3">
            <span className="text-[#55dbb1]">GOOD &lt;{tLow.toFixed(2)}</span>
            <span className="text-[#e9bf79]">MULTI-VIEW {tLow.toFixed(2)}–{tHigh.toFixed(2)}</span>
            <span className="text-[#f28d95]">DEFECT &gt;{tHigh.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
