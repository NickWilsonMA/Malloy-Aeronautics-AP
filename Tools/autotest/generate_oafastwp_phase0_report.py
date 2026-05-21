#!/usr/bin/env python3
"""Phase 0 firmware regression report (RTF + HTML) for SITL campaign evidence."""

from __future__ import print_function

import argparse
import glob
import html
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import generate_oafastwp_report_common as rpt
import generate_oafastwp_visual_evidence as visual
import firmware_SITL_validation_campaign as campaign
import oafastwp_spreadsheet_data as sheet

RUN_SCRIPT = campaign.RUN_TESTS_SCRIPT + ' 0'


def rtf_escape(text):
    text = text.replace('\\', '\\\\')
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    text = text.replace('\n', '\\par\n')
    return text


def rtf_heading(text, level=1):
    size = {1: 32, 2: 26, 3: 22}.get(level, 22)
    return '\\pard\\b\\fs%d %s\\b0\\fs22\\par\n' % (size, rtf_escape(text))


def rtf_body(text, bold=False):
    if bold:
        return '\\pard\\b %s\\b0\\fs22\\par\n' % rtf_escape(text)
    return '\\pard\\fs22 %s\\par\n' % rtf_escape(text)


def rtf_bullet(text):
    return '\\pard\\fs22\\bullet  %s\\par\n' % rtf_escape(text)


def collect_phase0_results(buildlogs):
    results = []
    for name, tid, desc in visual.PHASE0_TESTS:
        txt = rpt.latest_test_log(buildlogs, name)
        passed = False
        failure = ''
        evidence = []
        if txt:
            passed, content = rpt.parse_test_result(txt)
            m = re.search(r'FAILED: "[^"]+": (.+?)(?:\s*\(see|\n)', content, re.DOTALL)
            if m:
                failure = m.group(1).strip().replace('\n', ' ')[:240]
            evidence = rpt.extract_lines(content, [r'PASSED:', r'FAILED:', r'Exception caught:'])
        results.append({
            'name': name,
            'tid': tid,
            'description': desc,
            'passed': passed,
            'failure': failure,
            'log_ref': campaign.log_ref_relative(0, os.path.basename(txt)) if txt else '',
            'evidence': evidence[:5],
        })
    return results


def classify_failure(failure):
    if not failure:
        return 'Unknown'
    if 'GLOBAL_POSITION_INT' in failure or 'LOCAL_POSITION_NED' in failure:
        return 'SITL / MAVLink position stream lost (often flaky after long runs or TCP reconnect)'
    if 'AutoTestTimeoutException' in failure and 'Distance to Location' in failure:
        return 'Vehicle did not reach target location (RTL/navigation timeout)'
    if 'Hit ground' in failure or 'SIM Hit ground' in failure:
        return 'Vehicle contacted ground during manoeuvre'
    return 'See autotest log for traceback'


