#!/usr/bin/env bash
# Robot tests. Run ONLY in the Robot tab, with Studio OFF its recording / run screens.
#   ./robot_test.sh poses                  slow tour of the saved positions (no brick in the gripper)
#   ./robot_test.sh skill pick_present     one learned skill (also place_good, place_defect)
# Waits for GO. Ctrl+C stops; the arm holds its position.
cd "$(dirname "$0")" && exec /home/intel/physical-ai-studio/application/backend/.venv/bin/python -m cell.robot "$@"
