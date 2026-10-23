"""Page alignment regression; opt into native/browser checks on an RP9 host."""
import copy
import hashlib
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


class AlignmentSpecTests(unittest.TestCase):
    def test_invalid_document_and_page_alignment_is_rejected(self):
        for alignment in ('right', '', None, 1, [], {}):
            for level in ('document', 'page'):
                with self.subTest(alignment=alignment, level=level):
                    spec = a.read(ROOT / 'examples/presentation.json')
                    target = spec if level == 'document' else spec['pages'][0]
                    target['page_alignment'] = alignment
                    with self.assertRaisesRegex(ValueError, 'page_alignment'):
                        a.validate_spec(spec)


@unittest.skipUnless(os.environ.get('AXURE_NATIVE_TESTS') == '1', 'Set AXURE_NATIVE_TESTS=1 on an RP9 host with Playwright')
class NativeAlignmentTests(unittest.TestCase):
    def test_native_defaults_overrides_existing_page_edit_and_runtime(self):
        install = Path(os.environ.get('AXURE9_DIR', a.DEFAULT_INSTALL))
        spec = a.read(ROOT / 'examples/presentation.json')
        with tempfile.TemporaryDirectory(prefix='axure-alignment-') as temporary:
            folder = Path(temporary)
            source, edited = folder / 'source.rp', folder / 'edited.rp'
            a.create(spec, source, install)
            original = a.inspect(source, install)
            self.assertEqual([p['page_alignment'] for p in original['pages']], ['center', 'left', 'center'])
            self.assertEqual(original['editor']['initial_page'], original['pages'][0]['guid'])
            self.assertEqual(original['editor']['open_pages'], [original['pages'][0]['guid']])
            widgets = {w['name']: w for w in original['pages'][0]['widgets']}
            self.assertEqual(widgets['canvas']['x'], 525)
            self.assertEqual(widgets['heading']['x'] - widgets['canvas']['x'], 24)
            original_hash = hashlib.sha256(source.read_bytes()).hexdigest()

            # Existing widget-only patches preserve page alignment.
            a.edit(source, {'updates': [{'page': 'default', 'widget': 'heading', 'set': {'text': 'Updated'}}]}, folder / 'widget.rp', install)
            self.assertEqual([p['page_alignment'] for p in a.inspect(folder / 'widget.rp', install)['pages']], ['center', 'left', 'center'])
            # Page-only patches retain widget GUIDs, coordinates and text.
            a.edit(source, {'page_updates': [{'page': original['pages'][1]['guid'], 'set': {'page_alignment': 'center'}}]}, edited, install)
            actual = a.inspect(edited, install)
            self.assertEqual([p['page_alignment'] for p in actual['pages']], ['center', 'center', 'center'])
            for before, after in zip(original['pages'], actual['pages']):
                self.assertEqual(before['guid'], after['guid'])
                self.assertEqual(before['widgets'], after['widgets'])
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original_hash)

            inherited = copy.deepcopy(spec)
            inherited['page_alignment'] = 'left'
            a.create(inherited, folder / 'left-default.rp', install)
            self.assertEqual([p['page_alignment'] for p in a.inspect(folder / 'left-default.rp', install)['pages']], ['left', 'left', 'center'])

            exported = folder / 'html'
            self.assertTrue(a.export_html(source, exported, install)['source_unchanged'])
            result = subprocess.run(['node', str(ROOT / 'scripts/runtime_test.cjs'), str(exported),
                                     str(ROOT / 'examples/presentation.test.json')], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report['ok'])
            self.assertEqual(len(report['checks']), 6)


if __name__ == '__main__':
    unittest.main()