def write_rtf_report(out_path, results, stamp):
    passed_n = sum(1 for r in results if r['passed'])
    total = len(results)
    all_pass = passed_n == total
    gith = rpt.git_hash()
    failed = [r for r in results if not r['passed']]

    parts = [
        '{\\rtf1\\ansi\\deff0\n',
        '{\\fonttbl{\\f0 Calibri;}}\n',
        '{\\colortbl;\\red0\\green0\\blue0;\\red0\\green51\\blue102;}\n',
        '\\paperw11906\\paperh16838\\margl1440\\margr1440\\margt1440\\margb1440\n\n',
        '\\pard\\qc\\b\\fs32 %s\\b0\\fs22\\par\n' % rtf_escape(campaign.FIRMWARE_REGRESSION_REPORT_TITLE),
        '\\pard\\qc\\fs20 Generated: %s\\par\n' % rtf_escape(stamp),
        '\\pard\\qc Firmware: %s\\par\n' % rtf_escape(campaign.FIRMWARE_VERSION),
        '\\pard\\qc Campaign: docs/%s/\\par\n' % rtf_escape(campaign.CAMPAIGN_ID),
        '\\pard\\qc Git: %s\\par\n\\par\n' % rtf_escape(gith),
    ]

    parts.append(rtf_heading('1. Executive Summary', 2))
    parts.append(rtf_body(
        'This report summarises the generic firmware-update regression suite: %d unattended '
        'ArduCopter SITL autotests (P0-01..P0-22) — upstream ArduPilot regression plus Malloy '
        'Dijkstra baseline. Latest run under docs/%s/phase0/logs/. Overall result: %d/%d PASS (%s).'
        % (total, campaign.CAMPAIGN_ID, passed_n, total, 'PASS' if all_pass else 'FAIL'),
    ))
    parts.append('\\par\n')

    parts.append(rtf_heading('2. Test Results Matrix', 2))
    for r in results:
        status = 'PASS' if r['passed'] else 'FAIL'
        parts.append(rtf_body('%s  %s  [%s]  %s' % (r['tid'], status, r['name'], r['description']), bold=True))
        if r['log_ref']:
            parts.append(rtf_body('Log: %s' % r['log_ref']))
        parts.append('\\par\n')

    if failed:
        parts.append(rtf_heading('3. Failure Analysis', 2))
        for i, r in enumerate(failed, 1):
            parts.append(rtf_body('F%d. %s (%s)' % (i, r['tid'], r['name']), bold=True))
            parts.append(rtf_body('Symptom: %s' % (r['failure'] or 'No PASSED line in log')))
            parts.append(rtf_body('Likely cause: %s' % classify_failure(r['failure'])))
            if r['evidence']:
                parts.append(rtf_body('Log excerpt:'))
                for line in r['evidence']:
                    parts.append(rtf_body('  %s' % line[:200]))
            parts.append('\\par\n')

    parts.append(rtf_heading('4. Operational Notes', 2))
    parts.append(rtf_body(
        'Position-stream failures (GLOBAL_POSITION_INT / LOCAL_POSITION_NED) during a long firmware '
        'regression batch often indicate SITL or MAVLink TCP instability on WSL, not necessarily a '
        'defect. Re-run failed tests individually before treating as a regression.',
    ))
    parts.append(rtf_body(
        'P0-21 (Dijkstra maze RTL) failure with "SIM Hit ground" suggests the vehicle descended '
        'into terrain during RTL path planning — review OA/Dijkstra RTL altitude and maze geometry.',
    ))
    parts.append('\\par\n')

    parts.append(rtf_heading('5. Evidence Locations', 2))
    parts.append(rtf_bullet('Logs: phase0/logs/ArduCopter-P0_*.txt'))
    parts.append(rtf_bullet('Visual dashboard: phase0/visual_evidence/<timestamp>/index.html'))
    parts.append(rtf_bullet('Spreadsheet: %s.xlsx (%s tab)' % (
        campaign.CAMPAIGN_ID, campaign.PHASE0_WORKSHEET_NAME)))
    parts.append(rtf_bullet('This report: phase0/report/<timestamp>/'))
    parts.append('\\par\n')

    parts.append(rtf_heading('6. Sign-off Checklist', 2))
    for r in results:
        mark = 'PASS' if r['passed'] else 'FAIL — investigate or re-run'
        parts.append(rtf_bullet('%s — %s' % (r['tid'], mark)))
    parts.append(rtf_bullet('All firmware regression tests PASS before adding Phase 1 worksheet'))
    parts.append(rtf_bullet('Re-run failures: %s (single test via autotest.py)' % RUN_SCRIPT))
    parts.append('\\par\n')
    parts.append('}\n')

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(''.join(parts))


