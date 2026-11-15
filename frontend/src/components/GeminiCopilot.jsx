import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, Mic, Camera, Send, Volume2, Trash2, RefreshCw, Database, Clock } from 'lucide-react';

const API_BASE =
  import.meta.env.VITE_API_URL ||
  (window.location.port === '5173'
    ? 'http://localhost:8000'
    : window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : '');

export default function GeminiCopilot({
  activeRules = [],
  policyHistory = [],
  policyHistoryMeta = { provider: 'FALLBACK', activeThreshold: 0.55 },
  onRuleCreated,
  onRuleDeleted,
}) {
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);
  const [spokenFeedback, setSpokenFeedback] = useState('');
  const [panelMode, setPanelMode] = useState('rules');

  const [webcamActive, setWebcamActive] = useState(false);
  const [capturedImageBlob, setCapturedImageBlob] = useState(null);
  const [capturedImagePreview, setCapturedImagePreview] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordedAudioBlob, setRecordedAudioBlob] = useState(null);
  const [recordingSeconds, setRecordingSeconds] = useState(0);

  const videoRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const timerRef = useRef(null);

  const quickPrompts = [
    'Reject bricks with white tape and blue X into pink defect bowl',
    'Put back and re-grasp bricks scoring in 0.45 to 0.60 band',
  ];

  const toggleWebcam = async () => {
    if (webcamActive) {
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
      setWebcamActive(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        mediaStreamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        setWebcamActive(true);
      } catch {
        setSpokenFeedback('Webcam unavailable here — use text or preset rules.');
      }
    }
  };

  const captureSnapshot = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    canvas.getContext('2d').drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      setCapturedImageBlob(blob);
      setCapturedImagePreview(canvas.toDataURL('image/jpeg'));
    }, 'image/jpeg', 0.85);
  };

  const toggleRecording = async () => {
    if (isRecording) {
      if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
      setIsRecording(false);
      clearInterval(timerRef.current);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorder(stream);
        const chunks = [];
        recorder.ondataavailable = (e) => chunks.push(e.data);
        recorder.onstop = () => {
          setRecordedAudioBlob(new Blob(chunks, { type: 'audio/webm' }));
          stream.getTracks().forEach((t) => t.stop());
        };
        recorder.start();
        mediaRecorderRef.current = recorder;
        setIsRecording(true);
        setRecordingSeconds(0);
        timerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
      } catch {
        setSpokenFeedback('Microphone unavailable here — type a sorting rule directly.');
      }
    }
  };

  const handleSubmitRule = async (promptText) => {
    const textToSend = promptText || instruction;
    if (!textToSend.trim() && !capturedImageBlob && !recordedAudioBlob) return;
    setLoading(true);
    setSpokenFeedback('');

    const formData = new FormData();
    formData.append('text_instruction', textToSend);
    if (capturedImageBlob) formData.append('image', capturedImageBlob, 'snapshot.jpg');
    if (recordedAudioBlob) formData.append('audio', recordedAudioBlob, 'voice_instruction.webm');

    try {
      const res = await fetch(`${API_BASE}/api/copilot/rule`, { method: 'POST', body: formData });
      if (res.ok) {
        const data = await res.json();
        if (data.rule) {
          onRuleCreated(data.rule);
          setSpokenFeedback(data.spoken_confirmation || 'Sorting rule synchronized.');
          if ('speechSynthesis' in window && data.spoken_confirmation) {
            const u = new SpeechSynthesisUtterance(data.spoken_confirmation);
            u.rate = 1.05;
            window.speechSynthesis.speak(u);
          }
        }
      } else {
        throw new Error('offline');
      }
    } catch {
      // Standalone Figma Make fallback simulation
      const lower = textToSend.toLowerCase();
      const color = ['yellow', 'blue', 'red', 'green'].find((c) => lower.includes(c)) || 'any';
      const isRegrasp = lower.includes('grasp') || lower.includes('re-orient');
      const localRule = {
        rule_id: `rule_${Date.now().toString().slice(-4)}`,
        target_brick_color: color,
        defect_description: textToSend.trim(),
        anomaly_threshold: isRegrasp ? 0.48 : 0.52,
        action_on_match: isRegrasp ? 'REGRASP_AND_RECHECK' : 'DEFECTIVE_BOWL',
        spoken_confirmation: `Rule active: ${textToSend.trim()}`,
      };
      onRuleCreated(localRule);
      setSpokenFeedback(localRule.spoken_confirmation);
    } finally {
      setInstruction('');
      setCapturedImageBlob(null);
      setCapturedImagePreview(null);
      setRecordedAudioBlob(null);
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="glass-panel rounded-xl p-5 flex flex-col justify-between h-full space-y-4"
    >
      <div className="space-y-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#15352e]/80 border border-[#55dbb1]/30 flex items-center justify-center text-[#55dbb1]">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-[15px] font-semibold text-[#edf2f7]">Floor Copilot</h2>
              <p className="text-[11.5px] text-[#8e9bae]">
                Gemini 3.8 Flash · Voice, text, or camera sorting policies
              </p>
            </div>
          </div>
        </div>

        {webcamActive && (
          <div className="p-2.5 rounded-xl bg-[#06090f] border border-white/[0.08] space-y-2">
            <video ref={videoRef} autoPlay playsInline muted className="w-full h-36 object-cover rounded-lg bg-black" />
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={captureSnapshot}
                className="px-3 py-1 bg-[#55dbb1] text-[#070a0f] rounded-md text-[11px] font-semibold flex items-center gap-1.5"
              >
                <Camera className="w-3.5 h-3.5" /> Capture
              </button>
              <button
                type="button"
                onClick={toggleWebcam}
                className="px-2.5 py-1 text-[#8e9bae] hover:text-[#edf2f7] text-[11px]"
              >
                Close
              </button>
            </div>
          </div>
        )}

        {capturedImagePreview && (
          <div className="flex items-center gap-2.5 glass-subtle p-2 rounded-lg">
            <img src={capturedImagePreview} alt="Snapshot" className="w-8 h-8 rounded object-cover" />
            <span className="text-[11px] text-[#55dbb1]">Snapshot attached</span>
            <button
              onClick={() => { setCapturedImagePreview(null); setCapturedImageBlob(null); }}
              className="ml-auto text-[11px] text-[#f28d95] hover:underline"
            >
              Remove
            </button>
          </div>
        )}

        {/* Composer */}
        <div className="flex items-center gap-2 bg-[#06090f] border border-white/[0.08] focus-within:border-[#55dbb1]/50 rounded-xl p-1.5 transition-colors">
          <input
            type="text"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmitRule()}
            placeholder="Describe a defect rule or threshold adjustment…"
            className="flex-1 bg-transparent px-2.5 text-[12.5px] text-[#edf2f7] placeholder-[#8e9bae]/70 focus:outline-none"
          />
          <button
            type="button"
            onClick={toggleWebcam}
            className={`p-2 rounded-lg transition-colors ${webcamActive ? 'text-[#55dbb1] bg-[#15352e]' : 'text-[#8e9bae] hover:text-[#edf2f7]'}`}
          >
            <Camera className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={toggleRecording}
            title={isRecording ? `Recording (${recordingSeconds}s)` : 'Voice rule'}
            className={`p-2 rounded-lg transition-colors ${isRecording ? 'text-[#f28d95] bg-[#38232c] animate-pulse' : 'text-[#8e9bae] hover:text-[#edf2f7]'}`}
          >
            <Mic className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => handleSubmitRule()}
            disabled={loading}
            className="bg-[#55dbb1] hover:bg-[#55dbb1]/90 text-[#070a0f] px-3.5 py-1.5 rounded-lg text-[11.5px] font-semibold flex items-center gap-1.5 transition-all active:scale-95 disabled:opacity-50"
          >
            {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <><span>Apply</span><Send className="w-3 h-3" /></>}
          </button>
        </div>

        <AnimatePresence>
          {spokenFeedback && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="px-3 py-2 rounded-lg bg-[#15352e]/60 border border-[#55dbb1]/30 flex items-center gap-2 text-[11.5px] text-[#55dbb1]"
            >
              <Volume2 className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{spokenFeedback}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Quick Presets */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#8e9bae] mr-1">Presets</span>
          {quickPrompts.map((q, i) => (
            <button
              key={i}
              onClick={() => handleSubmitRule(q)}
              className="px-2.5 py-1 rounded-md glass-subtle hover:border-[#55dbb1]/30 text-[11px] text-[#b5c0ce] hover:text-[#edf2f7] transition-colors"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Toggle: Active Rules vs MariaDB Temporal */}
        <div className="pt-2 border-t border-white/[0.06] space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center bg-[#06090f] p-0.5 rounded-lg border border-white/[0.06]">
              {[
                { id: 'rules', label: `Active Rules (${activeRules.length})` },
                { id: 'timeline', label: `MariaDB Timeline (${policyHistory.length})`, icon: Database },
              ].map((t) => {
                const Icon = t.icon;
                const active = panelMode === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setPanelMode(t.id)}
                    className={`relative px-3 py-1 rounded-md text-[11px] font-medium flex items-center gap-1.5 transition-colors ${
                      active ? 'text-[#edf2f7]' : 'text-[#8e9bae] hover:text-[#edf2f7]'
                    }`}
                  >
                    {active && (
                      <motion.span
                        layoutId="copilotModePill"
                        transition={{ type: 'spring', stiffness: 360, damping: 28 }}
                        className="absolute inset-0 bg-white/[0.08] rounded-md"
                      />
                    )}
                    {Icon && <Icon className="relative z-10 w-3 h-3 text-[#55dbb1]" />}
                    <span className="relative z-10">{t.label}</span>
                  </button>
                );
              })}
            </div>

            {panelMode === 'timeline' && (
              <span className="text-[10px] font-mono text-[#55dbb1]">
                {policyHistoryMeta?.provider === 'LIVE' ? 'FOR SYSTEM_TIME ALL · LIVE' : 'FOR SYSTEM_TIME ALL'}
              </span>
            )}
          </div>

          <AnimatePresence mode="wait">
            {panelMode === 'rules' ? (
              <motion.div
                key="rules-list"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="space-y-2 max-h-[260px] overflow-y-auto pr-1"
              >
                {activeRules.map((rule) => {
                  const isReject = rule.action_on_match === 'DEFECTIVE_BOWL';
                  return (
                    <motion.div
                      layout
                      key={rule.rule_id}
                      className="glass-subtle rounded-lg px-3 py-2.5 flex items-center justify-between gap-2 group"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-white/[0.06] text-[#b5c0ce]">
                            {(rule.target_brick_color || 'ANY').toUpperCase()}
                          </span>
                          <span className="text-[12px] font-medium text-[#edf2f7] truncate">
                            {rule.defect_description || rule.rule_id}
                          </span>
                        </div>
                        <div className="text-[10.5px] font-mono text-[#8e9bae] mt-0.5">
                          threshold {Number(rule.anomaly_threshold || 0.55).toFixed(2)}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                            isReject ? 'bg-[#38232c] text-[#f28d95]' : 'bg-[#352e21] text-[#e9bf79]'
                          }`}
                        >
                          {isReject ? 'Defect Bowl' : 'Re-grasp'}
                        </span>
                        <button
                          onClick={() => onRuleDeleted(rule.rule_id)}
                          className="text-[#8e9bae] hover:text-[#f28d95] p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </motion.div>
                  );
                })}
              </motion.div>
            ) : (
              <motion.div
                key="timeline-list"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="space-y-2 max-h-[260px] overflow-y-auto pr-1"
              >
                {policyHistory.map((item, idx) => (
                  <div
                    key={`${item.policy_id}-${item.valid_from || idx}`}
                    className={`rounded-lg px-3 py-2 border ${
                      item.is_current ? 'glass-subtle' : 'bg-white/[0.01] border-white/[0.04] opacity-70'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 text-[10.5px] font-mono">
                      <span className="text-[#89b9ef]">{item.event_type}</span>
                      <span className={item.is_current ? 'text-[#55dbb1]' : 'text-[#8e9bae]'}>
                        {item.is_current ? 'CURRENT' : 'HISTORY'}
                      </span>
                    </div>
                    <div className="text-[11.5px] text-[#edf2f7] truncate mt-0.5">
                      {item.defect_description || item.policy_id}
                    </div>
                    <div className="flex items-center justify-between text-[10px] font-mono text-[#8e9bae] mt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-2.5 h-2.5" />
                        {item.valid_from || '—'} → {item.valid_to || 'NOW'}
                      </span>
                      <span className="text-[#edf2f7]">thr={Number(item.anomaly_threshold ?? 0.55).toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
