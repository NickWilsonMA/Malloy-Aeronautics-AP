#!/usr/bin/env python3
"""HTML evidence report for OAfastWP Phase 3 autotest (SITL-25..31 fence escape)."""

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
        'name': 'OAfastWP_BreachEscape_RTL_Home',
        'sitl_ids': ['SITL-25', 'SITL-26', 'SITL-27', 'SITL-31'],
        'description': 'Breach escape vector, RTL auto hand-off, no fence re-entry, clean GCS',
        'evidence_patterns': [
            r'Fence Breached',
            r'Got mode RTL',
            r'OAfastWP breach escape RTL home: PASS',
            r'PASSED:.*OAfastWP_BreachEscape_RTL_Home',
        ],
        'forbidden_patterns': [
            r'OADJ: dest unreachable',
            r'strict replan complete',
        ],
    },
    {
        'name': 'OAfastWP_MissionWP_InsideExclusion',
        'sitl_ids': ['SITL-28'],
        'description': 'AUTO mission WP inside exclusion holds with path error',
        'evidence_patterns': [
            r'Dijkstra: could not find path',
            r'OAfastWP mission WP inside exclusion: PASS',
            r'PASSED:.*OAfastWP_MissionWP_InsideExclusion',
        ],
        'forbidden_patterns': [],
    },
    {
        'name': 'OAfastWP_BreachEscape_RepeatedCycles',
        'sitl_ids': ['SITL-30'],
        'description': 'Three repeated breach -> escape -> RTL home cycles',
        'evidence_patterns': [
            r'Breach RTL cycle 1/3',
            r'Breach RTL cycle 2/3',
            r'Breach RTL cycle 3/3',
            r'Fence Breached',
            r'OAfastWP repeated breach RTL cycles: PASS',
            r'PASSED:.*OAfastWP_BreachEscape_RepeatedCycles',
        ],
        'forbidden_patterns': [
            r'OADJ: dest unreachable',
            r'strict replan complete',
        ],
    },
]


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate OAfastWP Phase 3 HTML report')
    parser.add_argument('--buildlogs', default=None)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    buildlogs = os.path.abspath(args.buildlogs or campaign.phase_buildlogs(3))
    if not os.path.isdir(buildlogs):
        print('Logs not found: %s' % buildlogs, file=sys.stderr)
        return 1

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = args.output or os.path.join(campaign.phase_report(3), stamp)

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
        phase_title='OAfastWP Phase 3 - SITL-25..31 fence escape vector',
        run_script=campaign.RUN_TESTS_SCRIPT + ' 3',
    )
    print('Report written: %s' % report_path)
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
