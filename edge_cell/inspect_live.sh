#!/usr/bin/env bash
# Live defect verdict from the inspect camera. Does not move the robot. Ctrl+C to stop.
cd "$(dirname "$0")" && exec /home/intel/physical-ai-studio/application/backend/.venv/bin/python -m inspection.live
