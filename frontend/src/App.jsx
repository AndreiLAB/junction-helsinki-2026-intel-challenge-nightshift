import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, Cloud, Cpu, Sparkles, History, LayoutGrid, ChevronDown, Radio } from 'lucide-react';
import PerformanceOverview from './components/PerformanceOverview';
import ClosedLoopPipeline from './components/ClosedLoopPipeline';
import DualCameraFeed from './components/DualCameraFeed';
import IntelTelemetry from './components/IntelTelemetry';
import GeminiCopilot from './components/GeminiCopilot';
import NemotronAuditFeed from './components/NemotronAuditFeed';
import CycleModal from './components/CycleModal';
import {
  PREVIEW_CLOUD_PROVIDERS,
  PREVIEW_RULES,
  PREVIEW_POLICY_HISTORY,
  PREVIEW_BENCHMARKS,
  PREVIEW_CYCLES,
  PREVIEW_HARDWARE_METRICS,
} from './data/previewSeed';

const CLOUD_STACK_LAYERS = [
  { key: 'gemini', label: 'Gemini 3.8 Flash' },
  { key: 'cloudinary', label: 'Cloudinary Overlay' },
  { key: 'nemotron', label: 'Nemotron B300' },
  { key: 'mariadb', label: 'MariaDB 11.8 Vector' },
  { key: 'modal', label: 'Modal Serverless' },
];

const NAV_TABS = [
  { id: 'cockpit', label: 'Cell Cockpit', icon: LayoutGrid },
  { id: 'bench', label: 'OpenVINO Bench', icon: Cpu },
  { id: 'copilot', label: 'Copilot & Rules', icon: Sparkles },
  { id: 'history', label: 'Archive', icon: History },
];

const API_BASE =
  import.meta.env.VITE_API_URL ||
  (window.location.port === '5173'
    ? 'http://localhost:8000'
    : window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : '');

const WS_URL =
  import.meta.env.VITE_WS_URL ||
  (window.location.protocol === 'https:'
    ? `wss://${window.location.hostname || 'localhost'}:8000/ws/live`
    : `ws://${window.location.hostname || 'localhost'}:8000/ws/live`);

