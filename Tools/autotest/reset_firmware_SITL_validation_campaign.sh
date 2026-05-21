#!/usr/bin/env bash
# Start (or restart) a firmware SITL validation campaign.
#
# Campaign name comes entirely from ArduCopter/version.h THISFIRMWARE, e.g.:
#   MA_COPTER-V4.3.0.16-OA-fastWP-fenceEscapeVector
#
# Creates:
#   docs/MA_COPTER-V4.3.0.16-OA-fastWP-fenceEscapeVector/
#   └── MA_COPTER-V4.3.0.16-OA-fastWP-fenceEscapeVector.xlsx  (+ Phase 0 template)
#
# Prerequisites:
#   - Feature branch checked out (suffix must match THISFIRMWARE after the build number)
#   - THISFIRMWARE build number incremented for this firmware update
#
# Usage (from repo root):
#   ./Tools/autotest/reset_firmware_SITL_validation_campaign.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

CAMPAIGN_PY="${SCRIPT_DIR}/firmware_SITL_validation_campaign.py"
FORCE=0
for arg in "$@"; do
    case "${arg}" in
        --force) FORCE=1 ;;
        *)
            echo "Usage: $0 [--force]" >&2
            exit 1
            ;;
    esac
done

echo "=== Preparing firmware SITL validation campaign ==="
echo "Reading THISFIRMWARE from ArduCopter/version.h"
echo ""

PREPARE_ARGS=()
if [[ "${FORCE}" -eq 1 ]]; then
    PREPARE_ARGS+=(--force)
fi
if ! python3 "${CAMPAIGN_PY}" prepare "${PREPARE_ARGS[@]}"; then
    echo ""
    echo "Reset aborted. Fix version.h and/or git branch, then re-run." >&2
    exit 1
fi

CAMPAIGN_ID="$(python3 "${CAMPAIGN_PY}" campaign_id)"
ROOT="$(python3 "${CAMPAIGN_PY}" root)"

echo ""
echo "=== Resetting campaign evidence ==="
echo "Campaign: ${CAMPAIGN_ID}"
echo "Removing: ${ROOT}"
rm -rf "${ROOT}"

LEGACY_XLSX="${REPO_ROOT}/docs/${CAMPAIGN_ID}.xlsx"
if [[ -f "${LEGACY_XLSX}" ]]; then
    echo "Removing legacy spreadsheet: ${LEGACY_XLSX}"
    rm -f "${LEGACY_XLSX}"
fi

LEGACY_LOGS="${REPO_ROOT}/../buildlogs"
if [[ -d "${LEGACY_LOGS}" ]]; then
    echo "Removing legacy buildlogs: ${LEGACY_LOGS}"
    rm -rf "${LEGACY_LOGS}"
fi

echo ""
"${SCRIPT_DIR}/init_firmware_SITL_validation_campaign.sh"
