#!/usr/bin/env bash
# Phase 1: SITL-01..23 fastWP + Dijkstra regression (copter, unattended).
#
# Usage (from repo root):
#   ./Tools/autotest/run_oafastwp_phase1.sh
#   ./Tools/autotest/run_oafastwp_phase1.sh --skip-build
#
# Run a single subtest:
#   ./Tools/autotest/autotest.py test.CopterTestsOAfastWPPhase1.SITL_02_CircleExclusionMission

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

SKIP_BUILD=0
for arg in "$@"; do
    case "${arg}" in
        --skip-build) SKIP_BUILD=1 ;;
        -h|--help)
            echo "Usage: $0 [--skip-build]"
            exit 0
            ;;
        *)
            echo "Unknown argument: ${arg}" >&2
            exit 1
            ;;
    esac
done

if [[ "${SKIP_BUILD}" -eq 0 ]]; then
    echo "=== Building ArduCopter SITL ==="
    ./Tools/autotest/autotest.py build.Copter
fi

echo "=== Running OAfastWP Phase 1 autotests (SITL-01..23) ==="
./Tools/autotest/autotest.py test.CopterTestsOAfastWPPhase1

echo "=== Generating Phase 1 evidence report ==="
python3 "${SCRIPT_DIR}/generate_oafastwp_phase1_report.py"

echo "=== Generating Phase 1 visual validation dashboard ==="
python3 "${SCRIPT_DIR}/generate_oafastwp_visual_evidence.py" --phase 1

echo "=== Updating spreadsheet (Phase 1) ==="
python3 "${SCRIPT_DIR}/update_fence_escape_spreadsheet.py" --phase 1

echo "=== OAfastWP Phase 1: ALL PASSED ==="
