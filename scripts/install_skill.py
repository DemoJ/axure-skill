"""Install this Agent Skills package into an explicitly selected host directory."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile


SKILL_NAME = 'axure-skill'
SOURCE = Path(__file__).resolve().parent.parent
ROOT_FILES = ('SKILL.md', 'README.md', 'LICENSE', 'package.json', '.gitignore', '.gitattributes')
DIRECTORIES = {
    'scripts': {'.py', '.cs', '.ps1', '.cjs'},
    'references': {'.md'},
    'examples': {'.json'},
    'agents': {'.yaml', '.yml'},
}
EXCLUDED = {'.cache', '.git', '__pycache__', 'node_modules', '.venv', 'outputs', 'deliverables'}


def source_files(source):
    source = source.resolve()
    header = (source / 'SKILL.md').read_text(encoding='utf-8-sig').split('---', 2)
    if len(header) != 3 or not re.search(r'^name:\s*axure-skill\s*$', header[1], re.M):
        raise ValueError('Source must declare name: axure-skill in SKILL.md.')
    selected = []
    for name in ROOT_FILES:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError('Missing or symlinked source file: ' + name)
        selected.append(path)
    for name, suffixes in DIRECTORIES.items():
        folder = source / name
        if folder.is_symlink():
            raise ValueError('Source directories must not be symlinked: ' + name)
        for path in sorted(folder.rglob('*')):
            relative = path.relative_to(source)
            if set(relative.parts) & EXCLUDED:
                continue
            if path.is_symlink():
                raise ValueError('Source symlinks are not supported: ' + str(relative))
            if path.is_file() and path.suffix.lower() in suffixes:
                if not path.resolve().is_relative_to(source):
                    raise ValueError('Source file resolves outside the skill directory.')
                selected.append(path)
    return selected


def install(source, target, dry_run=False):
    source, target = Path(source).resolve(), Path(target).expanduser().resolve()
    if target.name != SKILL_NAME:
        raise ValueError('Target directory must be named axure-skill to match SKILL.md.')
    if target == source or source in target.parents or target in source.parents:
        raise ValueError('Target must be separate from the source skill directory.')
    if target.exists():
        raise FileExistsError('Target exists; choose a new location or back up the existing skill: ' + str(target))
    selected = source_files(source)
    report = {'ok': True, 'skill': SKILL_NAME, 'target': str(target),
              'dry_run': dry_run, 'files': [str(p.relative_to(source)).replace('\\', '/') for p in selected]}
    if dry_run:
        return report
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.axure-install-', dir=target.parent) as temporary:
        staged = Path(temporary) / SKILL_NAME
        staged.mkdir()
        for path in selected:
            destination = staged / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        if target.exists():
            raise FileExistsError('Target was created during installation: ' + str(target))
        staged.rename(target)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path,
                        help='Full skill directory, ending with axure-skill. No host settings are modified.')
    parser.add_argument('--dry-run', action='store_true', help='List copied files without writing anything.')
    args = parser.parse_args()
    try:
        print(json.dumps(install(SOURCE, args.target, args.dry_run), ensure_ascii=False, indent=2))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
