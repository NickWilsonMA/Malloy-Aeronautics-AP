#!/usr/bin/env bash
# Add a phase worksheet + folder layout to an existing campaign spreadsheet.
#
# Usage:
#   ./Tools/autotest/add_firmware_SITL_validation_phase.sh 1
#   ./Tools/autotest/add_firmware_SITL_validation_phase.sh 2
#   ./Tools/autotest/add_firmware_SITL_validation_phase.sh 3

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

PHASE="${1:-}"
if [[ ! "${PHASE}" =~ ^[1-3]$ ]]; then
    echo "Usage: $0 <1|2|3>" >&2
    exit 1
fi

CAMPAIGN_PY="${SCRIPT_DIR}/firmware_SITL_validation_campaign.py"
XLSX="$(python3 "${CAMPAIGN_PY}" spreadsheet)"
if [[ ! -f "${XLSX}" ]]; then
    echo "Campaign not initialized. Run ./Tools/autotest/reset_firmware_SITL_validation_campaign.sh first." >&2
    exit 1
fi

python3 -c "
import sys
sys.path.insert(0, '${SCRIPT_DIR}')
import firmware_SITL_validation_campaign as c
import oafastwp_spreadsheet_data as s
c.ensure_phase_dirs(${PHASE})
path = s.add_phases_to_spreadsheet(c.spreadsheet_path(), (${PHASE},))
print('Added phase ${PHASE} tab:', path)
"

echo "Phase ${PHASE} folders:"
echo "  logs: $(python3 "${CAMPAIGN_PY}" buildlogs "${PHASE}")"
echo ""
echo "Next:"
echo "  ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh ${PHASE}"
echo "  ./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh ${PHASE}"
