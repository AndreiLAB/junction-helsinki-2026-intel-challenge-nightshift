"""Pure-software: derive the iceoryx2 service name Studio's SharedCamera publishes on,
and list live physicalai camera services (no camera device is opened)."""
import ctypes
from physicalai.capture.transport._spec import derive_service_name
for cfg in [
    {"class_path": "physicalai.capture.UVCCamera", "init_args": {"device": {"index": 0}}},
    {"class_path": "physicalai.capture.UVCCamera", "init_args": {"device": "/dev/null"}},
    {"class_path": "physicalai.capture.RealSenseCamera", "init_args": {"serial_number": "123456"}},
]:
    print(cfg["init_args"], "->", derive_service_name(cfg))
import iceoryx2 as iox2
try:
    svcs = [str(s.name()) for s in iox2.Service.list(iox2.config.global_config(), iox2.ServiceType.Ipc)]
    print("live services:", svcs)
except Exception as e:
    print("list failed:", type(e).__name__, e)
