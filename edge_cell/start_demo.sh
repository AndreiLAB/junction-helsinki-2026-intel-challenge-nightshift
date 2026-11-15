#!/usr/bin/env bash
# Full sorting run:  ./start_demo.sh 5   (number of bricks). Robot tab only. Waits for GO. Ctrl+C stops.
cd "$(dirname "$0")" && exec /home/intel/physical-ai-studio/application/backend/.venv/bin/python -m cell.robot run "${1:-5}" "${@:2}"
