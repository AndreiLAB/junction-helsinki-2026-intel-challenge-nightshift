import React, { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import PerformanceOverview from './components/PerformanceOverview';
import ClosedLoopPipeline from './components/ClosedLoopPipeline';
import DualCameraFeed from './components/DualCameraFeed';
import IntelTelemetry from './components/IntelTelemetry';
import GeminiCopilot from './components/GeminiCopilot';
import NemotronAuditFeed from './components/NemotronAuditFeed';
import CycleModal from './components/CycleModal';
import { Play, ChevronDown, ArrowRight, ToggleLeft, ToggleRight } from 'lucide-react';

export default function App() {
  const [activeStage, setActiveStage] = useState('IDLE');
  const [activeRules, setActiveRules] = useState([]);
  const [recentCycles, setRecentCycles] = useState([]);
  const [currentCycle, setCurrentCycle] = useState(null);
  const [hardwareMetrics, setHardwareMetrics] = useState(null);
  const [simulationRunning, setSimulationRunning] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedCycle, setSelectedCycle] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');

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
    <div className="min-h-screen bg-[#0b0f14] text-[#edf2f7] flex flex-col lg:flex-row w-full font-sans antialiased">
      {/* 1. Left Sidebar Navigation matching Figma */}
      <Sidebar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        wsConnected={wsConnected}
      />

      {/* 2. Main Inspection Workspace */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#0b0f14]">
        {/* Global Toolbar */}
        <header className="h-[72px] bg-[#0e131a] border-b border-[#26313e] px-6 flex items-center justify-between shrink-0">
          {/* Breadcrumbs */}
          <div className="flex items-center space-x-2 text-[12px]">
            <span className="text-[#8e9bae]">Workspace</span>
            <ArrowRight className="w-3.5 h-3.5 text-[#8e9bae]" />
            <span className="font-medium text-[#edf2f7] text-[13px]">Inspection cell</span>
            <div className="bg-[#18212c] px-2.5 py-0.5 rounded-[5px] ml-2 border border-[#26313e]">
              <span className="text-[11px] font-medium text-[#b5c0ce]">SO-ARM101</span>
            </div>
          </div>

          {/* Right Status & Operator Badge */}
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className="w-1.5 h-1.5 rounded-full bg-[#55dbb1] animate-pulse" />
              <span className="text-[12px] text-[#b5c0ce] font-normal hidden sm:inline">
                All systems operational
              </span>
            </div>

            <div className="h-4 w-px bg-[#26313e] hidden sm:block" />

            <div className="bg-[#18212c] border border-[#26313e] px-3 py-1.5 rounded-[5px] flex items-center space-x-2 cursor-pointer hover:border-[#55dbb1]/50 transition-colors">
              <span className="text-[11px] text-[#b5c0ce]">Operator</span>
              <ChevronDown className="w-3.5 h-3.5 text-[#8e9bae]" />
            </div>
          </div>
        </header>

        {/* Dashboard Content */}
        <main className="p-4 sm:p-6 space-y-4 max-w-[1400px] w-full mx-auto">
          {/* Page Heading & Main Action */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h1 className="text-[27px] font-semibold text-[#edf2f7] leading-tight">
                Mission control
              </h1>
              <p className="text-[13px] text-[#8e9bae] mt-1">
                Autonomous inspection, from perception to action.
              </p>
            </div>

            <div className="flex items-center space-x-3 self-end sm:self-auto shrink-0">
              {/* Dispatch Live Indicator */}
              <div className="bg-[#15352e] border border-[#55dbb1]/30 px-3 py-1 rounded-[5px] flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#55dbb1] animate-ping" />
                <span className="text-[11px] font-medium text-[#55dbb1]">Dispatch live</span>
              </div>

              {/* Simulate Cycle Primary Button */}
              <button
                onClick={() => handleTriggerCycle()}
                className="bg-[#55dbb1] hover:bg-[#55dbb1]/90 active:scale-95 text-[#0b0f14] px-4 py-2 rounded-[6px] text-[13px] font-semibold flex items-center space-x-2 transition-all shadow-md shadow-[#55dbb1]/20"
              >
                <Play className="w-4 h-4 fill-current" />
                <span>Simulate cycle</span>
              </button>
            </div>
          </div>

          {/* Performance Overview (4 Stat Cards) */}
          <PerformanceOverview cycles={recentCycles} />

          {/* Closed-Loop Autonomous Pipeline Bar */}
          <ClosedLoopPipeline activeStage={activeStage} />

          {/* Grid Row 1: Live Inspection & Edge Telemetry */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-7 xl:col-span-8">
              <DualCameraFeed currentCycle={currentCycle} />
            </div>
            <div className="lg:col-span-5 xl:col-span-4">
              <IntelTelemetry
                metrics={hardwareMetrics}
                simulationRunning={simulationRunning}
                onTriggerCycle={handleTriggerCycle}
                onToggleContinuousSimulation={handleToggleContinuousSimulation}
              />
            </div>
          </div>

          {/* Grid Row 2: Floor Copilot & Inspection History */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
            <div className="lg:col-span-5 xl:col-span-5">
              <GeminiCopilot
                activeRules={activeRules}
                onRuleCreated={handleRuleCreated}
                onRuleDeleted={handleRuleDeleted}
              />
            </div>
            <div className="lg:col-span-7 xl:col-span-7">
              <NemotronAuditFeed
                cycles={recentCycles}
                onSelectCycle={(cycle) => setSelectedCycle(cycle)}
              />
            </div>
          </div>

          {/* System Footer matching Figma */}
          <footer className="pt-2 pb-4 text-[10px] text-[#8e9bae] flex flex-wrap items-center justify-between gap-3 border-t border-[#26313e]/60">
            <div className="flex items-center space-x-3">
              <span className="font-medium text-[#b5c0ce]">OpenVINO 2026.0</span>
              <span>/</span>
              <span>Anomalib 2.7.0</span>
              <span>/</span>
              <span>SmolVLA · ACT</span>
              <span>/</span>
              <span>Intel Core Ultra Series 3</span>
            </div>

            <div className="flex items-center space-x-2">
              <span className="text-[#b5c0ce]">Auto-cycle stream</span>
              <button
                onClick={handleToggleContinuousSimulation}
                className="flex items-center space-x-1.5 focus:outline-none"
              >
                {simulationRunning ? (
                  <ToggleRight className="w-5 h-5 text-[#55dbb1]" />
                ) : (
                  <ToggleLeft className="w-5 h-5 text-[#8e9bae]" />
                )}
                <span className={`text-[10px] font-medium ${simulationRunning ? 'text-[#55dbb1]' : 'text-[#8e9bae]'}`}>
                  {simulationRunning ? 'On' : 'Off'}
                </span>
              </button>
            </div>
          </footer>
        </main>
      </div>

      {/* Inspection Modal */}
      {selectedCycle && (
        <CycleModal cycle={selectedCycle} onClose={() => setSelectedCycle(null)} />
      )}
    </div>
  );
}
