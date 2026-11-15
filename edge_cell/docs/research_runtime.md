# physicalai runtime research (read-only, 2026-11-14)

Paths: `SP` = `/home/intel/physical-ai-studio/application/backend/.venv/lib/python3.13/site-packages`,
`LIB` = `/home/intel/physical-ai-studio/library/src/physicalai`, `BE` = `/home/intel/physical-ai-studio/application/backend/src`.
Probes: `/home/intel/duplo-cell/tests/probe_*.py`. None of them touch hardware.

## 1. Versions and devices (`tests/probe_versions.py`, ran it)
| pkg | version |
|---|---|
| physicalai (runtime) | 0.4.1.dev5+g8381d43 (namespace pkg: venv site-packages + `library/src/physicalai`) |
| physicalai-train / -studio / -so101-plugin | 0.3.0 / 0.3.0 / 0.3.0 |
| openvino / openvino-tokenizers | 2026.4.1 / 2026.4.1.0 |
| torch | 2.11.0+xpu (lerobot 0.6.0, transformers 5.15.1) |

**`ov.Core().available_devices == ['CPU']` only** (`CPU -> Intel(R) Core(TM) Ultra X9 388H`), and that holds with and without the sandbox.
- GPU: `[GPU] Can't get FULL_DEVICE_NAME ... no supported devices found`. NPU: the plugin loads but finds no device.
  `torch.xpu.is_available() == False` ("XPU device count is zero").
- `/dev/dri/renderD128` and `/dev/accel/accel0` exist and user `intel` is in `render`/`video`. But the Intel compute
  runtime userspace is missing: there is no `/etc/OpenCL/vendors`, no `libze_loader`/`libze_intel_gpu`, and no NPU UMD in `ldconfig`.
  **Getting GPU/NPU working needs the driver packages installed (intel-opencl-icd, libze1/level-zero, intel-level-zero-npu, ...), which needs sudo.
  Ask the organisers.** Until then `device="GPU"` fails at compile time (`adapters/openvino.py:90`).

## 2. Loading a Studio OpenVINO export
- Studio writes exports to `<model.path>/exports/<backend>/` (`BE/runtime_session/model.py:92`) and loads them with
  `InferenceModel(export_dir, backend=..., device=...)` (`BE/workers/model_worker.py:114`).
- Constructor: `SP/physicalai/inference/model.py:99-110`, i.e. `InferenceModel(export_dir, policy_name=None, backend="auto", device="auto", runner=None, preprocessors=None, postprocessors=None, callbacks=None, **adapter_kwargs)`.
  `device="auto"` resolves to `"CPU"` (`adapters/openvino.py:165-171`). Pass `device="GPU"`/`"NPU"`/`"AUTO"` explicitly.
  `**adapter_kwargs` go to the OpenVINO `compile_model` config (`openvino.py:69-76`, `_compile_config` at :27).
  `InferenceModel.from_pretrained(repo_or_dir)` also works (:231).
- API:
  - `__call__(inputs)` runs callbacks, then preprocessors, then filters inputs to the adapter's names, then the runner, then postprocessors, and returns a dict (:290-325).
  - `predict_action_chunk(obs)` returns `(chunk, action_dim)` with the batch dimension stripped (:348-373).
  - `select_action(obs)` buffers the chunk and pops one `(action_dim,)` per call. It only runs inference again when the buffer is empty (:327-346).
  - `reset()` (:375) and `close()`/context manager (:396).
- **Observation keys are NOT `observation.images.*`.** They are built in `PolicySource._to_model_input` (`SP/physicalai/runtime/action_sources/policy.py:203-226`):
  - `"state"`: `float32 (1, 6)`
  - `"images.<cam>"`: `(1, H, W, 3) uint8 RGB` when there are 2 or more cameras, or a single `"images"` key when there is 1 camera
  - `"task"`: `[str]`, a list of strings
  - Camera names must match training names. Order is fixed automatically (`model.py:44-56, 440-474`).
- Image preprocessing is inside the manifest pipeline, so feed raw uint8 HWC:
  - ACT: `to_float_tensor` (/255, HWC to CHW), then `resize` letterbox to `config.image_size` (`LIB/policies/act/policy.py:711-719`).
  - SmolVLA: `smolvla_resize` (pad-resize to 512x512, scale to [-1,1], camera masks), then `new_line`, then `normalize` state mean_std (`LIB/policies/smolvla/policy.py:911-925`; `SP/.../preprocessors/smolvla.py:86-174`).
  - Actions are denormalised by a postprocessor, so the output is in robot units (normalized −100..100).
