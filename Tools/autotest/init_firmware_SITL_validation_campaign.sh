#!/usr/bin/env bash
# Create docs/<THISFIRMWARE>/ layout + template spreadsheet (Intro + Phase 0 tab).
# Normally invoked by reset_firmware_SITL_validation_campaign.sh.
#
# Usage (from repo root):
#   ./Tools/autotest/init_firmware_SITL_validation_campaign.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

CAMPAIGN_PY="${SCRIPT_DIR}/firmware_SITL_validation_campaign.py"
if ! python3 "${CAMPAIGN_PY}" campaign_id >/dev/null 2>&1; then
    echo "Campaign not prepared. Run ./Tools/autotest/reset_firmware_SITL_validation_campaign.sh first." >&2
    exit 1
fi

ROOT="$(python3 "${CAMPAIGN_PY}" root)"
XLSX="$(python3 "${CAMPAIGN_PY}" spreadsheet)"
CAMPAIGN_ID="$(python3 "${CAMPAIGN_PY}" campaign_id)"

echo "=== Initializing firmware SITL validation campaign ==="
echo "Campaign folder: ${ROOT}"

python3 "${SCRIPT_DIR}/oafastwp_spreadsheet_data.py"

cat > "${ROOT}/README.txt" << EOF
Firmware SITL validation campaign — ${CAMPAIGN_ID}

Name source: ArduCopter/version.h THISFIRMWARE (must match checked-out git branch suffix).

Workflow:
  1. Run autotests:   ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh <phase> [TestName] [--skip-build]
  2. Generate report: ./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh <phase>
  3. Add phase tab:   ./Tools/autotest/add_firmware_SITL_validation_phase.sh <1|2|3>   (when ready)

Each report/artifacts run creates a new timestamped folder under phase<N>/report/ and
phase<N>/visual_evidence/ (latest/ symlink always points at the newest run).

Layout:
  phase<N>/logs/              autotest .txt / .tlog / .BIN
  phase<N>/visual_evidence/   HTML dashboard + PNG cards
  phase0/report/            firmware regression RTF + HTML (Firmware_Regression_Report.rtf)
  $(basename "${XLSX}")       spreadsheet (Intro + phase tabs)
EOF

echo "=== Campaign ready ==="
echo "Spreadsheet: ${XLSX}"
echo "Phase 0 logs: $(python3 "${CAMPAIGN_PY}" buildlogs 0)"
echo ""
echo "Next:"
echo "  ./Tools/autotest/run_firmware_SITL_validation_campaign_tests.sh 0"
echo "  ./Tools/autotest/generate_firmware_SITL_validation_campaign_artifacts.sh 0"
