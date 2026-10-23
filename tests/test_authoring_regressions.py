"""Regressions from real authoring failures; optional RP9/Chromium integration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import axure_skill as a
from model import scalar, set_value


class AuthoringValidationTests(unittest.TestCase):
    def test_native_scalar_values_keep_their_clr_types(self):
        mask = scalar(15)
        set_value(mask, False)
        self.assertIs(type(mask['v']), int)
        self.assertEqual(mask['v'], 0)
        flag = scalar(False)
        set_value(flag, 1)
        self.assertIs(flag['v'], True)
        with self.assertRaisesRegex(ValueError, 'integer'):
            set_value(mask, 1.5)
        with self.assertRaisesRegex(ValueError, 'boolean'):
            set_value(flag, 'false')

    def test_list_target_has_an_actionable_error_before_model_lookup(self):
        compiler = object.__new__(a.NativeCompiler)
        with self.assertRaisesRegex(ValueError, 'use targets'):
            compiler.action({}, {'type': 'show', 'target': ['a', 'b']}, 'page')


@unittest.skipUnless(os.environ.get('AXURE_NATIVE_TESTS') == '1', 'Set AXURE_NATIVE_TESTS=1 on an RP9 host')
class NativeAuthoringTests(unittest.TestCase):
    def test_focused_border_mask_and_delayed_visibility_with_named_screenshots(self):
        from style_info import style_info
        install = Path(os.environ.get('AXURE9_DIR', a.DEFAULT_INSTALL))
        shadow = style_info(a, install, 'OUTER_SHADOW')['properties']['OUTER_SHADOW']
        self.assertIn('Color', shadow['fields'])
        self.assertIn('BlurRadius', shadow['fields'])
        spec = {'pages': [{'id': 'home', 'name': 'Home', 'widgets': [
            {'id': 'trigger', 'kind': 'button', 'x': 525, 'y': 20, 'width': 160, 'height': 40,
             'text': 'Open', 'native_style': {'CORNER_RADIUS': 16,
                 'OUTER_SHADOW': {'On': True, 'OffsetY': 8, 'BlurRadius': 24, 'Color': '#16000000'}},
             'events': {'OnClick': [{'type': 'wait', 'ms': 180}, {'type': 'show', 'target': 'panel'}]}},
            {'id': 'panel', 'kind': 'panel', 'x': 525, 'y': 80, 'width': 300, 'height': 120,
             'hidden': True, 'states': [{'name': 'Form', 'widgets': [
                 {'id': 'input', 'kind': 'input', 'x': 0, 'y': 0, 'width': 250, 'height': 44,
                  'state_styles': {'Focused': {'BORDER_VISIBILITY': False}}},
                 {'id': 'label', 'kind': 'text', 'x': 0, 'y': 60, 'width': 250, 'height': 30, 'text': 'Ready'}]}]}
        ]}]}
        with tempfile.TemporaryDirectory(prefix='axure-authoring-') as temporary:
            folder = Path(temporary).resolve()
            self.assertTrue(a.create(spec, folder / 'test.rp', install)['ok'])
            self.assertTrue(a.export_html(folder / 'test.rp', folder / 'html', install)['ok'])
            node = os.environ.get('AXURE_TEST_NODE', 'node')
            probe = subprocess.run([node, str(ROOT / 'scripts/runtime_test.cjs'), '--doctor'], capture_output=True)
            if probe.returncode:
                self.skipTest('Native checks passed; Playwright/Chromium unavailable')
            plan = {'steps': [{'open': 'Home', 'target': 'panel', 'visible': False},
                              {'click': 'trigger', 'target': 'panel', 'visible': True, 'screenshot': 'shots/phone.png'},
                              {'viewport': {'width': 1440, 'height': 900}, 'screenshot': 'shots/desktop.png'}]}
            a.write(folder / 'plan.json', plan)
            run = subprocess.run([node, str(ROOT / 'scripts/runtime_test.cjs'), str(folder / 'html'), str(folder / 'plan.json')],
                                 capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads(run.stdout)
            self.assertEqual(len(report['screenshots']), 2)
            self.assertTrue(all(Path(p).is_file() for p in report['screenshots']))


if __name__ == '__main__':
    unittest.main()
