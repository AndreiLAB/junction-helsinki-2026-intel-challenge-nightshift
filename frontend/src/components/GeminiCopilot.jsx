import React, { useState, useRef } from 'react';
import { Sparkles, Mic, Camera, Send, Volume2, Trash2, RefreshCw, Database, Clock } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || (window.location.port === '5173' ? 'http://localhost:8000' : (window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''));

export default function GeminiCopilot({
  activeRules,
  policyHistory = [],
  policyHistoryMeta = { provider: 'FALLBACK', activeThreshold: 0.55 },
  onRuleCreated,
  onRuleDeleted,
}) {
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);
  const [spokenFeedback, setSpokenFeedback] = useState('');
  const [panelMode, setPanelMode] = useState('rules'); // 'rules' | 'timeline'

  // Media State
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

  // Quick Preset Prompts matching Figma
  const quickPrompts = [
    "Reject yellow bricks with black side stripes",
    "Re-grasp blue bricks",
  ];

  // Start webcam
  const toggleWebcam = async () => {
    if (webcamActive) {
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(track => track.stop());
      }
      setWebcamActive(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
        mediaStreamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setWebcamActive(true);
      } catch (err) {
        console.warn("Webcam access error:", err);
        alert("Webcam access unavailable. You can still create multimodal rules via text or presets!");
      }
    }
  };

  // Capture snapshot from webcam
  const captureSnapshot = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      setCapturedImageBlob(blob);
      setCapturedImagePreview(canvas.toDataURL('image/jpeg'));
    }, 'image/jpeg', 0.85);
  };

  // Voice recording
  const toggleRecording = async () => {
    if (isRecording) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
      clearInterval(timerRef.current);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorder(stream);
        const chunks = [];

        recorder.ondataavailable = (e) => chunks.push(e.data);
        recorder.onstop = () => {
          const audioBlob = new Blob(chunks, { type: 'audio/webm' });
          setRecordedAudioBlob(audioBlob);
          stream.getTracks().forEach(track => track.stop());
        };

        recorder.start();
        mediaRecorderRef.current = recorder;
        setIsRecording(true);
        setRecordingSeconds(0);
        timerRef.current = setInterval(() => {
          setRecordingSeconds(s => s + 1);
        }, 1000);
      } catch (err) {
        console.warn("Microphone access error:", err);
        alert("Microphone access unavailable.");
      }
    }
  };

  // Submit Rule to Backend
  const handleSubmitRule = async (promptText) => {
    const textToSend = promptText || instruction;
    if (!textToSend.trim() && !capturedImageBlob && !recordedAudioBlob) return;

    setLoading(true);
    setSpokenFeedback('');

    const formData = new FormData();
    formData.append('text_instruction', textToSend);
    if (capturedImageBlob) {
      formData.append('image', capturedImageBlob, 'snapshot.jpg');
    }
    if (recordedAudioBlob) {
      formData.append('audio', recordedAudioBlob, 'voice_instruction.webm');
    }

    try {
      const res = await fetch(`${API_BASE}/api/copilot/rule`, {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        if (data.rule) {
          onRuleCreated(data.rule);
          setSpokenFeedback(data.spoken_confirmation || 'Sorting rule synchronized.');

          // Speak aloud confirmation using Web Speech API
          if ('speechSynthesis' in window && data.spoken_confirmation) {
            const utterance = new SpeechSynthesisUtterance(data.spoken_confirmation);
            utterance.rate = 1.05;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
          }
        }
        setInstruction('');
        setCapturedImageBlob(null);
        setCapturedImagePreview(null);
        setRecordedAudioBlob(null);
      }
    } catch (err) {
      console.error("Failed to submit rule:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-4 flex flex-col justify-between h-full">
      {/* Header */}
      <div>
        <div className="flex items-center justify-between pb-2 border-b border-[#26313e]">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-[#55dbb1]" />
            <h2 className="text-[16px] font-semibold text-[#edf2f7]">
              Floor copilot
            </h2>
          </div>
          <div className="bg-[#18212c] px-2.5 py-0.5 rounded-[4px] border border-[#26313e]">
            <span className="text-[10px] font-medium text-[#b5c0ce]">
              Gemini 3.8 Flash
            </span>
          </div>
        </div>

        <div className="text-[11px] text-[#8e9bae] mt-2 mb-3">
          Set sorting rules with natural language, voice, or camera.
        </div>

        {/* Live Webcam Pane if toggled */}
        {webcamActive && (
          <div className="mb-3 p-2 bg-[#0b0f14] border border-[#26313e] rounded-[6px] relative">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-32 object-cover rounded bg-black"
            />
            <div className="flex items-center justify-between mt-2">
              <button
                type="button"
                onClick={captureSnapshot}
                className="px-2.5 py-1 bg-[#55dbb1] text-[#0b0f14] rounded text-[11px] font-semibold flex items-center space-x-1"
              >
                <Camera className="w-3.5 h-3.5" />
                <span>Capture Snapshot</span>
              </button>
              <button
                type="button"
                onClick={toggleWebcam}
                className="px-2 py-1 bg-[#18212c] text-[#8e9bae] rounded text-[11px]"
              >
                Close Camera
              </button>
            </div>
          </div>
        )}

        {/* Captured Snapshot preview chip */}
        {capturedImagePreview && (
          <div className="mb-2 flex items-center space-x-2 bg-[#18212c] p-1.5 rounded-[5px] border border-[#55dbb1]/40">
            <img src={capturedImagePreview} alt="Snapshot" className="w-8 h-8 rounded object-cover" />
            <span className="text-[10px] text-[#55dbb1] font-medium">Webcam snapshot attached</span>
            <button
              onClick={() => { setCapturedImagePreview(null); setCapturedImageBlob(null); }}
              className="text-[10px] text-[#f28d95] ml-auto hover:underline"
            >
              Remove
            </button>
          </div>
        )}

        {/* Sorting Instruction Composer */}
        <div className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-1.5 flex items-center space-x-2">
          <input
            type="text"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSubmitRule()}
            placeholder="Describe a sorting rule…"
            className="flex-1 bg-transparent px-2 text-[12px] text-[#edf2f7] placeholder-[#8e9bae] focus:outline-none"
          />

          {/* Camera Button */}
          <button
            type="button"
            onClick={toggleWebcam}
            title="Inspect via Laptop Webcam"
            className={`p-1.5 rounded transition-colors ${
              webcamActive ? 'text-[#55dbb1] bg-[#15352e]' : 'text-[#8e9bae] hover:text-[#edf2f7]'
            }`}
          >
            <Camera className="w-4 h-4" />
          </button>

          {/* Mic Button */}
          <button
            type="button"
            onClick={toggleRecording}
            title={isRecording ? `Recording... (${recordingSeconds}s)` : "Voice Instruction"}
            className={`p-1.5 rounded transition-colors ${
              isRecording ? 'text-[#f28d95] bg-[#38232c] animate-pulse' : 'text-[#8e9bae] hover:text-[#edf2f7]'
            }`}
          >
            <Mic className="w-4 h-4" />
          </button>

          {/* Set Rule Button */}
          <button
            type="button"
            onClick={() => handleSubmitRule()}
            disabled={loading}
            className="bg-[#55dbb1] hover:bg-[#55dbb1]/90 text-[#0b0f14] px-3.5 py-1.5 rounded-[4px] text-[11px] font-semibold flex items-center space-x-1.5 transition-all disabled:opacity-50 shrink-0"
          >
            {loading ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <>
                <span>Set rule</span>
                <Send className="w-3 h-3" />
              </>
            )}
          </button>
        </div>

        {/* Spoken feedback banner if any */}
        {spokenFeedback && (
          <div className="mt-2 p-2 bg-[#15352e] border border-[#55dbb1]/30 rounded-[5px] flex items-center space-x-2 text-[11px] text-[#55dbb1]">
            <Volume2 className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">{spokenFeedback}</span>
          </div>
        )}

        {/* TRY Chips Row */}
        <div className="flex items-center space-x-2 mt-2.5 mb-3 flex-wrap gap-y-1.5">
          <span className="text-[9px] font-medium text-[#8e9bae] tracking-wider uppercase">
            TRY
          </span>
          {quickPrompts.map((q, idx) => (
            <button
              key={idx}
              onClick={() => {
                setInstruction(q);
                handleSubmitRule(q);
              }}
              className="bg-[#18212c] hover:bg-[#18212c]/80 text-[#b5c0ce] hover:text-[#edf2f7] text-[10px] font-medium px-2.5 py-1 rounded-[4px] border border-[#26313e]/60 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>

        {/* Divider */}
        <div className="h-px bg-[#26313e] my-3" />

        {/* Active Sorting Rules / MariaDB Temporal Timeline Toggle */}
        <div>
          <div className="flex items-center justify-between mb-2 gap-2">
            <div className="flex items-center bg-[#0b0f14] p-0.5 rounded-[5px] border border-[#26313e]">
              <button
                type="button"
                onClick={() => setPanelMode('rules')}
                className={`px-2.5 py-1 rounded-[4px] text-[11px] font-medium flex items-center space-x-1.5 transition-colors ${
                  panelMode === 'rules'
                    ? 'bg-[#18212c] text-[#edf2f7]'
                    : 'text-[#8e9bae] hover:text-[#edf2f7]'
                }`}
              >
                <span>Active rules</span>
                <span className="bg-[#0e131a] text-[#b5c0ce] text-[10px] px-1.5 py-0.2 rounded">
                  {activeRules.length}
                </span>
              </button>
              <button
                type="button"
                onClick={() => setPanelMode('timeline')}
                className={`px-2.5 py-1 rounded-[4px] text-[11px] font-medium flex items-center space-x-1.5 transition-colors ${
                  panelMode === 'timeline'
                    ? 'bg-[#15352e] text-[#55dbb1] border border-[#55dbb1]/30'
                    : 'text-[#8e9bae] hover:text-[#edf2f7]'
                }`}
              >
                <Database className="w-3 h-3" />
                <span>Policy Timeline</span>
                <span className="bg-[#0e131a] text-[#b5c0ce] text-[10px] px-1.5 py-0.2 rounded">
                  {policyHistory.length}
                </span>
              </button>
            </div>

            {panelMode === 'timeline' ? (
              <span
                className={`text-[9px] font-mono px-1.5 py-0.5 rounded border shrink-0 ${
                  policyHistoryMeta?.provider === 'LIVE'
                    ? 'text-[#55dbb1] bg-[#15352e]/70 border-[#55dbb1]/30'
                    : 'text-[#e9bf79] bg-[#352e21]/60 border-[#e9bf79]/25'
                }`}
                title="MariaDB WITH SYSTEM VERSIONING · SELECT ... FOR SYSTEM_TIME ALL"
              >
                {policyHistoryMeta?.provider === 'LIVE' ? 'MariaDB Temporal LIVE' : 'In-Memory Log'}
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setPanelMode('timeline')}
                className="text-[10px] font-medium text-[#55dbb1] hover:underline cursor-pointer shrink-0"
              >
                MariaDB Temporal →
              </button>
            )}
          </div>

          {panelMode === 'rules' ? (
            <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
              {activeRules.length === 0 ? (
                <div className="text-center py-4 text-[#8e9bae] text-[11px]">
                  No custom sorting rules active.
                </div>
              ) : (
                activeRules.slice(0, 6).map((rule) => {
                  const isReject = rule.action_on_match === 'DEFECTIVE_BOWL';
                  const colorUpper = (rule.target_brick_color || 'ANY').toUpperCase();

                  return (
                    <div
                      key={rule.rule_id}
                      className="flex items-center justify-between p-2 rounded-[5px] bg-[#18212c]/40 border border-[#26313e]/60 hover:border-[#26313e] transition-colors group"
                    >
                      <div className="flex items-center space-x-2.5 min-w-0">
                        <div className={`px-2 py-0.5 rounded-[4px] text-[10px] font-medium shrink-0 ${
                          colorUpper === 'YELLOW' ? 'bg-[#352e21] text-[#e9bf79]' :
                          colorUpper === 'RED' ? 'bg-[#38232c] text-[#f28d95]' :
                          colorUpper === 'BLUE' ? 'bg-[#18212c] text-[#89b9ef]' :
                          'bg-[#18212c] text-[#b5c0ce]'
                        }`}>
                          {colorUpper}
                        </div>

                        <div className="min-w-0">
                          <div className="text-[11px] font-medium text-[#edf2f7] truncate">
                            {rule.defect_description || rule.rule_id}
                          </div>
                          <div className="text-[10px] text-[#8e9bae] truncate tabular-nums">
                            Threshold {rule.anomaly_threshold || 0.55}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 shrink-0">
                        <div className={`px-2 py-0.5 rounded-[4px] text-[10px] font-medium ${
                          isReject ? 'bg-[#38232c] text-[#f28d95]' : 'bg-[#352e21] text-[#e9bf79]'
                        }`}>
                          {isReject ? 'Reject' : 'Re-grasp'}
                        </div>

                        <button
                          onClick={() => onRuleDeleted(rule.rule_id)}
                          className="text-[#8e9bae] hover:text-[#f28d95] p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                          title="Delete rule"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          ) : (
            <div className="space-y-2 max-h-[180px] overflow-y-auto pr-1">
              <div className="px-2 py-1 rounded bg-[#0b0f14] border border-[#26313e]/80 flex items-center justify-between text-[10px] text-[#8e9bae] font-mono">
                <span>FOR SYSTEM_TIME ALL</span>
                <span className="text-[#55dbb1] tabular-nums">
                  Active Threshold: {Number(policyHistoryMeta?.activeThreshold ?? 0.55).toFixed(2)}
                </span>
              </div>

              {policyHistory.length === 0 ? (
                <div className="text-center py-4 text-[#8e9bae] text-[11px]">
                  No temporal policy versions recorded yet.
                </div>
              ) : (
                policyHistory.map((item, idx) => {
                  const isCurrent = Boolean(item.is_current);
                  const src = (item.source || '').toLowerCase();
                  const sourceLabel = src.includes('gemini')
                    ? 'Gemini 3.8'
                    : src.includes('nemotron') || src.includes('verda')
                    ? 'Nemotron B300'
                    : src.includes('operator')
                    ? 'Operator UI'
                    : 'Bootstrap';
                  const validFromShort = item.valid_from ? item.valid_from.split(' ')[1] || item.valid_from : '—';
                  const validToShort = item.valid_to ? item.valid_to.split(' ')[1] || item.valid_to : 'NOW';

                  return (
                    <div
                      key={`${item.policy_id}-${item.valid_from || idx}`}
                      className={`p-2 rounded-[5px] border transition-colors ${
                        isCurrent
                          ? 'bg-[#18212c]/60 border-[#26313e]'
                          : 'bg-[#0e131a]/80 border-[#26313e]/40 opacity-80'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center space-x-1.5 min-w-0">
                          <span className={`px-1.5 py-0.2 rounded text-[9px] font-semibold uppercase tracking-wide shrink-0 ${
                            sourceLabel === 'Gemini 3.8'
                              ? 'bg-[#15352e] text-[#55dbb1]'
                              : sourceLabel === 'Nemotron B300'
                              ? 'bg-[#1b2a3d] text-[#89b9ef]'
                              : 'bg-[#18212c] text-[#b5c0ce]'
                          }`}>
                            {sourceLabel}
                          </span>
                          <span className="text-[10px] font-mono text-[#edf2f7] truncate">
                            {item.event_type}
                          </span>
                        </div>
                        <span className={`text-[9px] font-mono px-1.5 py-0.2 rounded shrink-0 ${
                          isCurrent
                            ? 'text-[#55dbb1] bg-[#15352e]/60'
                            : 'text-[#8e9bae] bg-[#18212c]'
                        }`}>
                          {isCurrent ? 'CURRENT' : 'HISTORY'}
                        </span>
                      </div>

                      <div className="mt-1 text-[11px] text-[#edf2f7] truncate">
                        {item.defect_description || item.policy_id}
                      </div>

                      <div className="mt-1 flex items-center justify-between text-[9px] text-[#8e9bae] font-mono tabular-nums">
                        <span className="flex items-center space-x-1 truncate">
                          <Clock className="w-2.5 h-2.5 shrink-0 text-[#8e9bae]" />
                          <span>{validFromShort} → {validToShort}</span>
                        </span>
                        <span className="text-[#b5c0ce] shrink-0 ml-2">
                          thr={Number(item.anomaly_threshold ?? 0.55).toFixed(2)}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
