"""Portable installer tests; no Axure, host agent, or external packages required."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install_skill.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallSkillTests(unittest.TestCase):
    def test_distinct_hosts_receive_the_same_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payloads = []
            for host in ('.claude', '.cursor', '.opencode', '.agents', '.codex'):
                target = root / host / 'skills/axure-skill'
                result = installer.install(installer.SOURCE, target)
                self.assertTrue(result['ok'])
                self.assertTrue((target / 'SKILL.md').is_file())
                self.assertTrue((target / 'README.md').is_file())
                self.assertTrue((target / 'references/agent-integration.md').is_file())
                self.assertTrue((target / 'scripts/axure_skill.py').is_file())
                payloads.append({str(p.relative_to(target)): p.read_bytes()
                                 for p in target.rglob('*') if p.is_file()})
            self.assertTrue(all(p == payloads[0] for p in payloads))

    def test_existing_install_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'axure-skill'
            target.mkdir()
            (target / 'keep.txt').write_text('keep', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                installer.install(installer.SOURCE, target)
            self.assertEqual((target / 'keep.txt').read_text(encoding='utf-8'), 'keep')
            self.assertEqual(len(list(target.iterdir())), 1)

    def test_dry_run_and_directory_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'not-created/axure-skill'
            report = installer.install(installer.SOURCE, target, dry_run=True)
            self.assertTrue(report['dry_run'])
            self.assertFalse(target.parent.exists())
            with self.assertRaises(ValueError):
                installer.install(installer.SOURCE, Path(temporary) / 'wrong-name')

    def test_runtime_artifacts_are_excluded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'source/axure-skill'
            shutil.copytree(installer.SOURCE, source)
            artifacts = ('scripts/NativeBridge.exe', 'scripts/__pycache__/secret.py',
                         'scripts/node_modules/example/index.py', '.cache/public-api/Axure.Document.dll',
                         'examples/private.rp', 'examples/.env', 'references/private.log')
            for name in artifacts:
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'not for distribution')
            target = root / 'target/axure-skill'
            report = installer.install(source, target)
            self.assertTrue(all(name not in report['files'] for name in artifacts))
            self.assertTrue(all(not (target / name).exists() for name in artifacts))


if __name__ == '__main__':
    unittest.main()
