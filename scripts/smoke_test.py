"""Integration checks against actual native RP output and the official read API."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

import axure_skill as a


def run():
    base = a.HERE.parent
    spec = a.read(base / 'examples/login.json')
    install = Path(os.environ.get('AXURE9_DIR', a.DEFAULT_INSTALL))
    tests = base / '.cache/tests'
    tests.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='integration-', dir=tests) as temporary:
        folder = Path(temporary)
        original, edited = folder / 'original.rp', folder / 'edited.rp'
        a.create(spec, original, install)
        before = hashlib.sha256(original.read_bytes()).hexdigest()
        patch = {'updates': [
            {'page': '登录', 'widget': 'title', 'set': {'text': '修改已生效', 'x': 540, 'font_size': 28, 'bold': False}},
            {'page': '登录', 'widget': 'subtitle', 'set': {'font_size': 20}},
            {'page': '登录', 'widget': 'email', 'set': {'text': 'demo@example.com', 'x': 540}},
            {'page': '登录', 'widget': 'password', 'set': {'password': False}},
        ]}
        a.edit(original, patch, edited, install)
        assert before == hashlib.sha256(original.read_bytes()).hexdigest(), 'Source changed'
        widgets = {w['name']: w for w in a.inspect(edited, install)['pages'][0]['widgets']}
        assert widgets['title']['text'] == '修改已生效' and widgets['title']['x'] == 540
        assert widgets['email']['text'] == 'demo@example.com'
        assert widgets['email']['placeholder'] == 'name@example.com', 'Edit lost placeholder'
        assert widgets['password']['password'] is False
        public = a.verify(edited, folder / 'preview')
        actual = {w['name']: w for w in public['pages'][0]['widgets']}
        assert actual['title']['font_size'] == 21 and actual['title']['bold'] is False
        assert actual['subtitle']['font_size'] == 15 and actual['subtitle']['text'] == '登录你的工作空间'
        assert all(Path(p['screenshot']).is_file() for p in public['pages'])
        assert not list(folder.glob('.axure-*')), 'Temporary staging data remains'
        for action, expected in [
            (lambda: a.create(spec, original, install), FileExistsError),
            (lambda: a.edit(original, patch, original, install), FileExistsError),
            (lambda: a.edit(original, {'updates': [{'page': '登录', 'widget': 'missing', 'set': {'x': 0}}]}, folder / 'invalid.rp', install), ValueError),
            (lambda: a.create({'pages': spec['pages'], 'unknown': 1}, folder / 'unknown.rp', install), ValueError),
        ]:
            try:
                action()
                raise AssertionError('Expected rejection')
            except expected:
                pass
        assert not (folder / 'invalid.rp').exists() and not (folder / 'unknown.rp').exists()
        assert before == hashlib.sha256(original.read_bytes()).hexdigest()
    return {'ok': True, 'checks': ['create 2 pages/12 widgets', 'native serializer readback',
            'official API load/render', 'edit text/geometry/font/input properties',
            'source unchanged', 'existing outputs preserved', 'invalid updates rejected', 'staging cleanup']}


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2))