def write_html_report(out_dir, results, stamp):
    passed_n = sum(1 for r in results if r['passed'])
    total = len(results)
    all_pass = passed_n == total
    gith = rpt.git_hash()
    index_path = os.path.join(out_dir, 'index.html')

    parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8">',
        '<title>%s</title>' % html.escape(campaign.FIRMWARE_REGRESSION_REPORT_TITLE),
        '<style>body{font-family:Calibri,system-ui,sans-serif;max-width:900px;margin:2em auto;padding:0 1em;}',
        'h1{color:#003366;}h2{color:#003366;border-bottom:1px solid #ccc;}',
        'table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ccc;padding:8px;}',
        'th{background:#4472C4;color:#fff;}.pass{color:#080;font-weight:bold;}.fail{color:#c00;font-weight:bold;}',
        'ul.evidence{font-size:0.9em;}</style></head><body>',
        '<h1>%s</h1>' % html.escape(campaign.FIRMWARE_REGRESSION_REPORT_TITLE),
        '<p><strong>Generated:</strong> %s<br>' % html.escape(stamp),
        '<strong>Firmware:</strong> %s<br>' % html.escape(campaign.FIRMWARE_VERSION),
        '<strong>Git:</strong> <code>%s</code><br>' % html.escape(gith),
        '<strong>Overall:</strong> <span class="%s">%d/%d PASS</span></p>' % (
            'pass' if all_pass else 'fail', passed_n, total),
        '<p><a href="%s">Download RTF report</a> (Word-compatible)</p>' % (
            html.escape(campaign.FIRMWARE_REGRESSION_RTF_NAME)),
        '<h2>Test Results</h2><table><tr><th>ID</th><th>Result</th><th>Autotest</th><th>Description</th><th>Log</th></tr>',
    ]
    for r in results:
        parts.append('<tr><td>%s</td><td class="%s">%s</td><td><code>%s</code></td><td>%s</td><td><code>%s</code></td></tr>' % (
            r['tid'], 'pass' if r['passed'] else 'fail', 'PASS' if r['passed'] else 'FAIL',
            html.escape(r['name']), html.escape(r['description']), html.escape(r['log_ref'])))
    parts.append('</table>')

    failed = [r for r in results if not r['passed']]
    if failed:
        parts.append('<h2>Failure Analysis</h2>')
        for i, r in enumerate(failed, 1):
            parts.append('<h3>F%d. %s</h3>' % (i, html.escape(r['tid'])))
            parts.append('<p><strong>Symptom:</strong> %s</p>' % html.escape(r['failure'] or 'unknown'))
            parts.append('<p><strong>Likely cause:</strong> %s</p>' % html.escape(classify_failure(r['failure'])))

    parts.append('<h2>Run command</h2><p><code>%s</code></p>' % html.escape(RUN_SCRIPT))
    parts.append('</body></html>')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    return index_path


def main():
    parser = argparse.ArgumentParser(description='Generate firmware regression RTF/HTML evidence report')
    parser.add_argument('--buildlogs', default=None)
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    buildlogs = os.path.abspath(args.buildlogs or campaign.phase_buildlogs(0))
    if not os.path.isdir(buildlogs):
        print('Logs not found: %s' % buildlogs, file=sys.stderr)
        return 1

    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stamp_dir = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir = args.output or os.path.join(campaign.phase_report(0), stamp_dir)
    os.makedirs(out_dir, exist_ok=True)

    results = collect_phase0_results(buildlogs)
    rtf_path = os.path.join(out_dir, campaign.FIRMWARE_REGRESSION_RTF_NAME)
    write_rtf_report(rtf_path, results, stamp)
    html_path = write_html_report(out_dir, results, stamp)

    latest = os.path.join(campaign.phase_report(0), 'latest')
    if os.path.islink(latest):
        os.unlink(latest)
    elif os.path.isdir(latest):
        import shutil
        shutil.rmtree(latest)
    os.symlink(out_dir, latest)

    passed_n = sum(1 for r in results if r['passed'])
    print('Firmware regression report: %s' % rtf_path)
    print('Firmware regression HTML:   %s' % html_path)
    print('Latest link:    %s' % latest)
    print('Result: %d/%d PASS' % (passed_n, len(results)))
    return 0 if passed_n == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
