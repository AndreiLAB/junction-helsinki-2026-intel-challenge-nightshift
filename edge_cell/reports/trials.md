# Robot trials. Evidence: REAL unless marked.

| when (Helsinki) | policy | skill / mode | result | time | notes |
|---|---|---|---|---|---|
| Sat 18:50 | ACT quick (10 eps) via Studio Run model | pick_present | success | - | "clumsy but did it" (team) |
| Sat 21:51 | - | poses tour (scripted) | ok after up-sideways-down routing | - | first try hit camera/bowl with direct moves |
| Sat 22:01 | - | photo session (3 good) | tilted views unusable | - | finger covers brick; max_views=1 |
| Sat ~22:15 | ACT quick, our runner, OpenVINO CPU | pick_present | success, but done-check missed (timeout 25 s) | 25 s | fixed done check |
| Sat ~22:25 | ACT quick, our runner, OpenVINO CPU | pick_present | success, done detected | 11.6 s | infer p50 159 ms p95 171 ms (4 chunks); brick_held diff 50.6 (thr 12); Anomalib 0.32 GOOD |

## SmolVLA v1 pick_present, try 1 (REAL, run 20261114-142928) — FAIL (missed brick)
- Went toward the plate, opened, closed at ~5 s with arm too HIGH: elbow 13 / wrist_flex 70 / roll 33 vs demo grasp median elbow 34 / wrist_flex 56 / roll 66. Gripper closed to 6 (empty). Then went to inspect (dist 12) on its own in 10.9 s.
- 142 of ~330 ticks rate-limited at policy_speed 1.0 (elbow limit 2.5/tick; demos reach 3-4/tick). Likely cause: arm lagged behind the policy, closed before reaching the brick.
- Next: retry with --policy-speed 1.5 (limits 3.75-7.5/tick, matches demo speed). GPU inference p50 139 ms.

## SmolVLA v1 pick_present, try 2 (REAL, Studio "Run model" on GPU, no speed limit of ours) — FAIL (closed near the brick)
- So the miss is not only our speed limit. Next: our runner with --horizon 15 (re-plan from a fresh picture every ~0.15 s instead of playing 1.4 s blind) and --policy-speed 1.5.

## SmolVLA v1 pick_present, try 3 (REAL, run 20261114-144714, --horizon 15 --policy-speed 1.5) — FAIL (never opened gripper)
- Went over the plate, never opened (gripper 2-5), drifted to inspect in 7 s. Re-planning every ~0.13 s made it worse.
- Suspect live inputs differ from training (replay on recorded frames looks fine). Added: skill runs save model inputs to runs/<id>/policy_inputs/*.npz for offline comparison.

## SmolVLA v1 pick_present, try 4 (REAL, run 20261114-145010, --policy-speed 1.5) — FAIL (timeout 20 s)
- Team: "almost always wants to grab the bowl by the edge". Also misses in Studio "Run model" on GPU.
- Live model inputs (runs/.../policy_inputs) match training pictures: same camera placement, similar light, RGB order OK. So the input pipeline is not the cause.
- Training: 2499 steps (auto-scaled batch ~250, 20 epochs), train loss 0.030 vs val loss 0.094 (held-out episodes): memorised the demos, does not generalise to new brick positions. Only 57 pick demos.
- Next: test place on its own (--handed), and retrain SmolVLA from v1 with "Augment images" for more epochs.

## SmolVLA v1 place, handed brick (REAL, --handed) — PASS 3/3
- place_good x2 (runs 20261114-145945, -150047): green bowl, done in 3.8 s / 3.3 s.
- place_defect x1 (run 20261114-150251): pink bowl, done in 4.1 s. GPU inference p50 ~152 ms.
- Same model, only the text changed: the instruction picks the bowl on the real robot.

## ACT v2 pick_present x3 (REAL, runs 20261114-181153/-181305/-181440, --pick-model act_v2 --policy-speed 1.5) — 1/3 (team; a 2nd picked but dropped it midway)
- All three hit the 20 s timeout; ACT retries after a miss (gripper opens again), which takes longer. Pick timeout raised to 30 s.
- Whole 100-action chunks (3.3 s) run blind; ACT is deterministic and 12 ms, so next try --horizon 30 (re-plan every second).
- SmolVLA v2 ready: val loss 0.168 (train 0.043), GPU 103 ms, task steering intact (pan shift +7..+32 / -8..-31).

## ACT v2 pick, --horizon 30 --policy-speed 1.5 (REAL) — team: 2.5/3
- runs 20261114-181840 done 12.8 s, -181949 done 11.7 s, -182107 timeout 30 s (with 3 bricks it hesitated between them until they were shuffled).
- SmolVLA v2 pick: team "bad" (worse than ACT). Decision: ACT v2 picks (horizon 30), SmolVLA v1 places.

## Full loop, 1 brick (REAL, ACT v2 pick + SmolVLA v1 place, horizon 30, policy speed 1.5)
- run 20261114-183321: defect brick, score 0.76 -> DEFECT -> pink bowl, run_end DONE. Team: full cycle works.
- run 20261114-183433: good brick 0.33 -> GOOD (NPU), place_good entered; pick took the full 30 s timeout first.
- Bricks already in the GREEN bowl make it fumble (pick demos always had it empty). Procedure: empty the green bowl between runs.
- These settings are now the defaults in configs/station.yaml: ./start_demo.sh N needs no extra options.

## One-by-one run, 5 bricks (REAL, run 20261114-193941) — ruined at brick 2
- Brick 1 good (0.12) -> green OK. Brick 2 defect (0.85) -> place_defect "done" after 4.5 s (gripper opened >10 = only partly; demos open ~15) and the home move (gripper -> 2) took over before the brick was out.
- Fix: place_done needs open >12 and >=3 s; then a RELEASE step: hold position, open gripper to 40 for 1 s; the home route keeps it open until the last downward step.

## RECORDED RUN (video): one-by-one, run 20261114-195437 (REAL) — 4/4 sorted, 0 human touches of the arm
| brick | pick s | score (NPU) | verdict | place s | brick total s |
|---|---|---|---|---|---|
| 1 | 18.0 | 0.32 | GOOD -> green | 3.9 | 49.9 (incl. first home) |
| 2 | 12.7 | 0.81 | DEFECT -> pink | 4.5 | 29.8 |
| 3 | 18.0 | 0.05 | GOOD -> green | 4.7 | 33.8 |
| 4 | – | 0.76 | DEFECT -> pink | 4.4 | – |
- Picks 12.7-18.0 s, places 3.9-4.7 s, 29.8-33.8 s per brick (bricks 2-3).
- Stopped (Ctrl+C) at home before brick 5. Verdicts all correct (team). Inspector latency on NPU in the loop 278-462 ms (incl. pre/post-processing).

## Earlier one-by-one run 20261114-195840 (REAL): bricks 1-2 DEFECT 0.85 / 0.81 -> pink OK; stopped during brick 3 pick.