export default function App() {
  const [activeTab, setActiveTab] = useState('cockpit');
  const [activeStage, setActiveStage] = useState('OPTIMIZE');
  const [cellState, setCellState] = useState('CONFIRM');
  const [policyBounds, setPolicyBounds] = useState({ t_low: 0.45, t_high: 0.60, anomaly_threshold: 0.55 });
  const [activeRules, setActiveRules] = useState(PREVIEW_RULES);
  const [recentCycles, setRecentCycles] = useState(PREVIEW_CYCLES);
  const [benchmarks, setBenchmarks] = useState(PREVIEW_BENCHMARKS);
  const [currentCycle, setCurrentCycle] = useState(PREVIEW_CYCLES[0]);
  const [hardwareMetrics, setHardwareMetrics] = useState(PREVIEW_HARDWARE_METRICS);
  const [simulationRunning, setSimulationRunning] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedCycle, setSelectedCycle] = useState(null);
  const [cloudProviders, setCloudProviders] = useState(PREVIEW_CLOUD_PROVIDERS);
  const [policyHistory, setPolicyHistory] = useState(PREVIEW_POLICY_HISTORY);
  const [policyHistoryMeta, setPolicyHistoryMeta] = useState({ provider: 'FALLBACK', activeThreshold: 0.54 });
  const [cloudMenuOpen, setCloudMenuOpen] = useState(false);
  const [simMenuOpen, setSimMenuOpen] = useState(false);

  const wsRef = useRef(null);

  const fetchBenchmarks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/benchmarks?limit=30`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.benchmarks) && data.benchmarks.length > 0) {
          setBenchmarks(data.benchmarks);
        }
      }
    } catch {
      // Standalone Figma Make preview keeps PREVIEW_BENCHMARKS
    }
  }, []);

  const fetchPolicyHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/policies/history?limit=30`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.history) && data.history.length > 0) setPolicyHistory(data.history);
        setPolicyHistoryMeta({
          provider: data.provider || 'FALLBACK',
          activeThreshold: data.active_anomaly_threshold ?? 0.55,
        });
        if (data.t_low !== undefined || data.t_high !== undefined) {
          setPolicyBounds((prev) => ({
            t_low: data.t_low ?? prev.t_low,
            t_high: data.t_high ?? prev.t_high,
            anomaly_threshold: data.active_anomaly_threshold ?? prev.anomaly_threshold,
          }));
        }
      }
    } catch {
      // Standalone preview fallback
    }
  }, []);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (res.ok) {
        const data = await res.json();
        if (data.cloud_providers) setCloudProviders(data.cloud_providers);
      }
    } catch {
      // Standalone preview fallback
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    fetchPolicyHistory();
    fetchBenchmarks();
    const id = setInterval(fetchHealth, 12000);
    return () => clearInterval(id);
  }, [fetchHealth, fetchPolicyHistory, fetchBenchmarks]);

  useEffect(() => {
    fetch(`${API_BASE}/api/state`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        if (Array.isArray(data.active_rules) && data.active_rules.length > 0) setActiveRules(data.active_rules);
        if (Array.isArray(data.recent_cycles) && data.recent_cycles.length > 0) {
          setRecentCycles(data.recent_cycles);
          setCurrentCycle(data.recent_cycles[0]);
        }
        if (Array.isArray(data.benchmarks) && data.benchmarks.length > 0) setBenchmarks(data.benchmarks);
        if (data.hardware_metrics) setHardwareMetrics(data.hardware_metrics);
        if (data.stage) setActiveStage(data.stage);
        if (data.cell_state) setCellState(data.cell_state);
        if (data.t_low !== undefined || data.t_high !== undefined) {
          setPolicyBounds((prev) => ({
            t_low: data.t_low ?? prev.t_low,
            t_high: data.t_high ?? prev.t_high,
            anomaly_threshold: data.active_anomaly_threshold ?? prev.anomaly_threshold,
          }));
        }
        if (data.simulation_running !== undefined) setSimulationRunning(data.simulation_running);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    let reconnectTimeout = null;
    const connectWebSocket = () => {
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;
        ws.onopen = () => setWsConnected(true);
        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'STAGE_CHANGE') {
              if (msg.stage) setActiveStage(msg.stage);
              if (msg.cell_state) setCellState(msg.cell_state);
            } else if (msg.type === 'NEW_CYCLE') {
              setCurrentCycle(msg.cycle);
              setRecentCycles((prev) => [msg.cycle, ...prev.filter((c) => c.cycle_id !== msg.cycle.cycle_id)].slice(0, 40));
              if (msg.hardware_metrics) setHardwareMetrics(msg.hardware_metrics);
              if (msg.cell_state || msg.cycle?.cell_state) setCellState(msg.cell_state || msg.cycle.cell_state);
              fetchHealth();
            } else if (msg.type === 'CYCLE_UPDATED') {
              setRecentCycles((prev) => prev.map((c) => (c.cycle_id === msg.cycle.cycle_id ? msg.cycle : c)));
              setCurrentCycle((prev) => (prev?.cycle_id === msg.cycle.cycle_id ? msg.cycle : prev));
              setSelectedCycle((prev) => (prev?.cycle_id === msg.cycle.cycle_id ? msg.cycle : prev));
              fetchHealth();
              fetchPolicyHistory();
            } else if (msg.type === 'BENCHMARKS_UPDATED') {
              if (Array.isArray(msg.benchmarks)) setBenchmarks(msg.benchmarks);
              if (msg.hardware_metrics) setHardwareMetrics(msg.hardware_metrics);
            } else if (msg.type === 'INITIAL_STATE') {
              if (Array.isArray(msg.active_rules) && msg.active_rules.length > 0) setActiveRules(msg.active_rules);
              if (Array.isArray(msg.recent_cycles) && msg.recent_cycles.length > 0) {
                setRecentCycles(msg.recent_cycles);
                setCurrentCycle(msg.recent_cycles[0]);
              }
              if (Array.isArray(msg.benchmarks) && msg.benchmarks.length > 0) setBenchmarks(msg.benchmarks);
              if (msg.hardware_metrics) setHardwareMetrics(msg.hardware_metrics);
              if (msg.stage) setActiveStage(msg.stage);
              if (msg.cell_state) setCellState(msg.cell_state);
            } else if (msg.type === 'RULE_CREATED' || msg.type === 'RULE_DELETED') {
              if (msg.active_rules) setActiveRules(msg.active_rules);
              fetchPolicyHistory();
            } else if (msg.type === 'SIMULATION_STATUS') {
              setSimulationRunning(msg.simulation_running);
            }
          } catch {
            // ignore parse failure
          }
        };
        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimeout = setTimeout(connectWebSocket, 4000);
        };
        ws.onerror = () => ws.close();
      } catch {
        setWsConnected(false);
      }
    };
    connectWebSocket();
    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, [fetchHealth, fetchPolicyHistory]);

  const handleTriggerCycle = async (outcome) => {
    setSimMenuOpen(false);
    try {
      const url = outcome ? `${API_BASE}/api/simulate-cycle?outcome=${outcome}` : `${API_BASE}/api/simulate-cycle`;
      const res = await fetch(url, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (data.cycle) {
          setCurrentCycle(data.cycle);
          setRecentCycles((prev) => [data.cycle, ...prev.filter((c) => c.cycle_id !== data.cycle.cycle_id)].slice(0, 40));
          return;
        }
      }
      throw new Error('offline');
    } catch {
      // Interactive offline / Figma Make animation showcase
      const chosen =
        outcome || ['PERFECT_BOWL', 'DEFECTIVE_BOWL', 'REGRASP_TRIGGERED'][Math.floor(Math.random() * 3)];
      const verdict = chosen === 'DEFECTIVE_BOWL' ? 'DEFECT' : chosen === 'REGRASP_TRIGGERED' ? 'UNCERTAIN' : 'GOOD';
      const score =
        verdict === 'DEFECT'
          ? [0.76, 0.81, 0.85][Math.floor(Math.random() * 3)]
          : verdict === 'UNCERTAIN'
          ? +(0.47 + Math.random() * 0.11).toFixed(2)
          : [0.05, 0.12, 0.32, 0.33][Math.floor(Math.random() * 4)];
      const color = verdict === 'DEFECT' ? 'pink' : verdict === 'UNCERTAIN' ? 'blue' : ['green', 'yellow'][Math.floor(Math.random() * 2)];
      const nextBrickIdx = (recentCycles[0]?.brick_idx || 4) + 1;

      setActiveStage('DETECT');
      setCellState('INSPECT');
      setTimeout(() => {
        setActiveStage('ACT');
        setCellState(verdict === 'DEFECT' ? 'PLACE_DEFECT' : verdict === 'UNCERTAIN' ? 'REGRASP' : 'PLACE_GOOD');
      }, 450);
      setTimeout(() => {
        setActiveStage('OPTIMIZE');
        setCellState('CONFIRM');
      }, 950);

      const newCycle = {
        cycle_id: `CYC-demo_${nextBrickIdx}`,
        run_id: 'figma-preview',
        brick_idx: nextBrickIdx,
        timestamp: new Date().toTimeString().slice(0, 8),
        color,
        defect_label:
          verdict === 'DEFECT'
            ? 'White Tape + Blue X Defect Marker'
            : verdict === 'UNCERTAIN'
            ? 'Uncertain Band [0.45, 0.60] — Put-Back Re-Grasp'
            : 'None (Pristine)',
        verdict,
        score,
        anomaly_score: score,
        t_low: policyBounds.t_low,
        t_high: policyBounds.t_high,
        views:
          verdict === 'UNCERTAIN'
            ? [{ view: 'inspect', score: +(score - 0.03).toFixed(2) }, { view: 'inspect_regrasp', score }]
            : [{ view: 'inspect', score }],
        action: chosen,
        instruction:
          verdict === 'DEFECT'
            ? 'Put the brick in the defective bowl.'
            : verdict === 'UNCERTAIN'
            ? 'Pick up a brick and hold it in front of the inspection camera.'
            : 'Put the brick in the good bowl.',
        cell_state: verdict === 'UNCERTAIN' ? 'REGRASP' : 'CONFIRM',
        model: 'patchcore_v1',
        precision: 'FP16',
        device: 'NPU',
        latency_ms: 181.0,
        cycle_s: +(29.8 + Math.random() * 4.0).toFixed(1),
        evidence: 'REAL',
        nemotron_provider: 'verda_b300',
        nemotron_reasoning:
          verdict === 'DEFECT'
            ? 'Inspect camera + PatchCore v1 (AUROC 0.949, F1 0.929) localized white tape + blue X defect; SmolVLA v1 placed brick in Pink DEFECT bowl.'
            : verdict === 'UNCERTAIN'
            ? 'Score sits inside [0.45, 0.60] deadband; put-back into Blue Source Bowl and re-pick via ACT v2 (12ms GPU).'
            : 'Clean stud topology verified on NPU below t_low 0.45; SmolVLA v1 placed brick in Green GOOD bowl.',
      };
      setCurrentCycle(newCycle);
      setRecentCycles((prev) => [newCycle, ...prev].slice(0, 40));
    }
  };

  const handleToggleAuto = async () => {
    setSimulationRunning((prev) => !prev);
    try {
      const res = await fetch(`${API_BASE}/api/toggle-simulation`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setSimulationRunning(data.simulation_running);
      }
    } catch {
      // keep toggled in preview
    }
  };

  const handleRuleCreated = (rule) => {
    setActiveRules((prev) => [rule, ...prev.filter((r) => r.rule_id !== rule.rule_id)]);
    fetchPolicyHistory();
  };

  const handleRuleDeleted = async (ruleId) => {
    setActiveRules((prev) => prev.filter((r) => r.rule_id !== ruleId));
    try {
      await fetch(`${API_BASE}/api/copilot/rule/${ruleId}`, { method: 'DELETE' });
      fetchPolicyHistory();
    } catch {
      // local remove in preview
    }
  };

  const liveCloudCount = CLOUD_STACK_LAYERS.filter((l) => cloudProviders?.[l.key]?.mode === 'LIVE').length;

  return (
    <div className="min-h-screen flex flex-col text-[#edf2f7]">
      {/* Frosted Top Navigation Command Bar */}
      <header className="sticky top-0 z-40 h-14 bg-[#070a0f]/80 backdrop-blur-xl border-b border-white/[0.06] px-4 sm:px-6 flex items-center justify-between gap-4">
        {/* Left: Brand + Cloud Stack Popover */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-[#55dbb1] text-[#070a0f] flex items-center justify-center shadow-[0_0_20px_rgba(85,219,177,0.35)] shrink-0">
            <LayoutGrid className="w-4 h-4" />
          </div>
          <div className="hidden sm:block leading-tight">
            <div className="text-[13px] font-semibold tracking-tight text-[#edf2f7]">
              SO-101 Physical AI
            </div>
            <div className="text-[10px] font-mono text-[#8e9bae]">
              {wsConnected ? 'Edge Cell Live · Junction 2026' : 'Interactive Studio Preview'}
            </div>
          </div>

          {/* Interactive Cloud 5/5 Pill */}
          <div className="relative">
            <button
              onClick={() => setCloudMenuOpen((v) => !v)}
              className="px-2.5 py-1 rounded-full glass-subtle hover:border-[#55dbb1]/40 flex items-center gap-1.5 text-[11px] font-mono transition-colors"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#55dbb1] animate-pulse" />
              <Cloud className="w-3 h-3 text-[#55dbb1]" />
              <span className="text-[#edf2f7]">{liveCloudCount}/5 LIVE</span>
              <ChevronDown className="w-3 h-3 text-[#8e9bae]" />
            </button>

            <AnimatePresence>
              {cloudMenuOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 6, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 4, scale: 0.96 }}
                  transition={{ duration: 0.16 }}
                  className="absolute left-0 mt-2 w-64 glass-panel rounded-xl p-2.5 space-y-1.5 z-50"
                >
                  <div className="text-[10px] font-mono uppercase tracking-wider text-[#8e9bae] px-1.5 pb-1">
                    Unified Cloud &amp; Data Stack
                  </div>
                  {CLOUD_STACK_LAYERS.map((layer) => {
                    const p = cloudProviders?.[layer.key];
                    const ok = p?.mode === 'LIVE';
                    return (
                      <div
                        key={layer.key}
                        className="flex items-center justify-between px-2 py-1.5 rounded-lg bg-white/[0.025] text-[11px]"
                      >
                        <span className="text-[#edf2f7]">{layer.label}</span>
                        <span className={`font-mono text-[10px] font-semibold ${ok ? 'text-[#55dbb1]' : 'text-[#e9bf79]'}`}>
                          {ok ? 'LIVE' : 'STANDBY'}
                        </span>
                      </div>
                    );
                  })}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Center: Animated Segmented Nav Pill */}
        <nav className="hidden md:flex items-center bg-white/[0.03] border border-white/[0.06] p-1 rounded-xl">
          {NAV_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`relative px-3.5 py-1.5 rounded-lg text-[12px] font-medium flex items-center gap-1.5 transition-colors ${
                  isActive ? 'text-[#070a0f] font-semibold' : 'text-[#8e9bae] hover:text-[#edf2f7]'
                }`}
              >
                {isActive && (
                  <motion.span
                    layoutId="topNavPill"
                    transition={{ type: 'spring', stiffness: 360, damping: 28 }}
                    className="absolute inset-0 bg-[#55dbb1] rounded-lg shadow-[0_0_20px_rgba(85,219,177,0.3)]"
                  />
                )}
                <Icon className="relative z-10 w-3.5 h-3.5" />
                <span className="relative z-10">{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Right: Primary Simulate Action + Auto */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={handleToggleAuto}
            className={`px-2.5 py-1.5 rounded-lg border text-[11px] font-mono flex items-center gap-1.5 transition-colors ${
              simulationRunning
                ? 'bg-[#15352e]/70 border-[#55dbb1]/40 text-[#55dbb1]'
                : 'glass-subtle text-[#8e9bae] hover:text-[#edf2f7]'
            }`}
          >
            <Radio className={`w-3.5 h-3.5 ${simulationRunning ? 'animate-pulse' : ''}`} />
            <span className="hidden sm:inline">Auto</span>
          </button>

          <div className="relative flex items-center">
            <button
              onClick={() => handleTriggerCycle()}
              className="bg-[#55dbb1] hover:bg-[#55dbb1]/90 active:scale-95 text-[#070a0f] pl-3 pr-2.5 py-1.5 rounded-l-lg text-[12px] font-semibold flex items-center gap-1.5 transition-all shadow-[0_0_20px_rgba(85,219,177,0.28)]"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Simulate</span>
            </button>
            <button
              onClick={() => setSimMenuOpen((v) => !v)}
              className="bg-[#45c49d] hover:bg-[#3cb38e] text-[#070a0f] px-1.5 py-1.5 rounded-r-lg border-l border-[#070a0f]/15 transition-colors"
            >
              <ChevronDown className="w-3.5 h-3.5" />
            </button>

            <AnimatePresence>
              {simMenuOpen && (
                <motion.div
                  initial={{ opacity: 0, y: 6, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 4, scale: 0.96 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full mt-2 w-44 glass-panel rounded-xl p-1.5 space-y-1 z-50"
                >
                  {[
                    { outcome: 'PERFECT_BOWL', label: 'Good Brick (< t_low)', color: 'text-[#55dbb1]' },
                    { outcome: 'DEFECTIVE_BOWL', label: 'Defect Brick (> t_high)', color: 'text-[#f28d95]' },
                    { outcome: 'REGRASP_TRIGGERED', label: 'Multi-View Re-grasp', color: 'text-[#e9bf79]' },
                  ].map((opt) => (
                    <button
                      key={opt.outcome}
                      onClick={() => handleTriggerCycle(opt.outcome)}
                      className={`w-full text-left px-2.5 py-1.5 rounded-lg hover:bg-white/[0.06] text-[11.5px] font-medium ${opt.color}`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </header>

      {/* Mobile Tab Strip */}
      <div className="flex md:hidden items-center justify-center gap-1 px-4 pt-3">
        {NAV_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 rounded-lg text-[11.5px] font-medium ${
              activeTab === tab.id ? 'bg-[#55dbb1] text-[#070a0f] font-semibold' : 'glass-subtle text-[#8e9bae]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Main Content Stage */}
      <main className="flex-1 w-full max-w-[1440px] mx-auto p-4 sm:p-6">
        <AnimatePresence mode="wait">
          {activeTab === 'cockpit' && (
            <motion.div
              key="tab-cockpit"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22 }}
              className="space-y-4"
            >
              <PerformanceOverview cycles={recentCycles} />
              <ClosedLoopPipeline activeStage={activeStage} cellState={cellState} currentCycle={currentCycle} />

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
                <div className="lg:col-span-8">
                  <DualCameraFeed
                    currentCycle={currentCycle}
                    cellState={cellState}
                    policyBounds={policyBounds}
                    activeStage={activeStage}
                  />
                </div>
                <div className="lg:col-span-4 flex flex-col gap-4">
                  <IntelTelemetry
                    metrics={hardwareMetrics}
                    benchmarks={benchmarks}
                    currentCycle={currentCycle}
                    expanded={false}
                    onOpenBenchTab={() => setActiveTab('bench')}
                  />
                  <NemotronAuditFeed
                    cycles={recentCycles}
                    maxItems={4}
                    onSelectCycle={(cyc) => setSelectedCycle(cyc)}
                    onOpenArchiveTab={() => setActiveTab('history')}
                  />
                </div>
              </div>
            </motion.div>
          )}

          {activeTab === 'bench' && (
            <motion.div
              key="tab-bench"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22 }}
            >
              <IntelTelemetry
                metrics={hardwareMetrics}
                benchmarks={benchmarks}
                currentCycle={currentCycle}
                expanded={true}
              />
            </motion.div>
          )}

          {activeTab === 'copilot' && (
            <motion.div
              key="tab-copilot"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-4"
            >
              <div className="lg:col-span-6">
                <GeminiCopilot
                  activeRules={activeRules}
                  policyHistory={policyHistory}
                  policyHistoryMeta={policyHistoryMeta}
                  onRuleCreated={handleRuleCreated}
                  onRuleDeleted={handleRuleDeleted}
                />
              </div>
              <div className="lg:col-span-6">
                <NemotronAuditFeed
                  cycles={recentCycles}
                  maxItems={10}
                  title="Audited Defect Stream"
                  onSelectCycle={(cyc) => setSelectedCycle(cyc)}
                />
              </div>
            </motion.div>
          )}

          {activeTab === 'history' && (
            <motion.div
              key="tab-history"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22 }}
            >
              <NemotronAuditFeed
                cycles={recentCycles}
                maxItems={40}
                title="Full Inspection & Audit Archive"
                onSelectCycle={(cyc) => setSelectedCycle(cyc)}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <AnimatePresence>
        {selectedCycle && (
          <CycleModal
            cycle={selectedCycle}
            policyBounds={policyBounds}
            onClose={() => setSelectedCycle(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
