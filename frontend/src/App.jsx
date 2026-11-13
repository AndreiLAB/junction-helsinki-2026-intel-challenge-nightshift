import React, { useState, useEffect, useRef } from 'react';
import ClosedLoopPipeline from './components/ClosedLoopPipeline';
import DualCameraFeed from './components/DualCameraFeed';
import IntelTelemetry from './components/IntelTelemetry';
import GeminiCopilot from './components/GeminiCopilot';
import NemotronAuditFeed from './components/NemotronAuditFeed';
import CycleModal from './components/CycleModal';
import { Play } from 'lucide-react';

export default function App() {
  const [activeStage, setActiveStage] = useState('IDLE');
  const [activeRules, setActiveRules] = useState([]);
  const [recentCycles, setRecentCycles] = useState([]);
  const [currentCycle, setCurrentCycle] = useState(null);
  const [hardwareMetrics, setHardwareMetrics] = useState(null);
  const [simulationRunning, setSimulationRunning] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedCycle, setSelectedCycle] = useState(null);

  const wsRef = useRef(null);

  // Initial state fetch from REST API
  useEffect(() => {
    const fetchInitialState = async () => {
      try {
        const res = await fetch('/api/state');
        if (res.ok) {
          const data = await res.json();
          if (data.active_rules) setActiveRules(data.active_rules);
          if (data.recent_cycles) {
            setRecentCycles(data.recent_cycles);
            if (data.recent_cycles.length > 0) {
              setCurrentCycle(data.recent_cycles[0]);
            }
          }
          if (data.hardware_metrics) setHardwareMetrics(data.hardware_metrics);
          if (data.stage) setActiveStage(data.stage);
          if (data.simulation_running !== undefined) setSimulationRunning(data.simulation_running);
        }
      } catch (err) {
        console.warn("Could not fetch /api/state:", err);
      }
    };
    fetchInitialState();
  }, []);

  // WebSocket Connection
  useEffect(() => {
    let reconnectTimeout = null;

    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/live`;
      
      console.log(`[WS] Connecting to ${wsUrl}...`);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("[WS] Connected to Physical AI Hub.");
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'STAGE_CHANGE') {
            setActiveStage(msg.stage);
          } else if (msg.type === 'NEW_CYCLE') {
            setCurrentCycle(msg.cycle);
            setRecentCycles(prev => [msg.cycle, ...prev.slice(0, 39)]);
            if (msg.hardware_metrics) setHardwareMetrics(msg.hardware_metrics);
          } else if (msg.type === 'INITIAL_STATE') {
            if (msg.active_rules) setActiveRules(msg.active_rules);
            if (msg.recent_cycles) {
              setRecentCycles(msg.recent_cycles);
              if (msg.recent_cycles.length > 0) setCurrentCycle(msg.recent_cycles[0]);
            }
            if (msg.hardware_metrics) setHardwareMetrics(msg.hardware_metrics);
            if (msg.stage) setActiveStage(msg.stage);
            if (msg.simulation_running !== undefined) setSimulationRunning(msg.simulation_running);
          } else if (msg.type === 'RULE_CREATED') {
            if (msg.active_rules) setActiveRules(msg.active_rules);
          } else if (msg.type === 'RULE_DELETED') {
            if (msg.active_rules) setActiveRules(msg.active_rules);
          } else if (msg.type === 'SIMULATION_STATUS') {
            setSimulationRunning(msg.simulation_running);
          }
        } catch (err) {
          console.error("[WS] Error parsing message:", err);
        }
      };

      ws.onclose = () => {
        console.warn("[WS] Disconnected. Reconnecting in 3 seconds...");
        setWsConnected(false);
        reconnectTimeout = setTimeout(connectWebSocket, 3000);
      };

      ws.onerror = (err) => {
        console.error("[WS] Error:", err);
        ws.close();
      };
    };

    connectWebSocket();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // API Callbacks
  const handleTriggerCycle = async (outcome) => {
    try {
      const url = outcome ? `/api/simulate-cycle?outcome=${outcome}` : '/api/simulate-cycle';
      const res = await fetch(url, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.cycle) {
          setCurrentCycle(data.cycle);
          setRecentCycles(prev => [data.cycle, ...prev.slice(0, 39)]);
        }
      }
    } catch (err) {
      console.error("Failed to trigger cycle:", err);
    }
  };

  const handleToggleContinuousSimulation = async () => {
    try {
      const res = await fetch('/api/toggle-simulation', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSimulationRunning(data.simulation_running);
      }
    } catch (err) {
      console.error("Failed to toggle simulation:", err);
    }
  };

  const handleRuleCreated = (newRule) => {
    setActiveRules(prev => [newRule, ...prev.filter(r => r.rule_id !== newRule.rule_id)]);
  };

  const handleRuleDeleted = async (ruleId) => {
    try {
      const res = await fetch(`/api/copilot/rule/${ruleId}`, { method: 'DELETE' });
      if (res.ok) {
        setActiveRules(prev => prev.filter(r => r.rule_id !== ruleId));
      }
    } catch (err) {
      console.error("Failed to delete rule:", err);
    }
  };

  return (
    <div className="min-h-screen bg-obsidian-950 text-slate-100 flex flex-col p-3 sm:p-4 lg:p-5 space-y-3 max-w-[1600px] mx-auto">
      {/* Top Header Bar */}
      <header className="flex flex-col sm:flex-row sm:items-center justify-between bg-obsidian-900 border border-obsidian-border rounded-xl px-4 py-2.5 shadow-xl backdrop-blur-md gap-2.5">
        {/* Left: Intel Robotics Branding */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-intel-blue flex items-center justify-center font-bold text-white text-base tracking-wider shadow-md shadow-glow-intel shrink-0">
            intel
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-sm font-extrabold tracking-tight text-white font-mono uppercase">
                PHYSICAL AI STUDIO • AUTONOMOUS INSPECTION CELL
              </h1>
              <span className="text-[9px] font-mono px-2 py-0.2 rounded-full bg-intel-blue/20 text-intel-light border border-intel-blue/40 font-semibold">
                Junction 2026
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-mono flex flex-wrap items-center gap-x-2">
              <span>Member 4: Gemini Multimodal Copilot & Cloudinary Media Hub</span>
              <span className="text-slate-600 hidden md:inline">•</span>
              <span className="text-emerald-400 font-medium">LeRobot SO-ARM101 • CAM-01 Top-View & CAM-02 Inspection</span>
            </div>
          </div>
        </div>

        {/* Right: Dispatch status badge & Pitch controls */}
        <div className="flex items-center space-x-2.5 shrink-0 self-end sm:self-auto">
          <div className="flex items-center space-x-2 bg-obsidian-950 px-2.5 py-1 rounded-lg border border-obsidian-border">
            {wsConnected ? (
              <>
                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                <span className="text-[11px] font-mono text-emerald-400 font-semibold">DISPATCH LIVE</span>
              </>
            ) : (
              <>
                <div className="w-2 h-2 rounded-full bg-amber-400" />
                <span className="text-[11px] font-mono text-amber-400 font-semibold">CONNECTING...</span>
              </>
            )}
          </div>

          <button
            onClick={() => handleTriggerCycle()}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-intel-blue hover:bg-intel-light hover:text-slate-950 text-white transition-all shadow-md active:scale-95 shadow-glow-intel"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Simulate Cycle</span>
          </button>
        </div>
      </header>

      {/* 1. Closed-Loop Pipeline Bar */}
      <ClosedLoopPipeline activeStage={activeStage} />

      {/* Main Grid Row 1: Dual-Camera Feed & Intel Telemetry */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <DualCameraFeed currentCycle={currentCycle} />
        <IntelTelemetry
          metrics={hardwareMetrics}
          simulationRunning={simulationRunning}
          onTriggerCycle={handleTriggerCycle}
          onToggleContinuousSimulation={handleToggleContinuousSimulation}
        />
      </div>

      {/* Main Grid Row 2: Gemini Copilot & Nemotron Audit Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <GeminiCopilot
          activeRules={activeRules}
          onRuleCreated={handleRuleCreated}
          onRuleDeleted={handleRuleDeleted}
        />
        <NemotronAuditFeed
          cycles={recentCycles}
          onSelectCycle={(cycle) => setSelectedCycle(cycle)}
        />
      </div>

      {/* Footer Hardware Spec Bar */}
      <footer className="bg-obsidian-900 border border-obsidian-border rounded-xl px-4 py-2 text-[10.5px] font-mono text-slate-500 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <span className="text-intel-light font-semibold">Stack:</span>
          <span>OpenVINO™ 2026.0 Physical AI</span>
          <span>•</span>
          <span>Anomalib v2.7.0 (50 TOPS NPU)</span>
          <span>•</span>
          <span>SmolVLA / ACT (12 Xe3 Cores)</span>
          <span>•</span>
          <span>Gemini 3.8 Flash (Multimodal)</span>
          <span>•</span>
          <span>Cloudinary Media Pipeline</span>
        </div>
        <div className="text-slate-400">
          Intel® Core™ Ultra X9 388H (50-TOPS NPU • 12 Xe3 iGPU • CPU) • Heterogeneous Acceleration Active
        </div>
      </footer>

      {/* Inspection Modal */}
      {selectedCycle && (
        <CycleModal cycle={selectedCycle} onClose={() => setSelectedCycle(null)} />
      )}
    </div>
  );
}
