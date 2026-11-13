import React, { useState } from 'react';
import { Camera, CheckCircle, AlertTriangle, RotateCcw } from 'lucide-react';

export default function DualCameraFeed({ currentCycle }) {
  const [viewMode, setViewMode] = useState('overlay'); // 'overlay' | 'heatmap' | 'raw'

  const score = currentCycle?.anomaly_score ?? 0.104;
  const isDefective = currentCycle?.action === 'DEFECTIVE_BOWL';
  const isRegrasp = currentCycle?.action === 'REGRASP_TRIGGERED';
  const isPerfect = currentCycle?.action === 'PERFECT_BOWL' || (!isDefective && !isRegrasp);

  const scorePct = Math.min(Math.max((score / 1.0) * 100, 2), 100);

  // Status Badge in Header
  let statusBadge = (
    <div className="bg-[#15352e] border border-[#55dbb1]/30 px-3 py-1 rounded-[5px] flex items-center space-x-1.5">
      <CheckCircle className="w-3.5 h-3.5 text-[#55dbb1]" />
      <span className="text-[11px] font-medium text-[#55dbb1]">Perfect brick</span>
    </div>
  );

  if (isDefective) {
    statusBadge = (
      <div className="bg-[#38232c] border border-[#f28d95]/30 px-3 py-1 rounded-[5px] flex items-center space-x-1.5">
        <AlertTriangle className="w-3.5 h-3.5 text-[#f28d95]" />
        <span className="text-[11px] font-medium text-[#f28d95]">Defective · Reject</span>
      </div>
    );
  } else if (isRegrasp) {
    statusBadge = (
      <div className="bg-[#352e21] border border-[#e9bf79]/30 px-3 py-1 rounded-[5px] flex items-center space-x-1.5">
        <RotateCcw className="w-3.5 h-3.5 text-[#e9bf79] animate-spin" />
        <span className="text-[11px] font-medium text-[#e9bf79]">Uncertain · Re-grasp</span>
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

  return (
    <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-4 flex flex-col justify-between h-full">
      {/* Top Header */}
      <div>
        <div className="flex items-center justify-between pb-3 border-b border-[#26313e]">
          <h2 className="text-[16px] font-semibold text-[#edf2f7]">
            Live inspection
          </h2>
          <div>{statusBadge}</div>
        </div>

        {/* Subheaders & Mode Switcher */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2.5 items-center">
          {/* Overhead camera label */}
          <div className="flex items-center space-x-2">
            <div className="w-1.5 h-1.5 rounded-full bg-[#55dbb1] animate-pulse" />
            <div>
              <div className="text-[12px] font-medium text-[#b5c0ce] leading-tight font-mono">
                CAM-01 // Top-View Workspace (Duplo Plate &amp; GOOD/DEFECTIVE Bowls)
              </div>
              <div className="text-[10px] text-[#8e9bae] leading-tight mt-0.5">
                RealSense D415 · 1080p / 60 fps
              </div>
            </div>
          </div>

          {/* Inspection Camera label & Switcher */}
          <div className="flex items-center justify-between sm:justify-end space-x-3">
            <div className="flex items-center space-x-2">
              <div className="w-1.5 h-1.5 rounded-full bg-[#89b9ef]" />
              <div className="text-[12px] font-medium text-[#b5c0ce] font-mono">
                CAM-02 // Inspection Camera (Plain Backdrop ROI)
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
          {/* CAM 01: Overhead Simulation Feed */}
          <div className="relative aspect-[409/218] w-full rounded-[6px] overflow-hidden border border-[#26313e] bg-[#0c1520] flex items-center justify-center">
            {/* Badges */}
            <div className="absolute left-2.5 top-2.5 bg-[#121922]/90 border border-[#26313e]/60 px-2 py-0.5 rounded-[4px] z-10">
              <span className="text-[10px] font-mono font-medium text-[#b5c0ce]">CAM 01 // TOP-VIEW</span>
            </div>
            <div className="absolute left-2.5 bottom-2.5 bg-[#121922]/90 border border-[#26313e]/60 px-2 py-0.5 rounded-[4px] z-10">
              <span className="text-[10px] font-mono font-medium text-[#b5c0ce]">SO-ARM101 CELL</span>
            </div>

            {/* SVG Arena Simulation */}
            <svg className="w-full h-full p-2" viewBox="0 0 300 180" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Workspace Boundary */}
              <rect x="10" y="10" width="280" height="160" rx="8" stroke="#1e293b" strokeWidth="1" strokeDasharray="3 3" />
              
              {/* GOOD Bowl: Accept */}
              <circle cx="55" cy="50" r="28" fill="#15352e" stroke="#55dbb1" strokeWidth="1.2" />
              <text x="55" y="48" textAnchor="middle" fill="#55dbb1" fontSize="7.5" fontFamily="monospace" fontWeight="600">GOOD BOWL</text>
              <text x="55" y="58" textAnchor="middle" fill="#8e9bae" fontSize="6.5" fontFamily="monospace">Bowl #1</text>

              {/* DEFECTIVE Bowl: Defective */}
              <circle cx="245" cy="50" r="28" fill="#38232c" stroke="#f28d95" strokeWidth="1.2" />
              <text x="245" y="48" textAnchor="middle" fill="#f28d95" fontSize="7.5" fontFamily="monospace" fontWeight="600">DEFECTIVE BOWL</text>
              <text x="245" y="58" textAnchor="middle" fill="#8e9bae" fontSize="6.5" fontFamily="monospace">Bowl #2</text>

              {/* Central Source Duplo Plate */}
              <circle cx="150" cy="115" r="42" fill="#0b0f14" stroke="#89b9ef" strokeWidth="1.2" strokeDasharray="2 2" />
              <circle cx="150" cy="115" r="2.5" fill="#89b9ef" />
              <text x="150" y="85" textAnchor="middle" fill="#8e9bae" fontSize="6.5" fontFamily="monospace">SOURCE DUPLO PLATE</text>

              {/* Duplo Brick */}
              <rect x="138" y="103" width="24" height="24" rx="3" fill={
                brickColor === 'yellow' ? '#f59e0b' :
                brickColor === 'red' ? '#ef4444' :
                brickColor === 'blue' ? '#3b82f6' : '#55dbb1'
              } stroke="#ffffff" strokeWidth="1.2" />

              {/* Arm Trajectory line */}
              {isDefective ? (
                <path d="M 150 115 Q 195 70 245 50" stroke="#f28d95" strokeWidth="1.5" strokeDasharray="3 3" fill="none" />
              ) : (
                <path d="M 150 115 Q 105 70 55 50" stroke="#55dbb1" strokeWidth="1.5" strokeDasharray="3 3" fill="none" />
              )}
            </svg>
          </div>

          {/* CAM 02: Close-Up Inspection ROI */}
          <div className="relative aspect-[409/218] w-full rounded-[6px] overflow-hidden border border-[#26313e] bg-[#070c1c] flex items-center justify-center">
            {/* Badges */}
            <div className="absolute left-2.5 top-2.5 bg-[#121922]/90 border border-[#26313e]/60 px-2 py-0.5 rounded-[4px] z-10">
              <span className="text-[10px] font-mono font-medium text-[#b5c0ce]">CAM 02 // BACKDROP ROI</span>
            </div>
            
            <div className={`absolute right-2.5 bottom-2.5 px-2.5 py-0.5 rounded-[4px] z-10 border ${
              isDefective
                ? 'bg-[#38232c] text-[#f28d95] border-[#f28d95]/30'
                : 'bg-[#15352e] text-[#55dbb1] border-[#55dbb1]/30'
            }`}>
              <span className="text-[10px] font-medium">
                {isDefective ? 'Defect detected' : 'No defect detected'}
              </span>
            </div>

            {/* Display Image or Synthesized Duplo visual */}
            {activeImage ? (
              <img
                src={activeImage}
                alt="Wrist inspection crop"
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="relative w-full h-full flex items-center justify-center">
                {/* Fallback procedural Duplo rendering */}
                <div className={`w-32 h-32 rounded-lg flex items-center justify-center relative shadow-lg ${
                  brickColor === 'yellow' ? 'bg-amber-500' :
                  brickColor === 'red' ? 'bg-rose-600' :
                  brickColor === 'blue' ? 'bg-blue-600' : 'bg-emerald-600'
                }`}>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="w-7 h-7 rounded-full bg-white/20 border border-white/30" />
                    <div className="w-7 h-7 rounded-full bg-white/20 border border-white/30" />
                    <div className="w-7 h-7 rounded-full bg-white/20 border border-white/30" />
                    <div className="w-7 h-7 rounded-full bg-white/20 border border-white/30" />
                  </div>
                  {viewMode !== 'raw' && (
                    <div className={`absolute inset-0 rounded-lg pointer-events-none ${
                      isDefective
                        ? 'bg-gradient-to-tr from-transparent via-rose-500/50 to-amber-500/60 mix-blend-color-dodge'
                        : 'bg-emerald-400/20 mix-blend-overlay'
                    }`} />
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Telemetry & Status Bar */}
      <div className="pt-2 border-t border-[#26313e]/70 space-y-2">
        <div className="flex flex-wrap items-center justify-between text-[11px] gap-2">
          {/* Target */}
          <div className="flex items-center space-x-2">
            <span className="text-[#8e9bae]">Target</span>
            <div className={`w-1.5 h-1.5 rounded-full ${
              brickColor === 'yellow' ? 'bg-amber-400' :
              brickColor === 'red' ? 'bg-rose-400' :
              brickColor === 'blue' ? 'bg-blue-400' : 'bg-[#55dbb1]'
            }`} />
            <span className="font-medium text-[#b5c0ce]">{colorDisplay}</span>
          </div>

          {/* Anomaly Score Readout */}
          <div className="flex items-baseline space-x-2">
            <span className="text-[#8e9bae]">Anomaly score</span>
            <span className={`text-[19px] font-semibold tabular-nums leading-none ${
              isDefective ? 'text-[#f28d95]' : 'text-[#55dbb1]'
            }`}>
              {score.toFixed(3)}
            </span>
            <span className="text-[10px] text-[#8e9bae]">Reject threshold 0.55</span>
          </div>
        </div>

        {/* Anomaly Progress Track with Threshold Marker */}
        <div className="relative w-full h-[6px] bg-[#18212c] rounded-[3px] overflow-visible">
          <div
            className={`h-full rounded-[3px] transition-all duration-300 ${
              isDefective ? 'bg-[#f28d95]' : 'bg-[#55dbb1]'
            }`}
            style={{ width: `${Math.min(scorePct, 100)}%` }}
          />
          {/* 0.55 Threshold Marker */}
          <div
            className="absolute top-[-4px] bottom-[-4px] w-[2px] bg-[#e9bf79] rounded-[1px] shadow-sm z-10"
            style={{ left: '55%' }}
            title="Rejection Threshold (0.55)"
          />
        </div>

        {/* Footer Labels */}
        <div className="flex items-center justify-between text-[10px] text-[#8e9bae]">
          <div className="flex items-center space-x-2">
            <span>SO-101 leader / follower</span>
            <span>•</span>
            <span className={`font-medium ${isDefective ? 'text-[#f28d95]' : 'text-[#55dbb1]'}`}>
              {isDefective ? 'DEFECTIVE Bowl' : isRegrasp ? 'Source Duplo Plate (Re-inspect)' : 'GOOD Bowl'}
            </span>
          </div>
          <div className="flex items-center space-x-3">
            <span>Nominal &lt; 0.35</span>
            <span className="text-[#e9bf79]">Boundary 0.50</span>
          </div>
        </div>
      </div>
    </div>
  );
}
