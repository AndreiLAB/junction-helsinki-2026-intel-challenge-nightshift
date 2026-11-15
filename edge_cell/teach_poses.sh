#!/usr/bin/env bash
# Save arm positions by moving the CONTROLLER arm by hand. Reads only; nothing moves by itself.
cd "$(dirname "$0")" && exec /home/intel/physical-ai-studio/application/backend/.venv/bin/python -m cell.teach "$@"
