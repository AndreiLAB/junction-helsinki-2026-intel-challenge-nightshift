import React, { useState } from 'react';
import {
  CheckCircle2,
  Copy,
  Check,
  Terminal,
  Clock,
  ShieldAlert,
  Camera,
  PackageCheck,
  Users,
  Grid
} from 'lucide-react';

const STUDIO_TASKS = [
  'Pick up a brick and hold it in front of the inspection camera.',
  'Put the brick in the good bowl.',
  'Put the brick in the defective bowl.',
];

const AGENT_PHRASES = [
  { label: 'Ask Lead what team should do now', cmd: 'what now?', target: 'Lead tab' },
  { label: 'Short update from an agent', cmd: 'status', target: 'Any agent tab' },
  { label: 'Pick up news from other agents', cmd: 'sync', target: 'Any agent tab' },
  {
    label: 'Unblock an agent going in circles',
    cmd: 'Stop. Tell me in plain words what is blocking you and the simplest way around it.',
    target: 'Stuck agent tab',
  },
  {
    label: 'Restarted session recovery',
    cmd: 'You are a restarted session. Read docs/STATUS.md and continue.',
    target: 'Restarted tab',
  },
  {
    label: 'Resume a closed tab',
    cmd: 'cd ~/duplo-cell && claude --resume',
    target: 'New terminal tab',
  },
];

const TIMETABLE = [
  {
    id: 'sat-1330',
    time: 'Sat 13:30',
    goal: 'Table ready (taped & outlined). Arms & cameras work in Studio. Lead says READY FOR HELPERS & helper tabs open.',
    fallback: 'Ask an Intel mentor about Studio now, and tell the Lead what is not working.',
  },
  {
    id: 'sat-1600',
    time: 'Sat 16:00',
    goal: '30 cycles recorded (15 unmarked, 15 marked). ~150 unmarked + ~40 marked inspection photos taken. Short test training run in cloud.',
    fallback: 'Keep recording, and type what now? in the Lead tab.',
  },
  {
    id: 'sat-1900',
    time: 'Sat 19:00',
    goal: 'Arm has moved by itself from a trained model. GOOD or DEFECT verdict appears on screen for a brick at inspection camera. Full training running.',
    fallback: 'We missed the 19:00 checkpoint. Choose the simpler path.',
  },
  {
    id: 'sat-2300',
    time: 'Sat 23:00',
    goal: 'One real brick sorted into the right bowl with no human touch. Run Prompt 5 ( the Judge ).',
    fallback: 'We missed the 23:00 checkpoint. Choose the simpler path.',
  },
  {
    id: 'sun-0300',
    time: 'Sun 03:00',
    goal: '8 of 10 bricks sorted, on video. Feature freeze: only fixes from here. Run Prompt 5 ( the Judge ).',
    fallback: 'We missed the 03:00 checkpoint. Choose the simpler path.',
  },
  {
    id: 'sun-0900',
    time: 'Sun 09:00',
    goal: 'Submitted on Junction Platform (1h before 10:00 deadline). 20-brick backup video filmed; 3-min demo rehearsed 3x.',
    fallback: 'Submit what you have. An honest partial result with a video beats nothing.',
  },
];

const ROLES = [
  {
    role: 'Operator',
    desc: 'Sits at the hackathon laptop, pastes prompts, and answers the agents (checks tabs every 15 mins for NEED A HUMAN).',
  },
  {
    role: 'Robot hand',
    desc: 'Moves the controller arm smoothly for Studio demonstrations and holds the physical power switch/plug during autonomous robot runs.',
  },
  {
    role: 'Brick keeper',
    desc: 'Places & resets bricks lightly on the 3×3 grid, marks defects on >=2 sides, seals 5 unmarked + 5 marked in the EXAM bag, logs what worked.',
  },
  {
    role: 'Timekeeper',
    desc: 'Watches the 6 Helsinki checkpoints, talks to Intel/Modal mentors, screenshots Studio (dataset, training, export), films video & submits by 09:00.',
  },
];

