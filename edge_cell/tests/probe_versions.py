"""Pure-software probe: package versions + OpenVINO devices. No hardware I/O."""
import importlib.metadata as m
for p in ["physicalai", "physicalai-train", "physicalai-studio", "physicalai-so101-plugin", "openvino", "openvino-tokenizers", "torch", "lerobot", "transformers"]:
    try: print(f"{p:28s} {m.version(p)}")
    except Exception as e: print(p, "MISSING", e)
import openvino as ov
c = ov.Core()
print("openvino runtime:", ov.get_version())
for d in c.available_devices:
    print(d, "->", c.get_property(d, "FULL_DEVICE_NAME"))