- Output: `action` with shape `(chunk_size, action_dim)`. Defaults are ACT chunk 100 / n_action_steps 100 and SmolVLA 50/50. If n_action_steps < chunk, `action_chunk_trimmer` trims the chunk (`smolvla/policy.py:934-940`).
- **No exported model exists on disk.** `~/.local/share/physicalai/models` is empty, there is no HF cache, and the only `manifest.json` hits are plugin manifests. Latency was therefore not measured.
  `tests/probe_inference.py <export_dir> [CPU|GPU|NPU] [task]` is ready. It builds zero inputs from `m.input_features` and prints chunk shape plus median/p90 ms.

## 3. SmolVLA text instruction: YES, a runtime string, and it can change per call
- The export declares an input feature `task` with `LANGUAGE`, `STRING`, shape `(tokenizer_max_length=48,)` (`LIB/policies/smolvla/policy.py:807-814`).
- The OpenVINO export sets `export_tokenizer=True`. That converts the HF tokenizer with `openvino_tokenizers` and saves **`tokenizer.xml`** in the export dir (`LIB/export/mixin_policy.py:540-549`). It also adds the preprocessor `ComponentSpec(type="ov_tokenizer", artifact="tokenizer.xml")` (`smolvla/policy.py:959-972`).
- At runtime `OVTokenizer` (`SP/.../preprocessors/ov_tokenizer.py:38-70`) runs on **CPU** only. It pops `inputs["task"]`, which must be a `list[str]`, and produces the model inputs `tokenized_prompt` and `tokenized_prompt_mask`. `new_line` appends `"\n"` first.
- The ONNX export instead uses `hf_tokenizer`, which downloads `vlm_model_name` at a pinned revision from the HF Hub on load (`smolvla/policy.py:949-954`, `hf_tokenizer.py:49-56`). That needs a network connection or the HF cache.
- **One exported SmolVLA therefore accepts any task string on every inference.** Prompts are truncated at 48 tokens. Example: `m({"state":..., "images.top":..., "task":["put the defective brick in the red bin"]})`.
  In a runtime loop, call `PolicySource.set_task(str)` (`policy.py:61-64`). It only takes effect at the next inference request; queued actions from the old chunk still play first unless you call `source.reset()` (:95).
  Caveat: whether the policy *obeys* different instructions depends on the training data (each episode's task string). ACT has no `task` input. Extra keys are silently dropped (`model.py:496-525`).

## 4. Robot runtime: running your own loop without Studio
Studio wraps `physicalai.runtime.PolicySource` inside `RobotRuntime`-style controls (`BE/runtime_session/controls/model.py:7,57`). The public API is in `SP/physicalai/runtime/__init__.py`.
- `RobotRuntime(robot, action_source, fps, cameras=None, callbacks=(), interpolator=None)` (`runtime/core.py:152-160`). Methods: `.connect()`, `.run(duration_s=None, stop_event=None, return_to_initial_state=False)` (:360), `.stop()` (:345), `.disconnect()`.
  Each cycle reads the robot and cameras, calls `action_source.update(...)`, runs `on_action_ready`, sends, runs `on_action_sent`, then `on_tick(TickEvent)` (`_tick` :458-503).
- **(b) Your own action source** is the `ActionSource` protocol (`runtime/action_sources/base.py:20-55`). It needs `connect(*, bus, session_id)`, `update(robot_state, camera_frames, step) -> np.ndarray(6,)` and `disconnect()`.
  The built-in `PolicySource(model, execution=SyncExecution()|AsyncExecution(), action_queue=ChunkedActionQueue(...), task=...)` wraps an `InferenceModel`.
- **(c) Per-action callback**: any object in `callbacks=`. `on_action_ready(*, action, step) -> action` can transform the action, e.g. as a safety clamp; an exception there ends the run. `on_action_sent(*, action, step)` is notify-only. `on_tick/on_inference/on_lifecycle/on_metrics` are duck-typed (`core.py:102-128`).
  Built-in callbacks: `ConsoleCallback`, `JsonlCallback`, `RerunCallback`, `LowPassFilterCallback`, `AsyncCallback`.
- **(a) Opening hardware directly**:
  - Robot: `from physicalai.robot.so101 import SO101`, then `SO101(port="/dev/ttyACM0", calibration="<calib.json>", role="follower", unit="normalized")`. The class is forwarded to `physicalai_so101_plugin/so101.py:101-136`. Calibration is required for normalized/degrees. Studio keeps it in its DB (robot payload) or a calibration dir, so export or copy the LeRobot calibration JSON.
  - Cameras: `physicalai.capture.UVCCamera(device=...)`, or better `SharedCamera` (see section 6).
- **Verified with a fake robot** (`tests/probe_runtime_fake.py`, ran it): `steps 15 reason duration_elapsed ready/sent/tick 15 15 15` at 30 fps for 0.5 s.
- Sketch:
```python
from physicalai.robot.so101 import SO101
from physicalai.capture import SharedCamera
from physicalai.runtime import RobotRuntime, PolicySource, AsyncExecution
from physicalai.inference import InferenceModel
robot = SO101(port="/dev/ttyACM0", calibration="follower.json", role="follower", unit="normalized")
cams = {"top": SharedCamera.from_publisher("physicalai/camera/UVCCamera/8/frame")}   # names = training names
class MySource:                     # or PolicySource(InferenceModel(dir, device="CPU"), task="...")
    def connect(self, *, bus, session_id): ...
    def update(self, robot_state, camera_frames, step): return next_action_6()  # np.float32 (6,)
    def disconnect(self): ...
class Safety:
    def on_action_ready(self, *, action, step): return clamp(action)
    def on_action_sent(self, *, action, step): log(action)
rt = RobotRuntime(robot, MySource(), fps=30, cameras=cams, callbacks=[Safety()])
with rt: rt.run(duration_s=20, stop_event=my_threading_event, return_to_initial_state=True)
```

## 5. SO101 joints and units (`physicalai_so101_plugin`)
- Order (`constants.py:36-43`): `shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper`, giving `state`/`action` shape `(6,)`.
- `unit="normalized"` is the default (`so101.py:111-115,135`):
  - Body joints run from **−100 to 100**, linear between the calibrated `range_min` and `range_max`, and clipped.
  - The **gripper runs from 0 to 100** (`_conversion.py:18-37`).
- `unit="degrees"`: body joints are in degrees relative to the calibrated range midpoint and are not clipped. The gripper stays at 0..100 (`_conversion.py:41-63`).
- Uncalibrated mode allows only raw `ticks` (0..4095).
- API:
  - `connect()` (:357) and `disconnect()` (:457). The follower enables torque on connect.
  - `get_observation().state`, or `.joint_positions` (:487-519).
  - `send_action(np.ndarray(6,), goal_time=0.1)` (:521-545). It raises on the leader arm and on a wrong shape.
  - `max_speed`, `joint_names`, `is_connected()`.

## 6. Device sharing with Studio
- **Cameras: Studio does not hold the V4L2 device in its own process.** `build_shared_camera` (`BE/utils/camera_factory.py:95-135`) creates a `SharedCamera`. That spawns a detached process, `python -m physicalai.capture.transport._publisher_worker` (`SP/physicalai/capture/transport/_publisher.py:79-87`). The publisher **owns the device exclusively** (`_shared_camera.py:1-15`) and publishes frames over **iceoryx2 shared memory**, with up to 32-64 subscribers.
  Service names are `physicalai/camera/<ClassName>/<device_id>/frame` (`_spec.py:160-206`).
  **Live right now: `physicalai/camera/UVCCamera/8/frame`** (`tests/probe_camera_services.py` lists the iceoryx2 services and only reads metadata).
  **Read Studio's frames without opening the device:** `cam = SharedCamera.from_publisher("physicalai/camera/UVCCamera/8/frame"); cam.connect(); f = cam.read_latest()` gives `Frame.data` as `(H,W,3)` uint8 RGB (`_shared_camera.py:221-256, 328-348`).
  Alternatively, `SharedCamera(camera=Config(...))` with the same config attaches to an existing publisher or spawns one. Opening `/dev/videoN` directly while the publisher streams normally fails, because the device is busy.
  Note: the publisher self-exits after `idle_timeout` (5 s) once it has no subscribers.
- **Serial (SO101): there is NO hard exclusivity.** `scservo_sdk` opens the port with plain `serial.Serial(...)` and no `exclusive=True` (`SP/scservo_sdk/port_handler.py:95-102`), and `SO101.connect()` takes no lock.
  Studio guards with an advisory `flock` (`claim_devices` / `acquire_locks`, `BE/workers/robot_worker.py:68-100`, `SP/physicalai/robot/transport/_lock.py`).
  **A second process opening the same `/dev/ttyACM*` will likely succeed silently. Both processes then share the half-duplex bus and get corrupted reads or a fight over the arm.** Disconnect Studio's robot (stop the session) before running your own loop. Optionally call `acquire_locks(name, robot.device_ids)` yourself so that Studio refuses with `robot_device_already_owned`.
- The cooperative alternative is `physicalai.robot.SharedRobot(name, robot=Config(...))` / `SharedRobot.attach(name)` over Zenoh (`robot/transport/_shared_robot.py:183`): one owner process, many clients.
  Studio's `RobotWorker` uses its own exclusive driver rather than a SharedRobot, so you cannot attach to Studio's arm. Use one owner, either your program or Studio.
