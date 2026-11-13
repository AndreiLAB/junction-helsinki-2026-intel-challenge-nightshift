import React, { useState, useRef, useEffect } from 'react';
import { Sparkles, Mic, Video, Send, Volume2, Trash2, Camera, Check, RefreshCw } from 'lucide-react';

export default function GeminiCopilot({ activeRules, onRuleCreated, onRuleDeleted }) {
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);
  const [spokenFeedback, setSpokenFeedback] = useState('');
  
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

  // Quick Preset Prompts
  const quickPrompts = [
    "Reject yellow bricks with black side stripes",
    "Flag red bricks with hairline cracks on top studs",
    "Re-grasp blue bricks if corner glare causes edge ambiguity",
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
        alert("Webcam access unavailable or permission denied. You can still test multimodal rules using text or sample presets!");
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
        
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data);
        };

        recorder.onstop = () => {
          const blob = new Blob(chunks, { type: 'audio/webm' });
          setRecordedAudioBlob(blob);
          stream.getTracks().forEach(t => t.stop());
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
        alert("Microphone unavailable or permission denied. Type your verbal rule below!");
      }
    }
  };

  // Text to speech helper
  const speakConfirmation = (text) => {
    if (!text || typeof window === 'undefined' || !window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn("Speech synthesis error:", e);
    }
  };

  // Submit Rule Form
  const handleSubmitRule = async (e) => {
    if (e) e.preventDefault();
    if (!instruction && !capturedImageBlob && !recordedAudioBlob) {
      alert("Please enter a voice/text instruction or capture an image coupon!");
      return;
    }

    setLoading(true);
    setSpokenFeedback('');

    try {
      const formData = new FormData();
      formData.append('text_instruction', instruction);
      if (capturedImageBlob) {
        formData.append('image', capturedImageBlob, 'snapshot.jpg');
      }
      if (recordedAudioBlob) {
        formData.append('audio', recordedAudioBlob, 'voice.webm');
      }

      const res = await fetch('/api/copilot/rule', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.rule) {
        onRuleCreated(data.rule);
      }

      if (data.spoken_confirmation) {
        setSpokenFeedback(data.spoken_confirmation);
        speakConfirmation(data.spoken_confirmation);
      }

      // Reset inputs
      setInstruction('');
      setCapturedImageBlob(null);
      setCapturedImagePreview(null);
      setRecordedAudioBlob(null);
    } catch (err) {
      console.error("Rule submission error:", err);
      alert("Failed to submit rule to Gemini Copilot.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    return () => {
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(t => t.stop());
      }
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  return (
    <div className="bg-obsidian-900 border border-obsidian-border rounded-xl p-3.5 shadow-xl backdrop-blur-md flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between mb-2.5 border-b border-obsidian-border pb-2">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-intel-light animate-pulse" />
          <h2 className="text-xs font-bold tracking-tight text-white uppercase font-mono">
            Gemini Multimodal Floor Copilot
          </h2>
        </div>
        <div className="flex items-center space-x-1.5">
          <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold">
            gemini-3.8-flash (High)
          </span>
          <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-obsidian-800 text-slate-300">
            Zero-Shot Policy Tuning
          </span>
        </div>
      </div>

      {/* Multimodal Commissioning Form */}
      <form onSubmit={handleSubmitRule} className="space-y-2 mb-3">
        {/* Quick Prompt Chips */}
        <div className="flex flex-wrap gap-1 items-center">
          <span className="text-[10px] text-slate-500 font-mono">Quick rules:</span>
          {quickPrompts.map((prompt, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => setInstruction(prompt)}
              className="text-[10px] font-sans bg-obsidian-950 hover:bg-obsidian-800 text-slate-300 px-2 py-0.5 rounded border border-obsidian-border hover:border-slate-600 transition-colors"
            >
              "{prompt}"
            </button>
          ))}
        </div>

        {/* Text Input Row */}
        <div className="relative flex items-center">
          <input
            type="text"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Speak or type instruction (e.g. 'Reject yellow bricks with black side stripes')..."
            className="w-full bg-obsidian-950 border border-obsidian-border rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-intel-light font-sans pr-28 transition-colors"
          />

          <div className="absolute right-1.5 flex items-center space-x-1">
            {/* Webcam toggle */}
            <button
              type="button"
              onClick={toggleWebcam}
              title={webcamActive ? "Close Webcam" : "Open Laptop Webcam to Show Brick"}
              className={`p-1.5 rounded text-xs transition-colors ${
                webcamActive
                  ? 'bg-intel-blue text-white'
                  : capturedImagePreview
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                  : 'bg-obsidian-800 text-slate-400 hover:text-white'
              }`}
            >
              <Video className="w-3.5 h-3.5" />
            </button>

            {/* Mic toggle */}
            <button
              type="button"
              onClick={toggleRecording}
              title={isRecording ? "Stop Voice Recording" : "Speak Voice Command"}
              className={`p-1.5 rounded text-xs transition-colors ${
                isRecording
                  ? 'bg-rose-600 text-white animate-pulse'
                  : recordedAudioBlob
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                  : 'bg-obsidian-800 text-slate-400 hover:text-white'
              }`}
            >
              <Mic className="w-3.5 h-3.5" />
            </button>

            {/* Submit button */}
            <button
              type="submit"
              disabled={loading}
              className="flex items-center space-x-1 px-2.5 py-1.5 rounded text-xs font-mono font-bold bg-intel-blue hover:bg-intel-light hover:text-slate-950 text-white transition-all disabled:opacity-50"
            >
              {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              <span>{loading ? 'Synthesizing...' : 'Set Rule'}</span>
            </button>
          </div>
        </div>

        {/* Live Webcam Drawer if active */}
        {webcamActive && (
          <div className="p-2 bg-obsidian-950 rounded-lg border border-obsidian-border flex items-center justify-between">
            <div className="relative w-36 h-28 rounded overflow-hidden bg-black border border-obsidian-border">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="w-full h-full object-cover"
              />
              <div className="absolute top-1 left-1 bg-rose-600 px-1 py-0.2 rounded text-[7.5px] font-mono text-white animate-pulse">
                LIVE
              </div>
            </div>

            <div className="flex-1 ml-3 flex flex-col justify-between h-28">
              <div className="text-[11px] text-slate-300 font-sans">
                Hold a marked Duplo test brick up to the camera and click capture.
              </div>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={captureSnapshot}
                  className="flex items-center space-x-1 px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-medium"
                >
                  <Camera className="w-3.5 h-3.5" />
                  <span>Capture Snapshot</span>
                </button>
                {capturedImagePreview && (
                  <span className="text-[10px] text-emerald-400 font-mono flex items-center space-x-1">
                    <Check className="w-3 h-3" />
                    <span>Staged</span>
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Audio Recording State indicator */}
        {isRecording && (
          <div className="p-1.5 bg-rose-950/40 border border-rose-800/60 rounded flex items-center justify-between text-xs font-mono text-rose-300 animate-pulse">
            <span className="flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <span>Listening to operator voice instruction... ({recordingSeconds}s)</span>
            </span>
            <button
              type="button"
              onClick={toggleRecording}
              className="text-xs underline hover:text-white"
            >
              Done Speaking
            </button>
          </div>
        )}

        {/* Spoken Confirmation Banner */}
        {spokenFeedback && (
          <div className="p-2 bg-intel-blue/15 border border-intel-light/40 rounded-lg flex items-start space-x-2 text-xs font-sans text-intel-light shadow-glow-intel">
            <Volume2 className="w-4 h-4 mt-0.5 shrink-0 text-intel-light" />
            <div className="flex-1">
              <div className="font-bold uppercase tracking-wider text-[9px] text-white font-mono">Voice Confirmation:</div>
              <div className="text-slate-200 mt-0.5 text-[11px]">{spokenFeedback}</div>
            </div>
          </div>
        )}
      </form>

      {/* Active Rules List */}
      <div>
        <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1.5">
          <span>Active Sorting Rules ({activeRules.length})</span>
          <span className="text-[10px] text-slate-500">Auto-synced with Intel VLA State Machine</span>
        </div>

        <div className="space-y-1.5 max-h-40 overflow-y-auto pr-1">
          {activeRules.map((rule) => (
            <div
              key={rule.rule_id}
              className="p-2 rounded-lg bg-obsidian-950/80 border border-obsidian-border flex items-start justify-between text-xs group hover:border-slate-700 transition-colors"
            >
              <div className="space-y-0.5">
                <div className="flex items-center space-x-1.5 font-mono">
                  <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase ${
                    rule.target_brick_color === 'yellow' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                    rule.target_brick_color === 'red' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' :
                    rule.target_brick_color === 'blue' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                    rule.target_brick_color === 'green' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' :
                    'bg-obsidian-800 text-slate-300'
                  }`}>
                    {rule.target_brick_color}
                  </span>
                  <span className="text-white font-bold tracking-tight text-[11px]">{rule.rule_id}</span>
                  <span className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                    rule.action_on_match === 'DEFECTIVE_BOWL'
                      ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }`}>
                    {rule.action_on_match}
                  </span>
                </div>

                <div className="text-[11px] text-slate-300 font-sans">{rule.defect_description}</div>
                <div className="text-[10px] text-slate-500 font-mono tabular-nums">
                  Threshold: <span className="text-amber-400 font-bold">{rule.anomaly_threshold}</span> • Reason: {rule.reasoning}
                </div>
              </div>

              <button
                onClick={() => onRuleDeleted(rule.rule_id)}
                title="Remove Rule"
                className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 transition-all"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
