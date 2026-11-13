import React, { useState } from 'react';
import { Camera, Layers, Flame, Eye, AlertTriangle, CheckCircle, RotateCcw, Crosshair } from 'lucide-react';

export default function DualCameraFeed({ currentCycle }) {
  const [viewMode, setViewMode] = useState('composite'); // 'composite' | 'heatmap' | 'raw'

  const score = currentCycle?.anomaly_score ?? 0.12;
  const isDefective = currentCycle?.action === 'DEFECTIVE_BOWL';
  const isRegrasp = currentCycle?.action === 'REGRASP_TRIGGERED';
  const isPerfect = currentCycle?.action === 'PERFECT_BOWL';

  const scorePercentage = Math.min(Math.max(score * 100, 0), 100);

  // Status styling
  let statusBadge = (
    <span className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-glow-emerald">
      <CheckCircle className="w-3.5 h-3.5" />
      <span>PERFECT BRICK</span>
    </span>
  );

  if (isDefective) {
    statusBadge = (
      <span className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40 shadow-glow-rose">
        <AlertTriangle className="w-3.5 h-3.5" />
        <span>DEFECTIVE — REJECT</span>
      </span>
    );
  } else if (isRegrasp) {
    statusBadge = (
      <span className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-500/20 text-amber-400 border border-amber-500/40 shadow-glow-amber">
        <RotateCcw className="w-3.5 h-3.5 animate-spin" />
        <span>UNCERTAIN — RE-GRASP</span>
      </span>
    );
  }

  // Determine active image
  let activeImage = currentCycle?.composite_url;
  if (viewMode === 'heatmap') {
    activeImage = currentCycle?.heatmap_url || currentCycle?.composite_url;
  } else if (viewMode === 'raw') {
    activeImage = currentCycle?.raw_url;
  }

  return (
    <div className="bg-obsidian-900 border border-obsidian-border rounded-xl p-3.5 shadow-xl backdrop-blur-md flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between mb-2.5 border-b border-obsidian-border pb-2">
        <div className="flex items-center space-x-2">
          <Camera className="w-4 h-4 text-intel-light" />
          <h2 className="text-xs font-bold tracking-tight text-white uppercase font-mono">
            Dual-Camera & Anomalib Heatmap Feed
          </h2>
        </div>
        <div>{statusBadge}</div>
      </div>

      {/* Feeds Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* CAM-01: Top-View Workspace (Duplo Plates) */}
        <div className="flex flex-col">
          <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono mb-1">
            <span className="flex items-center space-x-1.5 truncate">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
              <span className="text-white font-medium truncate">CAM-01 Top-View Workspace (Duplo Plates)</span>
            </span>
            <span className="text-[10px] text-slate-500 tabular-nums shrink-0 ml-1">60 FPS</span>
          </div>

          {/* Arena Visual Simulation */}
          <div className="relative aspect-square w-full rounded-lg overflow-hidden border border-obsidian-border bg-obsidian-950 flex items-center justify-center scanline">
            <svg className="w-full h-full p-3" viewBox="0 0 300 300" fill="none" xmlns="http://www.w3.org/2000/svg">
              {/* Workspace Boundary */}
              <rect x="15" y="15" width="270" height="270" rx="10" stroke="#1e293b" strokeWidth="1.5" strokeDasharray="4 4" />
              
              {/* Bowl 1: Accept */}
              <circle cx="65" cy="70" r="36" fill="#10b981" fillOpacity="0.12" stroke="#10b981" strokeWidth="1.5" />
              <text x="65" y="68" textAnchor="middle" fill="#34d399" fontSize="8.5" fontFamily="monospace" fontWeight="bold">ACCEPT BOWL</text>
              <text x="65" y="80" textAnchor="middle" fill="#6ee7b7" fontSize="7" fontFamily="monospace">Bowl #1</text>

              {/* Bowl 2: Defective */}
              <circle cx="235" cy="70" r="36" fill="#ef4444" fillOpacity="0.12" stroke="#ef4444" strokeWidth="1.5" />
              <text x="235" y="68" textAnchor="middle" fill="#f87171" fontSize="8.5" fontFamily="monospace" fontWeight="bold">DEFECT BOWL</text>
              <text x="235" y="80" textAnchor="middle" fill="#fca5a5" fontSize="7" fontFamily="monospace">Bowl #2</text>

              {/* Central Inspection Turntable Plates */}
              <circle cx="150" cy="180" r="54" fill="#0f172a" stroke="#00C7FD" strokeWidth="1.5" strokeDasharray="3 3" />
              <circle cx="150" cy="180" r="3" fill="#00C7FD" />
              <text x="150" y="138" textAnchor="middle" fill="#94a3b8" fontSize="7.5" fontFamily="monospace">DUPLO TURNTABLE</text>

              {/* Duplo Brick in Inspection Zone */}
              <rect x="135" y="165" width="30" height="30" rx="3" fill={
                currentCycle?.color === 'red' ? '#ef4444' :
                currentCycle?.color === 'yellow' ? '#f59e0b' :
                currentCycle?.color === 'green' ? '#10b981' :
                currentCycle?.color === 'orange' ? '#f97316' : '#3b82f6'
              } stroke="#ffffff" strokeWidth="1.5" />
              
              {/* Arm Base Position (LeRobot SO-ARM101) */}
              <rect x="135" y="275" width="30" height="15" rx="3" fill="#334155" />
              <line x1="150" y1="275" x2="150" y2="200" stroke="#0071C5" strokeWidth="3" strokeLinecap="round" />
              <circle cx="150" cy="200" r="5" fill="#00C7FD" />

              {/* Trajectory Guide */}
              {isDefective ? (
                <path d="M 150 180 Q 200 120 235 70" fill="none" stroke="#ef4444" strokeWidth="2" strokeDasharray="3 3" />
              ) : isPerfect ? (
                <path d="M 150 180 Q 100 120 65 70" fill="none" stroke="#10b981" strokeWidth="2" strokeDasharray="3 3" />
              ) : (
                <circle cx="150" cy="180" r="60" fill="none" stroke="#f59e0b" strokeWidth="1.5" strokeDasharray="4 2" />
              )}
            </svg>

            {/* Crosshair */}
            <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
              <Crosshair className="w-10 h-10 text-intel-light/25" />
            </div>

            <div className="absolute bottom-2 left-2 bg-obsidian-900/90 px-2 py-0.5 rounded text-[9px] font-mono text-slate-300 border border-obsidian-border">
              Target: <span className="text-white font-bold">{currentCycle?.color?.toUpperCase() || 'BLUE'}</span>
            </div>
            <div className="absolute top-2 right-2 bg-obsidian-900/90 px-2 py-0.5 rounded text-[9px] font-mono text-intel-light border border-obsidian-border font-semibold">
              LeRobot SO-ARM101
            </div>
          </div>
        </div>

        {/* CAM-02: Close-Up Inspection (Anomalib v2.7.0) */}
        <div className="flex flex-col">
          <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono mb-1">
            <span className="flex items-center space-x-1.5 truncate">
              <span className="w-2 h-2 rounded-full bg-intel-light animate-pulse shrink-0" />
              <span className="text-white font-medium truncate">CAM-02 Close-Up Inspection (Anomalib v2.7.0)</span>
            </span>
            {/* View switcher tabs */}
            <div className="flex items-center space-x-1 bg-obsidian-950 p-0.5 rounded border border-obsidian-border shrink-0">
              <button
                onClick={() => setViewMode('composite')}
                className={`px-1.5 py-0.2 text-[9px] rounded font-mono font-medium transition-colors ${
                  viewMode === 'composite'
                    ? 'bg-intel-blue text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Overlay
              </button>
              <button
                onClick={() => setViewMode('heatmap')}
                className={`px-1.5 py-0.2 text-[9px] rounded font-mono font-medium transition-colors ${
                  viewMode === 'heatmap'
                    ? 'bg-rose-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Heatmap
              </button>
              <button
                onClick={() => setViewMode('raw')}
                className={`px-1.5 py-0.2 text-[9px] rounded font-mono font-medium transition-colors ${
                  viewMode === 'raw'
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Raw
              </button>
            </div>
          </div>

          {/* High-res Image Display */}
          <div className="relative aspect-square w-full rounded-lg overflow-hidden border border-obsidian-border bg-obsidian-950 flex items-center justify-center group">
            {activeImage ? (
              <img
                src={activeImage}
                alt="Inspection Crop"
                className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
              />
            ) : (
              <div className="flex flex-col items-center justify-center text-slate-500 font-mono text-xs">
                <Layers className="w-6 h-6 mb-1 text-slate-600 animate-pulse" />
                <span>Synchronizing feed...</span>
              </div>
            )}

            {/* Overlaid Tag */}
            <div className="absolute top-2 left-2 bg-obsidian-950/85 backdrop-blur-md px-1.5 py-0.5 rounded text-[9px] font-mono text-slate-300 border border-obsidian-border">
              {viewMode === 'composite' ? 'Cloudinary Layer Composite' : viewMode === 'heatmap' ? 'Anomalib PatchCore Activation' : 'Optical RGB Crop'}
            </div>

            <div className="absolute bottom-2 right-2 bg-obsidian-950/85 backdrop-blur-md px-1.5 py-0.5 rounded text-[9px] font-mono text-intel-light border border-obsidian-border">
              Defect: <span className="text-white font-bold">{currentCycle?.defect_label || 'Pristine'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Anomaly Gauge with non-wrapping tabular scores */}
      <div className="mt-3 pt-2.5 border-t border-obsidian-border">
        <div className="flex items-center justify-between text-xs font-mono mb-1">
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400">Anomalib Score:</span>
            <span className={`text-sm font-bold tabular-nums whitespace-nowrap ${
              isDefective ? 'text-rose-400' : isRegrasp ? 'text-amber-400' : 'text-emerald-400'
            }`}>
              {score.toFixed(3)}
            </span>
          </div>
          <div className="flex items-center space-x-2 text-[10px] text-slate-500 tabular-nums">
            <span>Nominal: &lt;0.35</span>
            <span className="text-amber-400 font-bold">Boundary: 0.50</span>
            <span>Reject: &gt;0.55</span>
          </div>
        </div>

        {/* Visual Progress Bar with Threshold Marker */}
        <div className="relative w-full h-2.5 bg-obsidian-950 rounded-full overflow-hidden border border-obsidian-border p-0.5">
          {/* Threshold Mark */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-amber-400 z-10 shadow-[0_0_6px_#f59e0b]"
            style={{ left: '55%' }}
            title="Threshold (0.55)"
          />

          {/* Active fill */}
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              isDefective
                ? 'bg-gradient-to-r from-amber-500 to-rose-600 shadow-glow-rose'
                : isRegrasp
                ? 'bg-gradient-to-r from-emerald-500 to-amber-500 shadow-glow-amber'
                : 'bg-gradient-to-r from-teal-500 to-emerald-500 shadow-glow-emerald'
            }`}
            style={{ width: `${scorePercentage}%` }}
          />
        </div>
      </div>
    </div>
  );
}
