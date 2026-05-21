#!/usr/bin/env python3
"""HTML evidence report for OAfastWP Phase 2 autotest (SITL-14, 17, 23, 29, 32)."""

from __future__ import print_function

import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import generate_oafastwp_report_common as rpt
import firmware_SITL_validation_campaign as campaign

TESTS = [
    {
        'name': 'OAfastWP_GuidedInsideExclusion',
        'sitl_ids': ['SITL-29'],
        'description': 'GUIDED goto inside exclusion rejected; vehicle holds outside',
        'evidence_patterns': [
            r'OAfastWP guided inside exclusion: PASS',
            r'PASSED:.*OAfastWP_GuidedInsideExclusion',
        ],
        'forbidden_patterns': [],
    },
    {
        'name': 'OAfastWP_BreachEscape_ModeChangeAtStandoff',
        'sitl_ids': ['SITL-32'],
        'description': 'RTL -> Loiter -> RTL at escape stand-off still reaches home',
        'evidence_patterns': [
            r'Mode change at stand-off',
            r'Got mode LOITER',
            r'Got mode RTL',
            r'OAfastWP mode change at stand-off: PASS',
            r'PASSED:.*OAfastWP_BreachEscape_ModeChangeAtStandoff',
        ],
        'forbidden_patterns': [
            r'OADJ: dest unreachable',
            r'strict replan complete',
        ],
    },
    {
        'name': 'OAfastWP_RTL_BlockedPath',
        'sitl_ids': ['SITL-14'],
        'description': 'RTL avoids exclusion fence between aircraft and home',
        'evidence_patterns': [
            r'Got mode RTL',
            r'OAfastWP RTL blocked path: PASS',
            r'PASSED:.*OAfastWP_RTL_BlockedPath',
        ],
        'forbidden_patterns': [],
    },
    {
        'name': 'OAfastWP_FastWaypoints_Mission',
        'sitl_ids': ['SITL-17'],
        'description': 'AUTO mission with OA fast waypoints completes without fence breach',
        'evidence_patterns': [
            r'OAfastWP fast waypoints mission: PASS',
            r'PASSED:.*OAfastWP_FastWaypoints_Mission',
        ],
        'forbidden_patterns': [r'Fence Breached'],
    },
    {
        'name': 'OAfastWP_ThreePointDogleg',
        'sitl_ids': ['SITL-23'],
        'description': 'Three close waypoints with fast-waypoint dogleg smoothing',
        'evidence_patterns': [
            r'OAfastWP three-point dogleg: PASS',
            r'PASSED:.*OAfastWP_ThreePointDogleg',
        ],
        'forbidden_patterns': [],
    },
]


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate OAfastWP Phase 2 HTML report')
    parser.add_argument('--buildlogs', default=None)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    buildlogs = os.path.abspath(args.buildlogs or campaign.phase_buildlogs(2))
    if not os.path.isdir(buildlogs):
        print('Logs not found: %s' % buildlogs, file=sys.stderr)
        return 1

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = args.output or os.path.join(campaign.phase_report(2), stamp)

    results = []
    for spec in TESTS:
        name = spec['name']
        txt = rpt.latest_test_log(buildlogs, name)
        tlog = rpt.latest_file(os.path.join(buildlogs, 'ArduCopter-%s-autotest-*.tlog' % name))
        binlog = rpt.latest_bin_for_test(buildlogs, name)

        passed = False
        content = ''
        if txt:
            passed, content = rpt.parse_test_result(txt)

        evidence = rpt.extract_lines(content, spec['evidence_patterns']) if content else []
        forbidden = rpt.count_forbidden(content, spec.get('forbidden_patterns', []))
        oadj = rpt.count_oadj_state(binlog)

        os.makedirs(out_dir, exist_ok=True)
        map_png = None
        if tlog:
            map_png = os.path.join(out_dir, '%s_track.png' % name)
            if not rpt.plot_track(tlog, map_png, name):
                map_png = None

        artifacts = []
        for label, src in [('Autotest log', txt), ('MAVLink tlog', tlog), ('Dataflash BIN', binlog)]:
            if src and os.path.isfile(src):
                dst = os.path.join(out_dir, os.path.basename(src))
                if os.path.abspath(src) != os.path.abspath(dst):
                    shutil.copy2(src, dst)
                artifacts.append((label, os.path.basename(dst)))

        results.append({
            'name': name,
            'sitl_ids': spec['sitl_ids'],
            'description': spec['description'],
            'passed': passed,
            'evidence': evidence,
            'forbidden_found': forbidden,
            'oadj_count': oadj,
            'map_png': map_png,
            'artifacts': artifacts,
        })

    report_path = rpt.write_report(
        out_dir, buildlogs, results,
        phase_title='OAfastWP Phase 2 - SITL-14, 17, 23, 29, 32',
        run_script=campaign.RUN_TESTS_SCRIPT + ' 2',
    )
    print('Report written: %s' % report_path)
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
