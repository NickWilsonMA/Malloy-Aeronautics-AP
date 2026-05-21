#!/usr/bin/env bash
# Start (or restart) a firmware SITL validation campaign.
#
# Derives the campaign name from:
#   - ArduCopter/version.h  (e.g. 4.3.0.16 from THISFIRMWARE V4.3.0.16-...)
#   - current git branch    (e.g. oa-fastWP-fenceEscapeVector)
#
# Campaign folder + spreadsheet: docs/<version>-<branch>/
#
# Usage (from repo root):
#   git checkout oa-fastWP-fenceEscapeVector    # feature branch under test
#   # update ArduCopter/version.h first
#   ./Tools/autotest/reset_firmware_SITL_validation_campaign.sh
#
# Optional: --force  allow reset on main/master (not recommended)

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
echo "Reading: ArduCopter/version.h + git branch"
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
