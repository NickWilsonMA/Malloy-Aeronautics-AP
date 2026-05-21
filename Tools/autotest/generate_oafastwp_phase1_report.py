#!/usr/bin/env python3
"""HTML evidence report for OAfastWP Phase 1 autotest (SITL-01..23)."""

from __future__ import print_function

import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import generate_oafastwp_report_common as rpt
import firmware_SITL_validation_campaign as campaign

TESTS = [
    ('SITL_01_PolygonExclusionMission', 'SITL-01', 'Polygon exclusion AUTO mission'),
    ('SITL_02_CircleExclusionMission', 'SITL-02', 'Circular exclusion AUTO mission'),
    ('SITL_03_MultipleExclusionMission', 'SITL-03', 'Multiple exclusion fences corridor'),
    ('SITL_04_InclusionFenceMission', 'SITL-04', 'Inclusion fence operation'),
    ('SITL_05_OverlappingExclusionMission', 'SITL-05', 'Overlapping exclusion fences'),
    ('SITL_06_NarrowCorridorMission', 'SITL-06', 'Narrow corridor between fences'),
    ('SITL_07_NoValidPathMission', 'SITL-07', 'No valid path - safe hold'),
    ('SITL_08_AddFenceDuringMission', 'SITL-08', 'Add fence during AUTO'),
    ('SITL_09_ChangeFenceDuringMission', 'SITL-09', 'Change fence during AUTO'),
    ('SITL_10_DeleteFenceDuringMission', 'SITL-10', 'Delete fence during AUTO'),
    ('SITL_11_EnableFenceInAir', 'SITL-11', 'Enable fence in air'),
    ('SITL_12_DisableFenceInAir', 'SITL-12', 'Disable fence in air'),
    ('SITL_13_FenceBreachRecovery', 'SITL-13', 'Fence breach recovery'),
    ('SITL_14_RTLBlockedPath', 'SITL-14', 'RTL through blocked path'),
    ('SITL_15_RTLToRallyBlockedPath', 'SITL-15', 'RTL to rally through fence'),
    ('SITL_16_FastWaypointsDisabled', 'SITL-16', 'Fast waypoints disabled baseline'),
    ('SITL_17_FastWaypointsEnabled', 'SITL-17', 'Fast waypoints enabled'),
    ('SITL_18_DenseWaypointsNearFence', 'SITL-18', 'Dense WPs near fence'),
    ('SITL_19_WaypointsCloseToMargin', 'SITL-19', 'WPs close to fence margin'),
    ('SITL_20_AltitudeGeofenceCeiling', 'SITL-20', 'Altitude geofence ceiling'),
    ('SITL_21_AltitudeAndHorizontalFence', 'SITL-21', 'Altitude + horizontal fence'),
    ('SITL_22_OAOptionsToggleInFlight', 'SITL-22', 'OA_OPTIONS toggle in flight'),
    ('SITL_23_ThreePointDogleg', 'SITL-23', 'Three-point dogleg'),
]


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Generate OAfastWP Phase 1 HTML report')
    parser.add_argument('--buildlogs', default=None)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    buildlogs = os.path.abspath(args.buildlogs or campaign.phase_buildlogs(1))
    if not os.path.isdir(buildlogs):
        print('Logs not found: %s' % buildlogs, file=sys.stderr)
        return 1

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = args.output or os.path.join(campaign.phase_report(1), stamp)

    results = []
    for name, sitl, desc in TESTS:
        txt = rpt.latest_test_log(buildlogs, name)
        tlog = rpt.latest_file(os.path.join(buildlogs, 'ArduCopter-%s-autotest-*.tlog' % name))
        binlog = rpt.latest_bin_for_test(buildlogs, name)
        passed, content = (False, '')
        if txt:
            passed, content = rpt.parse_test_result(txt)
        evidence = rpt.extract_lines(content, [r'PASSED:.*' + name, r'PASS']) if content else []
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
            'name': name, 'sitl_ids': [sitl], 'description': desc,
            'passed': passed, 'evidence': evidence, 'forbidden_found': [],
            'oadj_count': rpt.count_oadj_state(binlog), 'map_png': map_png,
            'artifacts': artifacts,
        })

    report_path = rpt.write_report(
        out_dir, buildlogs, results,
        phase_title='OAfastWP Phase 1 - SITL-01..23 regression',
        run_script=campaign.RUN_TESTS_SCRIPT + ' 1',
    )
    print('Report written: %s' % report_path)
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