export default function StationPlaybook() {
  const [copiedKey, setCopiedKey] = useState(null);
  const [completedCheckpoints, setCompletedCheckpoints] = useState({ 'sat-1330': true });
  const [heldOutSquares, setHeldOutSquares] = useState([2, 6]); // default 2 held-out squares on 3x3 grid
  const [cyclesRecorded, setCyclesRecorded] = useState(0);

  const copyText = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  const toggleCheckpoint = (id) => {
    setCompletedCheckpoints((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleSquare = (idx) => {
    setHeldOutSquares((prev) => {
      if (prev.includes(idx)) return prev.filter((i) => i !== idx);
      if (prev.length >= 2) return [prev[1], idx];
      return [...prev, idx];
    });
  };

  return (
    <div className="space-y-4">
      {/* Top Banner: Physical AI Studio Exact Task Names & 3x3 Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Studio Tasks Card */}
        <div className="lg:col-span-7 bg-[#121922] border border-[#26313e] rounded-[8px] p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2.5 border-b border-[#26313e]">
              <div className="flex items-center space-x-2">
                <Camera className="w-4 h-4 text-[#55dbb1]" />
                <h2 className="text-[15px] font-semibold text-[#edf2f7]">
                  Physical AI Studio — 3 Exact Task Names
                </h2>
              </div>
              <span className="bg-[#352e21] text-[#e9bf79] border border-[#e9bf79]/30 px-2 py-0.5 rounded-[4px] text-[10px] font-medium">
                Copy with full stop (.) included
              </span>
            </div>

            <p className="text-[11px] text-[#8e9bae] mt-2 mb-3">
              One cycle is <strong>two recordings</strong>: first a <strong>pick</strong> (hold still 1s in front of inspection camera, then stop), then without letting go start the <strong>place</strong> recording to the GOOD or DEFECTIVE bowl and return to rest.
            </p>

            <div className="space-y-2">
              {STUDIO_TASKS.map((task, idx) => (
                <div
                  key={idx}
                  className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-2.5 flex items-center justify-between gap-2"
                >
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <span className="w-5 h-5 rounded bg-[#18212c] text-[#55dbb1] text-[10px] font-mono font-bold flex items-center justify-center shrink-0">
                      {idx + 1}
                    </span>
                    <code className="text-[12px] text-[#edf2f7] font-mono truncate select-all">
                      {task}
                    </code>
                  </div>
                  <button
                    onClick={() => copyText(task, `task-${idx}`)}
                    className="px-2.5 py-1 rounded bg-[#18212c] hover:bg-[#26313e] text-[#b5c0ce] hover:text-[#edf2f7] text-[10px] font-medium flex items-center space-x-1 shrink-0 transition-colors"
                  >
                    {copiedKey === `task-${idx}` ? (
                      <>
                        <Check className="w-3 h-3 text-[#55dbb1]" />
                        <span className="text-[#55dbb1]">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Round 1 Quota Bar */}
          <div className="mt-4 pt-3 border-t border-[#26313e]/70 flex flex-wrap items-center justify-between gap-2 text-[11px]">
            <div className="flex items-center space-x-3">
              <span className="text-[#8e9bae]">Round 1 Demo Target:</span>
              <span className="font-semibold text-[#55dbb1] tabular-nums">
                {cyclesRecorded} / 30 cycles
              </span>
              <span className="text-[#8e9bae]">(15 unmarked · 15 marked)</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <button
                onClick={() => setCyclesRecorded((c) => Math.max(0, c - 1))}
                className="px-2 py-0.5 rounded bg-[#18212c] text-[#b5c0ce] hover:text-[#edf2f7] text-[11px]"
              >
                -1
              </button>
              <button
                onClick={() => setCyclesRecorded((c) => Math.min(30, c + 1))}
                className="px-2.5 py-0.5 rounded bg-[#55dbb1] text-[#0b0f14] font-semibold text-[11px]"
              >
                +1 Cycle
              </button>
            </div>
          </div>
        </div>

        {/* 3x3 Duplo Plate Grid & Inspection Photo Quotas */}
        <div className="lg:col-span-5 bg-[#121922] border border-[#26313e] rounded-[8px] p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2.5 border-b border-[#26313e]">
              <div className="flex items-center space-x-2">
                <Grid className="w-4 h-4 text-[#89b9ef]" />
                <h2 className="text-[15px] font-semibold text-[#edf2f7]">
                  3×3 Plate Grid &amp; EXAM Bag
                </h2>
              </div>
              <span className="text-[10px] text-[#8e9bae]">
                Click 2 squares to hold out
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3 items-center">
              {/* Interactive 3x3 Grid */}
              <div className="grid grid-cols-3 gap-1.5 bg-[#0b0f14] p-2.5 rounded-[6px] border border-[#26313e] aspect-square max-w-[165px] mx-auto w-full">
                {Array.from({ length: 9 }).map((_, idx) => {
                  const isHeldOut = heldOutSquares.includes(idx);
                  const row = Math.floor(idx / 3) + 1;
                  const col = (idx % 3) + 1;
                  return (
                    <button
                      key={idx}
                      onClick={() => toggleSquare(idx)}
                      className={`rounded-[4px] flex flex-col items-center justify-center text-[10px] font-mono border transition-all ${
                        isHeldOut
                          ? 'bg-[#38232c] border-[#f28d95]/50 text-[#f28d95]'
                          : 'bg-[#15352e]/60 border-[#55dbb1]/30 text-[#55dbb1]'
                      }`}
                      title={
                        isHeldOut
                          ? 'Held-out square: NEVER place a brick here during training!'
                          : 'Active training square: rotate brick orientation each cycle'
                      }
                    >
                      <span className="font-bold">
                        R{row}C{col}
                      </span>
                      <span className="text-[8px] uppercase">
                        {isHeldOut ? 'TEST ONLY' : 'TRAIN'}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Photo & Exam Bag Checklist */}
              <div className="space-y-2 text-[11px]">
                <div className="bg-[#0b0f14] border border-[#26313e] rounded-[5px] p-2">
                  <div className="text-[#edf2f7] font-semibold">Inspection Photos (Round 1)</div>
                  <div className="text-[#8e9bae] text-[10px] mt-0.5">
                    • <strong>~150 unmarked photos</strong> (every colour, turn wrist slowly)
                  </div>
                  <div className="text-[#8e9bae] text-[10px]">
                    • <strong>~40 marked photos</strong> (marker defects on ≥2 sides)
                  </div>
                </div>

                <div className="bg-[#0b0f14] border border-[#e9bf79]/30 rounded-[5px] p-2">
                  <div className="text-[#e9bf79] font-semibold flex items-center space-x-1">
                    <PackageCheck className="w-3.5 h-3.5" />
                    <span>Sealed EXAM Bag</span>
                  </div>
                  <div className="text-[#8e9bae] text-[10px] mt-0.5">
                    <strong>5 unmarked + 5 marked</strong> bricks. Leave closed until the Inspection agent asks for the final exam.
                  </div>
                </div>

                <div className="text-[10px] text-[#8e9bae]">
                  Held-out squares:{' '}
                  <span className="text-[#f28d95] font-mono font-semibold">
                    {heldOutSquares
                      .map((i) => `R${Math.floor(i / 3) + 1}C${(i % 3) + 1}`)
                      .join(', ') || 'None'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-3 pt-2 border-t border-[#26313e]/70 text-[10px] text-[#8e9bae]">
            <strong>Rule:</strong> Rest bricks lightly on the plate (do not press onto studs). Screenshot Studio’s dataset, training &amp; export screens!
          </div>
        </div>
      </div>

      {/* Middle Row: 6 Checkpoints Timetable & ~/duplo-cell 5-Tab Commands */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* 6 Checkpoints Timetable */}
        <div className="lg:col-span-7 bg-[#121922] border border-[#26313e] rounded-[8px] p-4">
          <div className="flex items-center justify-between pb-2.5 border-b border-[#26313e] mb-3">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-[#e9bf79]" />
              <h2 className="text-[15px] font-semibold text-[#edf2f7]">
                Saturday → Sunday Timetable (Helsinki Time)
              </h2>
            </div>
            <span className="text-[10px] text-[#8e9bae]">
              Deadline: Sun 10:00 (Submit by 09:00)
            </span>
          </div>

          <div className="space-y-2">
            {TIMETABLE.map((item) => {
              const done = !!completedCheckpoints[item.id];
              return (
                <div
                  key={item.id}
                  className={`p-2.5 rounded-[6px] border transition-colors ${
                    done
                      ? 'bg-[#15352e]/25 border-[#55dbb1]/30'
                      : 'bg-[#0b0f14] border-[#26313e]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div
                      onClick={() => toggleCheckpoint(item.id)}
                      className="flex items-start space-x-2.5 cursor-pointer flex-1"
                    >
                      <CheckCircle2
                        className={`w-4 h-4 mt-0.5 shrink-0 ${
                          done ? 'text-[#55dbb1]' : 'text-[#8e9bae]/50'
                        }`}
                      />
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="text-[11px] font-mono font-bold text-[#edf2f7]">
                            {item.time}
                          </span>
                          {done && (
                            <span className="text-[9px] bg-[#15352e] text-[#55dbb1] px-1.5 py-0.2 rounded">
                              DONE
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-[#b5c0ce] mt-0.5">
                          {item.goal}
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => copyText(item.fallback, `fb-${item.id}`)}
                      className="px-2 py-1 rounded bg-[#18212c] hover:bg-[#26313e] text-[#e9bf79] text-[9.5px] font-medium flex items-center space-x-1 shrink-0"
                      title={`If missed: "${item.fallback}"`}
                    >
                      {copiedKey === `fb-${item.id}` ? (
                        <Check className="w-3 h-3 text-[#55dbb1]" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                      <span>If missed</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 5 Terminal Tabs & Agent Control Phrases */}
        <div className="lg:col-span-5 bg-[#121922] border border-[#26313e] rounded-[8px] p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-2.5 border-b border-[#26313e] mb-3">
              <div className="flex items-center space-x-2">
                <Terminal className="w-4 h-4 text-[#55dbb1]" />
                <h2 className="text-[15px] font-semibold text-[#edf2f7]">
                  ~/duplo-cell 5-Tab Setup &amp; Phrases
                </h2>
              </div>
              <span className="text-[10px] font-mono text-[#8e9bae]">
                Ubuntu Station
              </span>
            </div>

            {/* 5 Tabs summary */}
            <div className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-2.5 mb-3 text-[11px] space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[#8e9bae]">Tab 1 (Lead):</span>
                <button
                  onClick={() =>
                    copyText('mkdir -p ~/duplo-cell && cd ~/duplo-cell && claude', 'tab1')
                  }
                  className="font-mono text-[10px] text-[#55dbb1] hover:underline flex items-center space-x-1"
                >
                  <span>mkdir -p ~/duplo-cell &amp;&amp; cd ~/duplo-cell &amp;&amp; claude</span>
                  <Copy className="w-3 h-3" />
                </button>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[#8e9bae]">Tabs 2–4 (Policy, Inspection, Speed):</span>
                <button
                  onClick={() => copyText('cd ~/duplo-cell && claude', 'tab24')}
                  className="font-mono text-[10px] text-[#89b9ef] hover:underline flex items-center space-x-1"
                >
                  <span>cd ~/duplo-cell &amp;&amp; claude</span>
                  <Copy className="w-3 h-3" />
                </button>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[#8e9bae]">Tab 5 (Robot — NO Claude):</span>
                <button
                  onClick={() => copyText('cd ~/duplo-cell', 'tab5')}
                  className="font-mono text-[10px] text-[#e9bf79] hover:underline flex items-center space-x-1"
                >
                  <span>cd ~/duplo-cell (hold power, type GO)</span>
                  <Copy className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* Quick Copy Phrases */}
            <div className="space-y-1.5">
              {AGENT_PHRASES.map((p, idx) => (
                <div
                  key={idx}
                  className="bg-[#0b0f14] border border-[#26313e] rounded-[5px] px-2.5 py-1.5 flex items-center justify-between gap-2"
                >
                  <div className="min-w-0">
                    <div className="text-[10px] text-[#8e9bae]">
                      {p.label} <span className="text-[#55dbb1]">({p.target})</span>
                    </div>
                    <code className="text-[11px] text-[#edf2f7] font-mono truncate block">
                      {p.cmd}
                    </code>
                  </div>
                  <button
                    onClick={() => copyText(p.cmd, `phrase-${idx}`)}
                    className="px-2 py-1 rounded bg-[#18212c] hover:bg-[#26313e] text-[#b5c0ce] text-[10px] shrink-0"
                  >
                    {copiedKey === `phrase-${idx}` ? (
                      <Check className="w-3 h-3 text-[#55dbb1]" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Safety reminder */}
          <div className="mt-3 pt-2 border-t border-[#26313e]/70 flex items-center space-x-2 text-[10px] text-[#f28d95]">
            <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
            <span>
              <strong>Robot runs:</strong> Close Studio first if Lead says so. Hold power switch, type <code>GO</code>, press <code>Ctrl+C</code> or cut power if arm shakes.
            </span>
          </div>
        </div>
      </div>

      {/* Bottom Row: 4 Team Roles */}
      <div className="bg-[#121922] border border-[#26313e] rounded-[8px] p-4">
        <div className="flex items-center space-x-2 pb-2.5 border-b border-[#26313e] mb-3">
          <Users className="w-4 h-4 text-[#c4a7ea]" />
          <h2 className="text-[15px] font-semibold text-[#edf2f7]">
            Who Does What (Swap Roles When Someone Sleeps)
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {ROLES.map((r) => (
            <div
              key={r.role}
              className="bg-[#0b0f14] border border-[#26313e] rounded-[6px] p-3"
            >
              <div className="text-[12px] font-semibold text-[#55dbb1] mb-1">
                {r.role}
              </div>
              <div className="text-[11px] text-[#8e9bae] leading-relaxed">
                {r.desc}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
