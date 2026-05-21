#!/usr/bin/env bash
# Run all OAfastWP autotest phases in order:
#   Phase 0 -> P0-01..22 upstream regression gate
#   Phase 1 -> SITL-01..23
#   Phase 2 -> SITL-14, 17, 23, 29, 32
#   Phase 3 -> SITL-25..31
#
# Usage:
#   ./Tools/autotest/run_oafastwp_all.sh
#   ./Tools/autotest/run_oafastwp_all.sh --skip-build

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

ARGS=()
[[ "${SKIP_BUILD}" -eq 1 ]] && ARGS+=(--skip-build)

"${SCRIPT_DIR}/run_oafastwp_phase0.sh" "${ARGS[@]}"
"${SCRIPT_DIR}/run_oafastwp_phase1.sh" --skip-build
"${SCRIPT_DIR}/run_oafastwp_phase2.sh" --skip-build
"${SCRIPT_DIR}/run_oafastwp_phase3.sh" --skip-build

echo "=== OAfastWP all phases complete ==="
