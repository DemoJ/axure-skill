"""Text alignment must survive RP serialization, export, and existing-file edits."""
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


@unittest.skipUnless(os.environ.get('AXURE_NATIVE_TESTS') == '1', 'Set AXURE_NATIVE_TESTS=1 on an RP9 host')
class NativeTextAlignmentTests(unittest.TestCase):
    def test_alignment_across_templates_and_existing_file_edits(self):
        widgets, steps = [], [{'open': 'Alignment'}]
        for kind in ('text', 'heading1', 'rect', 'button'):
            for align in ('left', 'center', 'right'):
                name = kind + '_' + align
                widgets.append({'id': name, 'kind': kind, 'x': 525,
                                'y': 20 + len(widgets) * 44, 'width': 300, 'height': 40,
                                'text': name, 'align': align, 'font_size': 16, 'bold': False})
                steps.append({'target': name, 'style': {'textAlign': align, 'fontWeight': '400'}})
        widgets.append({'id': 'panel', 'kind': 'panel', 'x': 525, 'y': 600,
                        'width': 300, 'height': 80, 'states': [{'name': 'State', 'widgets': [
                            {'id': 'nested', 'kind': 'text', 'x': 0, 'y': 0, 'width': 300,
                             'height': 40, 'text': 'Nested', 'align': 'center'}]}]})
        steps.append({'target': 'nested', 'style': {'textAlign': 'center'}})
        spec = {'pages': [{'id': 'alignment', 'name': 'Alignment', 'widgets': widgets}]}
        install = Path(os.environ.get('AXURE9_DIR', a.DEFAULT_INSTALL))
        with tempfile.TemporaryDirectory(prefix='axure-text-alignment-') as temporary:
            folder = Path(temporary).resolve()
            a.create(spec, folder / 'source.rp', install)
            node = os.environ.get('AXURE_TEST_NODE', 'node')
            probe = subprocess.run([node, str(ROOT / 'scripts/runtime_test.cjs'), '--doctor'], capture_output=True)
            if probe.returncode:
                self.skipTest('Native creation passed; Playwright/Chromium unavailable')

            def check(source, name, checks):
                exported = folder / name
                a.export_html(source, exported, install)
                plan = folder / (name + '.json')
                a.write(plan, {'steps': checks})
                run = subprocess.run([node, str(ROOT / 'scripts/runtime_test.cjs'), str(exported), str(plan)],
                                     capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertTrue(json.loads(run.stdout)['ok'])

            check(folder / 'source.rp', 'created', steps)
            a.edit(folder / 'source.rp', {'updates': [
                {'page': 'Alignment', 'widget': 'text_center', 'set': {'align': 'right'}},
                {'page': 'Alignment', 'widget': 'nested', 'set': {'align': 'left'}}
            ]}, folder / 'edited.rp', install)
            check(folder / 'edited.rp', 'edited', [{'open': 'Alignment'},
                  {'target': 'text_center', 'style': {'textAlign': 'right', 'fontWeight': '400'}},
                  {'target': 'nested', 'style': {'textAlign': 'left'}}])


if __name__ == '__main__':
    unittest.main()
