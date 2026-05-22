#!/usr/bin/env python3
"""Update campaign spreadsheet from all phase logs (runs + re-runs). Report/visual evidence deferred."""

from __future__ import print_function

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import generate_oafastwp_visual_evidence as visual
import firmware_SITL_validation_campaign as campaign
import update_fence_escape_spreadsheet as upd

PHASE_TESTS = {
    0: visual.PHASE0_TESTS,
    1: visual.PHASE1_TESTS,
    2: visual.PHASE2_TESTS,
    3: visual.PHASE3_TESTS,
}


def main():
    parser = argparse.ArgumentParser(
        description='Update campaign spreadsheet from autotest logs (all phases with data)')
    parser.add_argument('phase', type=int, choices=[0, 1, 2, 3],
                        help='Phase context for summary / re-run hints (spreadsheet updates all phases)')
    args = parser.parse_args()

    phase = args.phase
    buildlogs = campaign.phase_buildlogs(phase)
    xlsx = campaign.spreadsheet_path()
    campaign_root = campaign.campaign_root()

    if not os.path.isfile(xlsx):
        print('Campaign not initialized. Run: %s' % campaign.RESET_SCRIPT, file=sys.stderr)
        return 1
    if not os.path.isdir(buildlogs):
        print('No logs folder: %s' % buildlogs, file=sys.stderr)
        print('Run: %s %d' % (campaign.RUN_TESTS_SCRIPT, phase), file=sys.stderr)
        return 1

    tests = PHASE_TESTS[phase]
    results = visual.collect_results(buildlogs, tests)
    passed_n = sum(1 for r in results if r['passed'])
    total = len(results)
    failed = [r for r in results if not r['passed']]
    missing = [r for r in results if not r.get('txt_path')]

    print('')
    print('=== Campaign spreadsheet update ===')
    print('Campaign:    %s' % campaign_root)
    print('Context:     Phase %d (%d/%d PASS from latest logs)' % (phase, passed_n, total))
    print('Spreadsheet: %s' % xlsx)
    print('')

    rc = upd.update_all_spreadsheet(xlsx)
    if rc != 0:
        return rc

    print('')
    _print_rerun_commands(phase, failed, missing)
    return 0 if not failed and not missing else 1


def _print_rerun_commands(phase, failed, missing):
    if not failed and not missing:
        print('All Phase %d tests PASS.' % phase)
        if phase == 0:
            print('Next: %s 1  (when ready for fence regression)' % campaign.ADD_PHASE_SCRIPT)
        return

    print('Re-run failed or missing tests (logs go to %s/logs):' % campaign.phase_dir_name(phase))
    seen = set()
    for r in failed + missing:
        tid = r['sitl_ids'][0]
        if tid in seen:
            continue
        seen.add(tid)
        print('  %s %d %s --skip-build' % (campaign.RUN_TESTS_SCRIPT, phase, r['name']))
    print('')
    print('Then refresh spreadsheet:')
    print('  %s %d' % (campaign.GENERATE_ARTIFACTS_SCRIPT, phase))


if __name__ == '__main__':
    sys.exit(main())
