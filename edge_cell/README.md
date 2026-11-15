# Duplo Inspection Cell

An SO-101 robot arm picks a Duplo brick, shows it to an inspection camera and drops it in the **good**
or the **defective** bowl, with no human touch. Learned policies move the arm, an Anomalib model judges the
brick, and every model runs with **OpenVINO on one Intel Core Ultra laptop**, using the **CPU, GPU and NPU**
for different jobs.

Built at Junction 2026 for the Intel Physical AI challenge.

## How it works

```
 top / wrist / inspect cameras ──► Physical AI Studio camera service (shared frames)
                                          │
        ┌─────────────────────────────────┼──────────────────────────────────┐
        ▼                                 ▼                                  ▼
  ACT v2 (OpenVINO, GPU)        PatchCore (Anomalib, OpenVINO, NPU)   SmolVLA (OpenVINO, GPU)
  "pick a brick and show it"    good / defective score                "put in the good bowl"
        │                                 │                           "put in the defective bowl"
        └──────────────► state machine + safety filter (CPU, 30 Hz) ◄────────────┘
                                          │
                                     SO-101 follower arm
```

One brick, start to finish:

1. **HOME**: scripted move to the rest pose.
2. **PICK_PRESENT** (learned, ACT): grasp a brick from the blue bowl and bring it to the inspection camera.
   ACT re-plans from fresh camera images every second. If it misses, it keeps trying.
3. **CHECK_HELD** (CPU): compare the inspection picture with an empty-gripper reference. If the gripper is empty, pick again.
4. **INSPECT** (NPU): PatchCore anomaly score. The verdict rule is: score < 0.45 GOOD, > 0.60 DEFECTIVE, in between
   UNCERTAIN (treated as defective, so it never passes a doubtful brick).
5. **PLACE_GOOD / PLACE_DEFECT** (learned, SmolVLA): **one** model, steered only by the text instruction.
6. **Release**: hold, open the gripper wide, then a scripted move home (up, across, down).

**Learned:** grasping and presenting the brick (ACT), and carrying it to the bowl the instruction names (SmolVLA).
**Scripted:** the home move, the short final move to the inspection pose, the release and the return home.

## Chip split (OpenVINO, measured on this laptop)

| Job | Model | CPU | GPU | NPU | Runs on |
|---|---|---|---|---|---|
| Pick policy, one 100-step plan | ACT v2 | – | **12 ms** | – | GPU |
| Place policy, one 50-step plan | SmolVLA (450M) | 2325 ms | **104 ms** | – | GPU |
| Defect check, one image | PatchCore | 245 ms | 24 ms | **181 ms** | NPU |
| State machine, safety, brick-held check | – | **every tick (30 Hz)** | – | – | CPU |

- The **GPU** runs the policies. They predict several times a second, and SmolVLA is 22× faster there than on the CPU.
- The **NPU** runs the defect check once per brick. 0.18 s is fast enough, it gives the same scores as the GPU,
  and it leaves the GPU free for the policies.
- The **CPU** runs the control loop and safety checks, which must never wait for a model.

Hardware: Intel Core Ultra X9 388H, Intel Arc integrated GPU, Intel AI Boost NPU, OpenVINO 2026.4.

## Results (real robot)

- **Full sorting run, one brick after another, no human touch (on video):** 4 of 4 bricks sorted into the right
  bowl, 2 good and 2 defective.

  | Brick | Pick | Defect score (NPU) | Verdict → bowl | Place |
  |---|---|---|---|---|
  | 1 | 18.0 s | 0.32 | GOOD → green | 3.9 s |
  | 2 | 12.7 s | 0.81 | DEFECTIVE → pink | 4.5 s |
  | 3 | 18.0 s | 0.05 | GOOD → green | 4.7 s |
  | 4 | – | 0.76 | DEFECTIVE → pink | 4.4 s |

  A whole brick (pick, inspect, place, return home) takes about **30–34 s**.
  The good and defective scores are far apart: good bricks scored 0.05–0.32 (GOOD below 0.45), and defective
  bricks scored 0.76–0.85 (DEFECTIVE above 0.60).
- **Placing (SmolVLA):** 3/3 into the right bowl in a separate test with a handed brick. The same picture with a
  different instruction sends the arm to the other bowl.
- **Picking with SmolVLA:** 0/4. It reached for the bowl rim. That's why picking uses ACT, which re-plans from
  fresh images every second.

Every run writes `runs/<id>/events.jsonl`; robot trials are logged in `reports/trials.md`.

## Data and training

- 154 teleoperated demonstrations recorded in **Intel Physical AI Studio** (SO-101 leader/follower, 3 cameras):
  94 pick-and-show, 30 place-good, 30 place-defective. Some pick demos deliberately include a miss and a re-grasp.
- Policies were trained in Studio on Modal GPUs and exported to OpenVINO by Studio:
  ACT v2 (10 epochs, batch 64, image augmentation) and SmolVLA (fine-tuned from `lerobot/smolvla_base`).
- PatchCore (Anomalib 2.7) was trained on inspection-camera frames of good bricks taken from the demos.
  Defective bricks carry white tape with a blue X.

## Run it

Needs Physical AI Studio running (it shares the camera frames) and not driving the arm itself.

```bash
./start_demo.sh 5 --one-by-one        # sort 5 bricks; before each one it asks you to put a brick in the blue bowl
./start_demo.sh 5                     # sort 5 bricks already in the blue bowl
./robot_test.sh skill pick_present    # one learned skill
./robot_test.sh skill place_good --handed   # placing test: you hand it a brick at the camera
./inspect_live.sh                     # live defect check on the inspection camera
./teach_poses.sh                      # teach home / inspect / travel poses by teleoperation
python -m cell.run --mock             # whole state machine with a fake arm, fake cameras and a fake inspector
```

Every robot program waits for you to type `GO`, starts slowly, and holds position on `Ctrl+C`.
Every command passes through a safety filter: joint limits, a speed limit, and a stop on stale camera frames or invalid actions.

## Layout

| Folder | What |
|---|---|
| `cell/` | state machine, motion routing, safety filter, policy runner, real-robot program, pose teaching |
| `inspection/` | Anomalib training, frame extraction, OpenVINO inspector service, live viewer |
| `common/` | config loading, event log |
| `configs/` | station config (ports, cameras, poses, limits, models), calibrations, reference images |
| `tests/` | unit tests (state machine, safety, inspector, dry run with fakes) and replay checks for policies |
| `reports/` | benchmarks (`reports/bench/*.json`) and the trial log |
