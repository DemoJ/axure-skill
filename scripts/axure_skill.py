"""Create and inspect editable Axure RP9 files without UI automation."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

from model import *
from advanced import NativeCompiler, EXTRA_KINDS

HERE = Path(__file__).resolve().parent
DEFAULT_INSTALL = Path(r'C:\Program Files (x86)\Axure\Axure RP 9')
EXPECTED_SHA256 = 'f7dcdec8f44f122cf4c7f887655335dc49df159dc01dc981a649f1003b095505'
KINDS = {'rect': 'Box 1', 'text': 'Paragraph', 'button': 'Primary Button',
         'input': 'Text Field', 'checkbox': 'Checkbox'}
KINDS.update(EXTRA_KINDS)
PAGE_ALIGNMENT = -1073741798  # RP9 PName.PAGE_ALIGNMENT; distinct from text alignment.
PAGE_ALIGNMENTS = {'left': 0, 'center': 1}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')

def bridge(install, command, source, destination):
    exe = HERE / 'NativeBridge.exe'
    if not exe.exists() or exe.stat().st_mtime < (HERE / 'NativeBridge.cs').stat().st_mtime:
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE / 'build.ps1')], check=True, capture_output=True)
    result = subprocess.run([str(exe), str(install), command, str(source), str(destination)], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
    return json.loads(result.stdout.decode('utf-8-sig'))

def check_install(install):
    exe = install / 'AxureRP9.exe'
    if not exe.is_file():
        raise ValueError('AxureRP9.exe was not found in ' + str(install))
    actual = hashlib.sha256(exe.read_bytes()).hexdigest()
    if actual != EXPECTED_SHA256:
        raise ValueError('Unsupported Axure binary. This adapter requires the tested RP 9.0.0.3744 build. SHA256=' + actual)
    return actual

def verify(file, render_directory=None):
    cmd = [str(Path(os.environ['WINDIR']) / 'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'),
           '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(HERE / 'verify.ps1'), '-InputFile', str(Path(file).resolve())]
    if render_directory:
        cmd.extend(['-RenderDirectory', str(Path(render_directory).resolve())])
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace') + result.stdout.decode('utf-8', errors='replace'))
    return json.loads(result.stdout.decode('utf-8-sig'))


def export_html(file, output, install):
    """Generate real Axure HTML without starting its editor or opening a browser."""
    check_install(install)
    file, output = file.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError('HTML output directory must be new.')
    output.parent.mkdir(parents=True, exist_ok=True)
    helper = HERE / 'NativeExport.exe'
    source = HERE / 'NativeExport.cs'
    if not helper.exists() or helper.stat().st_mtime < source.stat().st_mtime:
        csc = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework/v4.0.30319/csc.exe'
        result = subprocess.run([str(csc), '/nologo', '/platform:x86', '/r:System.Web.Extensions.dll', '/out:' + str(helper), str(source)], capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stdout.decode('utf-8', errors='replace'))
    before = hashlib.sha256(file.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='.axure-html-', dir=output.parent) as temporary:
        job = Path(temporary)
        working = job / 'input.rp'
        shutil.copy2(file, working)
        try:
            result = subprocess.run([str(helper), str(install), str(working), str(job / 'html'), str(job / 'runtime')],
                                    capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired:
            raise RuntimeError('Native HTML export exceeded 60 seconds; its isolated helper was stopped.') from None
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))
        report = json.loads(result.stdout.decode('utf-8-sig'))
        if before != hashlib.sha256(file.read_bytes()).hexdigest():
            raise RuntimeError('Source file changed during export.')
        (job / 'html').rename(output)
    return {**report, 'output': str(output), 'source_unchanged': True}

def cache(install):
    check_install(install)
    folder = HERE.parent / '.cache' / 'rp9-3744-v2'
    if not (folder / 'index.json').exists():
        folder.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.rp9-cache-', dir=folder.parent) as temporary:
            generated = Path(temporary) / 'library'
            bridge(install, 'unpack', install / 'DefaultSettings/Libraries/Default.rplib', generated)
            try:
                generated.rename(folder)
            except OSError:
                # A concurrent first invocation may have published its complete cache.
                if not (folder / 'index.json').is_file():
                    raise RuntimeError('Incomplete template cache: ' + str(folder))
    return folder


def model_schema(install):
    folder = HERE.parent / '.cache/native-schema-v3'
    if not (folder / 'catalog.json').exists():
        folder.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.schema-', dir=folder.parent) as temporary:
            generated = Path(temporary) / 'models'
            bridge(install, 'schema', 'all', generated)
            try:
                generated.rename(folder)
            except OSError:
                if not (folder / 'catalog.json').exists():
                    raise
    return folder

def locate(folder):
    result = {}
    for path in folder.glob('[0-9]*.json'):
        doc = read(path)
        result.setdefault(rtype(root(doc)), []).append((path.stem, doc))
    return result

def prop_scalar(example, new):
    out = copy.deepcopy(example)
    set_value(out, new)
    return out

def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)

def argb(color):
    if not isinstance(color, str) or len(color) not in (7, 9) or not color.startswith('#'):
        raise ValueError('Use #RRGGBB or #AARRGGBB for colors.')
    n = int(color[1:], 16)
    if len(color) == 7:
        n |= 0xff000000
    return n - 0x100000000 if n >= 0x80000000 else n

def style_prop(style, code, new, exemplar=None):
    ps = items(get(style, 'PropList'))
    item = next((p for p in ps if value(get(p, 'DOAName')) == code), None)
    if item is None:
        if exemplar is None:
            raise ValueError('Missing native property template ' + str(code))
        item = copy.deepcopy(exemplar)
        set_value(get(item, 'DOAName'), code)
        ps.append(item)
    if isinstance(new, dict):
        put(item, 'Value', new)
    else:
        set_value(get(item, 'Value'), new)

def alignment_template(design):
    return next(p for o in design['objects'] if rtype(o) == 'Axure:PageStyle'
                for p in items(get(o, 'PropList')) if value(get(p, 'DOAName')) == PAGE_ALIGNMENT)

def set_page_alignment(page, alignment, exemplar):
    if not isinstance(alignment, str) or alignment not in PAGE_ALIGNMENTS:
        raise ValueError('page_alignment must be left or center.')
    style = by_id(page)[ref_id(get(root(page), 'page-style'))]
    style_prop(style, PAGE_ALIGNMENT, PAGE_ALIGNMENTS[alignment], exemplar)

def page_alignment(page, design):
    mapping = by_id(design)
    sheet = mapping[ref_id(get(root(design), 'PageStyleSheet'))]
    default = mapping[ref_id(get(sheet, 'DefaultPageStyle'))]
    style = by_id(page)[ref_id(get(root(page), 'page-style'))]
    # Page overrides take precedence over the document's inherited default.
    for candidate in (style, default):
        prop = next((p for p in items(get(candidate, 'PropList'))
                     if value(get(p, 'DOAName')) == PAGE_ALIGNMENT), None)
        if prop is not None:
            native = value(get(prop, 'Value'))
            return next((name for name, code in PAGE_ALIGNMENTS.items() if code == native), native)
    return 'left'

def bounds(style, spec):
    for code, keys in [(-1073741723, ('X', 'Y')), (-1073741719, ('Width', 'Height'))]:
        p = next(p for p in items(get(style, 'PropList')) if value(get(p, 'DOAName')) == code)
        for key in keys:
            set_value(get(get(p, 'Value'), key), spec[key.lower()])

def template_records(doc):
    # Keep all record dependencies used by a simple widget, excluding page scaffolding.
    wanted = [o for o in doc['objects'] if rtype(o).startswith('Axure:DiagramObject:') or rtype(o) == 'Axure:Style']
    return wanted

def modify_widget(doc, widget, spec, property_templates, rich_template):
    mapping = by_id(doc)
    style = mapping[ref_id(get(widget, 'MyStyle'))]
    bounds(style, spec)
    set_value(get(get(widget, 'name-block'), 'text'), spec['id'])
    for key in ('AutoFitHeight', 'AutoFitWidth'):
        if get(widget, key):
            set_value(get(widget, key), False)
    if spec['kind'] in ('input', 'textarea'):
        if 'text' in spec:
            set_value(get(get(widget, 'TextBlock'), 'text'), spec['text'])
        if 'placeholder' in spec:
            set_value(get(widget, 'PlaceholderText'), spec['placeholder'])
        # RP9 TextBox.Type: 0=text, 1=password, verified against the native enum.
        if 'password' in spec:
            set_value(get(widget, 'Type'), 1 if spec['password'] else 0)
    elif 'text' in spec or get(widget, 'RichTextBlock'):
        rich = get(widget, 'RichTextBlock')
        if rich is None:
            rich = copy.deepcopy(rich_template)
            remap(rich, {value(get(get(rich, 'property-dictionary'), 'text-object-id')): oid(widget),
                         value(get(get(rich, 'property-dictionary'), 'parent-diagram-id')): ref_id(get(root(doc), 'diagram'))})
            put(widget, 'RichTextBlock', rich)
        paragraphs = items(get(get(rich, 'attributed-string'), 'Paragraphs'))
        if 'text' in spec:
            paragraphs[:] = [paragraphs[0]]
            runs = items(get(paragraphs[0], 'Inlines'))
            runs[:] = [runs[0]]
            set_value(get(runs[0], 'Text'), spec['text'])
        for paragraph in paragraphs:
            for run in items(get(paragraph, 'Inlines')):
                if 'font_size' in spec:
                    set_value(get(run, 'Size'), spec['font_size'] * .75)
                if 'font_family' in spec:
                    set_value(get(run, 'Family'), spec['font_family'])
                if 'bold' in spec:
                    set_value(get(run, 'Weight'), 700 if spec['bold'] else 400)
                if 'color' in spec:
                    set_value(get(run, 'Color'), argb(spec['color']))
            if 'align' in spec:
                set_value(get(paragraph, 'HorizontalAlignment'), {'left': 0, 'center': 1, 'right': 2}[spec['align']])
    for key, code in [('fill', -1073741817), ('border_color', -1073741816)]:
        if key in spec:
            p = property_templates[code]
            v = copy.deepcopy(get(p, 'Value'))
            set_value(get(v, 'fill-color'), argb(spec[key]))
            style_prop(style, code, v, p)
    if 'border_width' in spec:
        style_prop(style, -1073741809, spec['border_width'], property_templates[-1073741809])
    for key, code, transform in [('font_size', -1073741822, lambda v: v * .75),
                                 ('font_family', -1073741823, lambda v: v),
                                 ('bold', -1073740823, lambda v: 700 if v else 400),
                                 ('align', -1073741821, lambda v: {'left': 0, 'center': 1, 'right': 2}[v])]:
        if key in spec:
            style_prop(style, code, transform(spec[key]), property_templates[code])
    if 'color' in spec:
        v = copy.deepcopy(get(property_templates[-1073741818], 'Value'))
        set_value(get(v, 'fill-color'), argb(spec['color']))
        style_prop(style, -1073741818, v, property_templates[-1073741818])

def validate_spec(spec):
    if not isinstance(spec, dict):
        raise ValueError('Spec must be a JSON object.')
    allowed_top = {'title', 'pages', 'variables', 'page_alignment'}
    if set(spec) - allowed_top:
        raise ValueError('Unknown document fields: ' + str(set(spec) - allowed_top))
    if not isinstance(spec.get('pages'), list) or not spec['pages']:
        raise ValueError('pages must be a nonempty list.')
    if not isinstance(spec.get('page_alignment', 'center'), str) or spec.get('page_alignment', 'center') not in PAGE_ALIGNMENTS:
        raise ValueError('page_alignment must be left or center.')
    variables = spec.get('variables', {})
    if not isinstance(variables, dict) or any(not isinstance(k, str) or not k or isinstance(v, (dict, list)) or v is None for k, v in variables.items()):
        raise ValueError('variables must map nonempty names to scalar default values.')
    page_ids = set()
    keys = {'id', 'kind', 'x', 'y', 'width', 'height', 'text', 'placeholder', 'password',
            'font_size', 'font_family', 'bold', 'color', 'fill', 'border_color', 'border_width', 'align',
            'events', 'states', 'initial_state', 'fit_to_content', 'fixed', 'scrollbars', 'hidden', 'disabled', 'selected',
            'tooltip', 'native', 'native_style', 'state_styles', 'options', 'multiple', 'selection_group', 'item_widgets', 'columns', 'data'}
    for page in spec['pages']:
        if not isinstance(page, dict) or not isinstance(page.get('widgets'), list):
            raise ValueError('Each page needs a widgets list.')
        if set(page) - {'id', 'name', 'widgets', 'events', 'page_alignment'}:
            raise ValueError('Unsupported page properties.')
        if not isinstance(page.get('page_alignment', 'center'), str) or page.get('page_alignment', 'center') not in PAGE_ALIGNMENTS:
            raise ValueError('page_alignment must be left or center.')
        if not isinstance(page.get('id'), str) or not page['id'] or page['id'] in page_ids:
            raise ValueError('Each page needs a unique nonempty id.')
        page_ids.add(page['id'])
        if not isinstance(page.get('name'), str) or not page['name']:
            raise ValueError('Each page needs a name.')
        if 'events' in page and not isinstance(page['events'], dict):
            raise ValueError('Page events must be an object.')
        widget_ids = set()
        for w in page.get('widgets', []):
            if not isinstance(w, dict):
                raise ValueError('Widgets must be objects.')
            if set(w) - keys:
                raise ValueError('Unsupported widget fields: ' + str(set(w) - keys))
            if w.get('kind') not in KINDS:
                raise ValueError('Supported kinds: ' + ', '.join(KINDS))
            if not isinstance(w.get('id'), str) or not w['id'] or w['id'] in widget_ids:
                raise ValueError('Each widget needs a unique nonempty id within its page.')
            widget_ids.add(w['id'])
            for k in ('x', 'y', 'width', 'height'):
                if isinstance(w.get(k), bool) or not isinstance(w.get(k), (float, int)) or not math.isfinite(w[k]):
                    raise ValueError('Finite numeric ' + k + ' required.')
            if not (0 < w['width'] <= 20000 and 0 < w['height'] <= 20000 and abs(w['x']) <= 20000 and abs(w['y']) <= 20000):
                raise ValueError('Bounds exceed supported document coordinates.')
            for k in ('text', 'placeholder', 'font_family'):
                if k in w and not isinstance(w[k], str):
                    raise ValueError(k + ' must be text.')
            for k in ('fill', 'border_color', 'color'):
                if k in w:
                    argb(w[k])
            if 'align' in w and w['align'] not in ('left', 'center', 'right'):
                raise ValueError('align must be left, center or right.')
            for k in ('font_size', 'border_width'):
                if k in w and (isinstance(w[k], bool) or not isinstance(w[k], (int, float)) or not math.isfinite(w[k]) or w[k] < 0):
                    raise ValueError('Invalid ' + k)
            if 'font_size' in w and not 1 <= w['font_size'] <= 300:
                raise ValueError('font_size must be between 1 and 300 pixels.')
            for k in ('bold', 'password', 'hidden', 'disabled', 'selected', 'fit_to_content', 'fixed', 'multiple'):
                if k in w and not isinstance(w[k], bool):
                    raise ValueError(k + ' must be boolean.')
            if 'password' in w and w['kind'] != 'input':
                raise ValueError('password applies to input widgets.')
            if 'placeholder' in w and w['kind'] not in ('input', 'textarea'):
                raise ValueError('placeholder applies to input/textarea widgets.')
            for key, kinds in [('states', ('panel',)), ('initial_state', ('panel',)),
                               ('fit_to_content', ('panel', 'repeater')), ('fixed', ('panel',)), ('scrollbars', ('panel',)),
                               ('multiple', ('droplist', 'listbox')), ('columns', ('repeater',)),
                               ('data', ('repeater',)), ('item_widgets', ('repeater',))]:
                if key in w and w['kind'] not in kinds:
                    raise ValueError(key + ' does not apply to ' + w['kind'])
            for key in ('native', 'native_style', 'state_styles', 'events'):
                if key in w and not isinstance(w[key], dict):
                    raise ValueError(key + ' must be an object.')
            if any(not isinstance(v, dict) for v in w.get('state_styles', {}).values()):
                raise ValueError('Each state_styles value must be an object of native style properties.')
            if 'initial_state' in w and 'states' not in w:
                raise ValueError('initial_state requires explicit states.')
            if 'options' in w:
                if w['kind'] not in ('droplist', 'listbox') or not isinstance(w['options'], list) or any(not isinstance(o, str) and (not isinstance(o, dict) or set(o) - {'text', 'selected'} or not isinstance(o.get('text'), str)) for o in w['options']):
                    raise ValueError('options requires droplist/listbox and text or {text, selected} items.')
                if any(isinstance(o, dict) and 'selected' in o and not isinstance(o['selected'], bool) for o in w['options']):
                    raise ValueError('Option selected must be boolean.')
            if w['kind'] == 'repeater':
                if not isinstance(w.get('item_widgets'), list) or not isinstance(w.get('data'), list):
                    raise ValueError('repeater requires item_widgets and data lists.')
                columns = w.get('columns')
                if not isinstance(columns, list) or not columns or any(not isinstance(c, str) or not c for c in columns) or len(set(columns)) != len(columns):
                    raise ValueError('repeater requires unique nonempty column names.')
                if any(not isinstance(row, dict) or set(row) - set(columns) for row in w['data']):
                    raise ValueError('repeater row contains unknown columns.')
            if 'states' in w:
                if w['kind'] != 'panel' or not isinstance(w['states'], list) or not w['states']:
                    raise ValueError('states requires a panel and a nonempty list.')
                if any(not isinstance(s, dict) or set(s) - {'name', 'widgets', 'events'} or not isinstance(s.get('name'), str) or not s['name'] or ('events' in s and not isinstance(s['events'], dict)) for s in w['states']):
                    raise ValueError('Panel state fields are name, widgets and events; name must be nonempty.')
                names = [s['name'] for s in w['states']]
                if len(set(names)) != len(names):
                    raise ValueError('Panel state names must be unique.')
                if 'initial_state' in w and w['initial_state'] not in names:
                    raise ValueError('initial_state must name a panel state.')
                for state in w['states']:
                    validate_spec({'pages': [{'id': 'state', 'name': state['name'], 'widgets': state.get('widgets', [])}]})
            if w.get('item_widgets'):
                validate_spec({'pages': [{'id': 'item', 'name': 'item', 'widgets': w['item_widgets']}]})


def spec_widgets(widgets, include_repeater=True):
    for widget in widgets:
        yield widget
        for state in widget.get('states', []):
            yield from spec_widgets(state.get('widgets', []), include_repeater)
        if include_repeater:
            yield from spec_widgets(widget.get('item_widgets', []), include_repeater)


def produce(output, builder):
    """Publish only verified artifacts, preserve existing files, clean staging data."""
    output = output.resolve()
    if output.suffix.lower() != '.rp':
        raise ValueError('Output must have the .rp extension.')
    suffixes = ('.rp', '.manifest.json', '.spec.json', '.verification.json', '.patch.json')
    if any(output.with_suffix(s).exists() for s in suffixes):
        raise FileExistsError('Choose a new output stem; existing files are preserved.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.axure-stage-', dir=output.parent) as temporary:
        staged = Path(temporary) / output.name
        result = builder(staged)
        for suffix in suffixes:
            source = staged.with_suffix(suffix)
            if source.exists():
                with source.open('rb') as src, output.with_suffix(suffix).open('xb') as dst:
                    shutil.copyfileobj(src, dst)
        result['output'] = str(output)
        result.pop('work_directory', None)
        return result

def create(spec, output, install):
    validate_spec(spec)
    return produce(output, lambda staged: _create(spec, staged, install))


def _create(spec, output, install):
    validate_spec(spec)
    output = output.resolve()
    if output.exists():
        raise FileExistsError('Choose a new output file; existing files are preserved.')
    if output.suffix.lower() != '.rp':
        raise ValueError('Output must have the .rp extension.')
    output.parent.mkdir(parents=True, exist_ok=True)
    library = cache(install)
    index = read(library / 'index.json')
    catalogue = locate(library)
    design_stem, design = copy.deepcopy(catalogue['Axure:DesignDocument'][0])
    alignment_prop = alignment_template(design)
    infos = {value(get(o, 'package-name')): o for o in design['objects'] if rtype(o) == 'Axure:PackageInfo'}
    def template(name):
        pkg = value(field(get(infos[name], 'package-id'), 'nbcv'))
        stem = index['root']['children'][pkg.replace('-', '')]['parts']['package']
        return stem, read(library / (stem + '.json'))
    templates = {k: template(name) for k, name in KINDS.items()}
    rich_template = copy.deepcopy(get(templates['text'][1]['objects'][2], 'RichTextBlock'))
    property_templates = {}
    for o in design['objects']:
        if rtype(o) == 'Axure:Style':
            for p in items(get(o, 'PropList')):
                property_templates.setdefault(value(get(p, 'DOAName')), p)
    dm = by_id(design)
    site = dm[ref_id(get(root(design), 'sitemap'))]
    tree = dm[ref_id(get(site, 'tree'))]
    node_template = next(o for o in design['objects'] if rtype(o) == 'Axure:Node')
    node_ref = copy.deepcopy(items(get(tree, 'children'))[0])
    node_table = get(site, 'node-table')
    package_ref = next(copy.deepcopy(v) for _, v in pairs(node_table) if field(v, 'nbcv'))
    old_page_infos = {oid(o) for o in design['objects'] if rtype(o) == 'Axure:PackageInfo' and value(field(get(o, 'package-id'), 'gbcx')) == 'Axure:Page'}
    design['objects'] = [o for o in design['objects'] if oid(o) not in old_page_infos and rtype(o) not in ('Axure:Node', 'Axure:DynamicPanelInfo', 'Axure:PanelDiagramInfo', 'Axure:MasterTreeFolder')]
    package_infos = items(get(root(design), 'PackageInfos'))
    package_infos[:] = [r for r in package_infos if ref_id(r) not in old_page_infos]
    set_value(get(root(design), 'document-type'), 1)
    items(get(tree, 'children')).clear()
    pairs(node_table).clear()
    # Only generator packages remain; page parts are added below.
    generator_ids = {value(field(get(o, 'package-id'), 'nbcv')).replace('-', '') for o in design['objects'] if rtype(o) == 'Axure:PackageInfo'}
    index['root']['children'] = {k: v for k, v in index['root']['children'].items() if k in generator_ids}
    work = output.parent / ('.axure-work-' + uuid.uuid4().hex)
    work.mkdir()
    for path in library.iterdir():
        if path.is_file() and path.suffix in ('.json', '.raw', '.part'):
            shutil.copy2(path, work / path.name)
    manifest = {'title': spec.get('title', output.stem), 'pages': [], 'verification': 'native serializer readback'}
    compiler = NativeCompiler(sys.modules[__name__], library, templates, design, work, index, property_templates, rich_template, node_ref, install)
    compiler.global_variables(spec.get('variables', {}))
    for number, page_spec in enumerate(spec['pages']):
        stem = 'page-' + str(number)
        source_stem, page = copy.deepcopy(templates['rect'])
        page['objects'], ids = clone_records(page['objects'])
        page['root'] = ids[page['root']]
        page['package'] = page['root']
        page_root = root(page)
        alignment = page_spec.get('page_alignment', spec.get('page_alignment', 'center'))
        set_page_alignment(page, alignment, alignment_prop)
        diagram = by_id(page)[ref_id(get(page_root, 'diagram'))]
        old_widgets = [o for o in page['objects'] if rtype(o).startswith('Axure:DiagramObject:') or rtype(o) == 'Axure:Style']
        old_ids = {oid(o) for o in old_widgets}
        page['objects'][:] = [o for o in page['objects'] if oid(o) not in old_ids]
        widget_refs = items(get(diagram, 'diagram-objects'))
        widget_ref_template = copy.deepcopy(widget_refs[0])
        widget_refs.clear()
        drop(page_root, 'LegacyContainedObjects')
        style_cache = get(page_root, 'StyleCache')
        cache_styles = items(get(style_cache, 'Styles'))
        cached_ids = {value(get(get(c, 'Info'), 'Id')) for c in cache_styles}
        for _, cached_source in templates.values():
            for c in items(get(get(root(cached_source), 'StyleCache'), 'Styles')):
                identifier = value(get(get(c, 'Info'), 'Id'))
                if identifier not in cached_ids:
                    cache_styles.append(copy.deepcopy(c))
                    cached_ids.add(identifier)
        page_manifest = {'id': page_spec['id'], 'name': page_spec['name'], 'guid': page['root'],
                         'page_alignment': alignment, 'widgets': []}
        compiler.register_page(page_spec, page, stem)
        for wspec in page_spec.get('widgets', []):
            widget = compiler.add_widget(page, diagram, wspec, page_spec['id'], stem)
            page_manifest['widgets'].append({'id': wspec['id'], 'guid': oid(widget), 'kind': wspec['kind'], **{k: wspec[k] for k in ('x', 'y', 'width', 'height')}})
        write(work / (stem + '.json'), page)
        shutil.copy2(library / (source_stem + '.raw'), work / (stem + '.raw'))
        shutil.copy2(library / (source_stem + '.part'), work / (stem + '.part'))
        index['root']['children'][page['root'].replace('-', '')] = {'parts': {'package': stem}, 'children': compiler.children[stem]}
        info_records, _ = clone_records([infos['Box 1']])
        info = info_records[0]
        for key in ('nbcv', 'Qbcj'):
            set_value(field(get(info, 'package-id'), key), page['root'])
        set_value(get(info, 'package-name'), page_spec['name'])
        items(get(info, 'root-panel-infos'))[:] = compiler.metadata[stem]
        design['objects'].append(info)
        package_infos.append(reference(node_ref, oid(info)))
        ns, _ = clone_records([node_template])
        node = ns[0]
        items(get(node, 'children')).clear()
        put(node, 'parent-node', reference(node_ref, oid(tree)))
        put(node, 'tree', reference(node_ref, oid(tree)))
        design['objects'].append(node)
        nr = reference(node_ref, oid(node))
        items(get(tree, 'children')).append(nr)
        pr = copy.deepcopy(package_ref)
        for key in ('nbcv', 'Qbcj'):
            set_value(field(pr, key), page['root'])
        pairs(node_table).append([copy.deepcopy(nr), pr])
        manifest['pages'].append(page_manifest)
    compiler.finish()
    # Clear library UI workspace state so no removed library pages are reopened.
    settings_stem, settings = copy.deepcopy(catalogue['Axure:DocumentSettings'][0])
    sr = root(settings)
    for key in ('open-tab-package-ids', 'open-tab-object-ids', 'collasped-page-ids', 'collasped-master-folder-ids',
                'dpmanager-editor-package-ids', 'dpmanager-editor-object-ids', 'dpmanager-collapse-object-ids', 'collasped-interaction-treeview-ids'):
        n = get(sr, key)
        if n and field(n, 'zbZy'):
            items(n).clear()
    for key in ('selected-tab-package-id', 'selected-tab-object-id'):
        if get(sr, key):
            set_value(get(sr, key), ZERO)
    # Open the first real page on launch rather than leaving an empty editor.
    set_value(get(sr, 'selected-tab-package-id'), manifest['pages'][0]['guid'])
    for list_key, selected_key in [('open-tab-package-ids', 'selected-tab-package-id'),
                                   ('open-tab-object-ids', 'selected-tab-object-id')]:
        items(get(sr, list_key)).append(copy.deepcopy(get(sr, selected_key)))
    write(work / (settings_stem + '.json'), settings)
    write(work / (design_stem + '.json'), design)
    write(work / 'index.json', index)
    result = bridge(install, 'pack', work, output)
    # Fresh process + full file parse; verify real output coordinates and text.
    inspected = inspect(output, install)
    for page, actual_page in zip(spec['pages'], inspected['pages']):
        if actual_page['page_alignment'] != page.get('page_alignment', spec.get('page_alignment', 'center')):
            raise RuntimeError('Output page alignment mismatch: ' + page['id'])
        actual_by_name = {w['name']: w for w in flatten_widgets(actual_page['widgets'])}
        for requested in spec_widgets(page['widgets']):
            actual = actual_by_name[requested['id']]
            for key in ('x', 'y', 'width', 'height'):
                if actual[key] != requested[key]:
                    raise RuntimeError('Output bounds mismatch: ' + requested['id'])
            if requested.get('text') is not None and actual['text'] != requested['text']:
                raise RuntimeError('Output text mismatch: ' + requested['id'])
            if 'states' in requested and {s['name'] for s in actual['states']} != {s['name'] for s in requested['states']}:
                raise RuntimeError('Output panel state mismatch: ' + requested['id'])
            if requested['kind'] == 'repeater' and actual['data'] != [{c: str(row.get(c, '')) for c in requested['columns']} for row in requested['data']]:
                raise RuntimeError('Output repeater data mismatch: ' + requested['id'])
    manifest['native_packages_verified'] = result['nativePackagesVerified']
    if (HERE.parent / '.cache/public-api/Axure.Document.dll').exists():
        public = verify(output)
        if len(public['pages']) != len(spec['pages']):
            raise RuntimeError('Official API page count mismatch.')
        for page, actual_page in zip(spec['pages'], public['pages']):
            if actual_page['name'] != page['name'] or len(actual_page['widgets']) != len(page['widgets']):
                raise RuntimeError('Official API page or widget count mismatch.')
            actual_by_name = {w['name']: w for w in flatten_widgets(actual_page['widgets'])}
            # The public API exposes panel states, but no repeater item widgets.
            for w in spec_widgets(page['widgets'], include_repeater=False):
                actual = actual_by_name[w['id']]
                for key in ('x', 'y', 'width', 'height'):
                    # Native checkbox height follows font metrics and is reported explicitly.
                    if key == 'height' and w['kind'] in ('checkbox', 'radio'):
                        continue
                    if key in ('width', 'height') and w['kind'] == 'repeater':
                        continue
                    if not math.isclose(actual[key], w[key], abs_tol=0.0001):
                        raise RuntimeError('Official API geometry mismatch: ' + w['id'] + '.' + key)
                for key in ('text', 'bold'):
                    if key in w and actual[key] != w[key]:
                        raise RuntimeError('Official API ' + key + ' mismatch: ' + w['id'])
                if 'font_size' in w and not math.isclose(actual['font_size'], w['font_size'] * .75, abs_tol=0.0001):
                    raise RuntimeError('Official API font size mismatch: ' + w['id'])
        manifest['official_api'] = public
        write(output.with_suffix('.verification.json'), public)
    write(output.with_suffix('.manifest.json'), manifest)
    write(output.with_suffix('.spec.json'), spec)
    return {'ok': True, 'output': str(output), 'pages': len(manifest['pages']),
            'widgets': sum(len(p['widgets']) for p in manifest['pages']),
            'widgets_including_containers': sum(1 for p in spec['pages'] for _ in spec_widgets(p['widgets'])),
            'native_packages_verified': result['nativePackagesVerified'], 'work_directory': str(work)}

def edit(file, patch, output, install):
    if output.resolve() == file.resolve():
        raise FileExistsError('Use a new output file; edit preserves the source.')
    return produce(output, lambda staged: _edit(file, patch, staged, install))


def _edit(file, patch, output, install):
    check_install(install)
    if output.exists() or output.resolve() == file.resolve():
        raise FileExistsError('Use a new output file; edit preserves the source.')
    if (not isinstance(patch, dict) or set(patch) - {'updates', 'page_updates'}
            or not isinstance(patch.get('updates', []), list) or not isinstance(patch.get('page_updates', []), list)
            or not (patch.get('updates') or patch.get('page_updates'))):
        raise ValueError('Patch must contain a nonempty updates or page_updates list.')
    existing = inspect(file, install)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.parent / ('.axure-work-' + uuid.uuid4().hex)
    bridge(install, 'unpack', file, work)
    catalog = locate(work)
    design = catalog['Axure:DesignDocument'][0][1]
    props = {}
    for o in design['objects']:
        if rtype(o) == 'Axure:Style':
            for p in items(get(o, 'PropList')):
                props.setdefault(value(get(p, 'DOAName')), p)
    lib = cache(install)
    paragraph = next(doc for _, doc in locate(lib)['Axure:Page']
                     if get(doc['objects'][2], 'RichTextBlock'))
    rich_template = get(paragraph['objects'][2], 'RichTextBlock')
    idx = read(work / 'index.json')
    source_library = locate(lib)
    library_design = source_library['Axure:DesignDocument'][0][1]
    library_infos = {value(get(o, 'package-name')): o for o in library_design['objects'] if rtype(o) == 'Axure:PackageInfo'}
    library_index = read(lib / 'index.json')
    templates = {}
    for kind, name in KINDS.items():
        pkg = value(field(get(library_infos[name], 'package-id'), 'nbcv'))
        template_stem = library_index['root']['children'][pkg.replace('-', '')]['parts']['package']
        templates[kind] = (template_stem, read(lib / (template_stem + '.json')))
    for o in library_design['objects']:
        if rtype(o) == 'Axure:Style':
            for p in items(get(o, 'PropList')):
                props.setdefault(value(get(p, 'DOAName')), p)
    node_ref = next(items(get(o, 'children'))[0] for o in library_design['objects'] if rtype(o) == 'Axure:Tree' and items(get(o, 'children')))
    compiler = NativeCompiler(sys.modules[__name__], lib, templates, design, work, idx, props, rich_template, node_ref, install)
    compiler.existing(existing)
    changed = {}
    expected = {}
    expected_pages = {}
    for update in patch.get('page_updates', []):
        if (not isinstance(update, dict) or set(update) != {'page', 'set'}
                or not isinstance(update['set'], dict) or set(update['set']) != {'page_alignment'}):
            raise ValueError('Each page update needs page and set:{page_alignment:left|center}.')
        matches = [p for p in existing['pages'] if p['name'] == update['page'] or p['guid'] == update['page']]
        if len(matches) != 1:
            raise ValueError('Page selector is missing or ambiguous.')
        page = matches[0]
        if page['guid'] in expected_pages:
            raise ValueError('Combine changes for one page into a single page update.')
        stem = page['package_stem']
        if stem not in compiler.docs:
            compiler.docs[stem] = read(work / (stem + '.json'))
        doc = changed.setdefault(stem, compiler.docs[stem])
        set_page_alignment(doc, update['set']['page_alignment'], alignment_template(library_design))
        expected_pages[page['guid']] = update['set']['page_alignment']
    allowed = {'x', 'y', 'width', 'height', 'text', 'placeholder', 'password', 'font_size', 'font_family',
               'bold', 'color', 'fill', 'border_color', 'border_width', 'align'}
    for update in patch.get('updates', []):
        if not isinstance(update, dict) or set(update) - {'page', 'widget', 'set', 'events'} or not {'page', 'widget'} <= set(update) or not (update.get('set') or 'events' in update) or not isinstance(update.get('set', {}), dict) or set(update.get('set', {})) - allowed:
            raise ValueError('Each update needs page/widget and supported set fields and/or events.')
        matches = [p for p in existing['pages'] if p['name'] == update['page'] or p['guid'] == update['page']]
        if len(matches) != 1:
            raise ValueError('Page selector is missing or ambiguous.')
        page = matches[0]
        matches = [w for w in flatten_widgets(page['widgets']) if w['name'] == update['widget'] or w['guid'] == update['widget']]
        if len(matches) != 1:
            raise ValueError('Widget selector is missing or ambiguous.')
        widget_summary = matches[0]
        if widget_summary['guid'] in expected:
            raise ValueError('Combine changes for one widget into a single update.')
        kind = {'Axure:DiagramObject:VectorShape': 'rect', 'Axure:DiagramObject:TextBox': 'input',
                'Axure:DiagramObject:Checkbox': 'checkbox', 'Axure:DiagramObject:DynamicPanel': 'panel',
                'Axure:DiagramObject:Repeater': 'repeater'}.get(widget_summary['type'])
        if kind is None:
            raise ValueError('Editing this widget type has not been verified.')
        spec = {k: widget_summary[k] for k in ('x', 'y', 'width', 'height')}
        spec.update({'id': widget_summary['name'], 'kind': kind})
        spec.update(update.get('set', {}))
        if kind != 'repeater':
            validate_spec({'pages': [{'id': 'edit', 'name': 'edit', 'widgets': [spec]}]})
        stem = widget_summary['package_stem']
        doc = changed.setdefault(stem, compiler.docs[stem])
        widget = by_id(doc)[widget_summary['guid']]
        modify_widget(doc, widget, spec, props, rich_template)
        if 'events' in update:
            if not isinstance(update['events'], dict):
                raise ValueError('events must be an object; use {} to remove interactions.')
            if update['events']:
                compiler.event_map(doc, widget, page['guid'], update['events'], False)
            else:
                drop(widget, 'InteractionMap')
        expected[widget_summary['guid']] = spec
    compiler.finish()
    for stem, doc in changed.items():
        write(work / (stem + '.json'), doc)
    result = bridge(install, 'pack', work, output)
    inspected = inspect(output, install)
    for page in inspected['pages']:
        if page['guid'] in expected_pages and page['page_alignment'] != expected_pages[page['guid']]:
            raise RuntimeError('Edited page alignment mismatch: ' + str(page['name']))
    reread = {w['guid']: w for p in inspected['pages'] for w in flatten_widgets(p['widgets'])}
    for guid, spec in expected.items():
        for key in ('x', 'y', 'width', 'height', 'text', 'placeholder', 'password'):
            if key in spec and reread[guid][key] != spec[key]:
                raise RuntimeError('Edited output mismatch: ' + spec['id'] + '.' + key)
    result['official_api_verified'] = False
    if (HERE.parent / '.cache/public-api/Axure.Document.dll').exists():
        public = verify(output)
        result['official_api_verified'] = True
        write(output.with_suffix('.verification.json'), public)
    write(output.with_suffix('.patch.json'), patch)
    return result

def inspect(file, install):
    file = Path(file).resolve()
    with tempfile.TemporaryDirectory(prefix='.axure-inspect-', dir=file.parent) as temporary:
        return _inspect(file, install, Path(temporary) / 'packages')


def flatten_widgets(widgets):
    for widget in widgets:
        yield widget
        for state in widget.get('states', []):
            yield from flatten_widgets(state['widgets'])
        yield from flatten_widgets(widget.get('children', []))


def _inspect(file, install, folder):
    bridge(install, 'unpack', file, folder)
    found = locate(folder)
    design = found['Axure:DesignDocument'][0][1]
    names = {value(field(get(o, 'package-id'), 'nbcv')): value(get(o, 'package-name'))
             for o in design['objects'] if rtype(o) == 'Axure:PackageInfo'}
    result = {'file': str(file), 'document_type': value(get(root(design), 'document-type')), 'pages': [], 'variables': {}}
    settings = root(found['Axure:DocumentSettings'][0][1])
    result['editor'] = {'initial_page': value(get(settings, 'selected-tab-package-id')),
                        'open_pages': [value(p) for p in items(get(settings, 'open-tab-package-ids'))]}
    dm = by_id(design)
    variable_set = next((o for o in design['objects'] if rtype(o) == 'Axure:GlobalVariableSet'), None)
    if variable_set:
        for reference_node in items(get(variable_set, 'global-variables')):
            variable = dm[ref_id(reference_node)]
            result['variables'][value(get(variable, 'name'))] = value(get(variable, 'default-value'))
    idx = read(folder / 'index.json')
    packages = {}
    def collect(node):
        for identifier, child in node.get('children', {}).items():
            if child.get('parts', {}).get('package'):
                packages[str(uuid.UUID(identifier))] = child['parts']['package']
            collect(child)
    collect(idx['root'])
    docs = {}
    def document(stem):
        if stem not in docs:
            docs[stem] = read(folder / (stem + '.json'))
        return docs[stem]
    def widgets(doc, diagram, stem, depth=0):
        if depth > 20:
            raise ValueError('Container nesting exceeds 20 levels.')
        m = by_id(doc)
        output = []
        for widget_ref in items(get(diagram, 'diagram-objects')):
            w = m[ref_id(widget_ref)]
            style = m[ref_id(get(w, 'MyStyle'))]
            ps = {value(get(p, 'DOAName')): value(get(p, 'Value')) for p in items(get(style, 'PropList'))}
            xy, wh = ps.get(-1073741723, {'X':0,'Y':0}), ps.get(-1073741719, {'Width':0,'Height':0})
            rich = get(w, 'RichTextBlock')
            text = ''
            if rich:
                text = '\n'.join(''.join(value(get(run, 'Text')) or '' for run in items(get(p, 'Inlines')))
                                 for p in items(get(get(rich, 'attributed-string'), 'Paragraphs')))
            elif get(w, 'TextBlock'):
                text = value(get(get(w, 'TextBlock'), 'text'))
            summary = {'guid': oid(w), 'name': value(get(get(w, 'name-block'), 'text')), 'type': rtype(w),
                       'text': text, 'x': float(xy['X']), 'y': float(xy['Y']),
                       'width': float(wh['Width']), 'height': float(wh['Height']), 'package_stem': stem}
            ix = get(w, 'InteractionMap')
            if ix:
                ixmap = m[ref_id(ix)]
                summary['interaction_records'] = [
                    {'type': rtype(m[ref_id(v)]), 'fields': value(field(m[ref_id(v)], 'ebL0'))}
                    for _, v in pairs(get(ixmap, 'node-table'))]
            if get(w, 'PlaceholderText'):
                summary.update(placeholder=value(get(w, 'PlaceholderText')), password=value(get(w, 'Type')) == 1)
            if get(w, 'panel-diagrams'):
                summary['states'] = []
                for pr in items(get(w, 'panel-diagrams')):
                    identifier = value(field(pr, 'nbcv'))
                    if identifier not in packages:
                        raise ValueError('Missing panel state package: ' + identifier)
                    state_stem = packages[identifier]
                    state_doc = document(state_stem)
                    state_diagram = by_id(state_doc)[ref_id(get(root(state_doc), 'diagram'))]
                    summary['states'].append({'name': value(get(state_diagram, 'Name')), 'guid': identifier,
                                              'widgets': widgets(state_doc, state_diagram, state_stem, depth+1)})
            if get(w, 'BaseDiagram'):
                summary['children'] = widgets(doc, m[ref_id(get(w, 'BaseDiagram'))], stem, depth+1)
                dataset = m[ref_id(get(w, 'Data'))]
                columns = {value(get(m[ref_id(c)], 'variable-id')): value(get(m[ref_id(c)], 'name')) for c in items(get(dataset, 'columns'))}
                summary['columns'] = list(columns.values())
                summary['data'] = [{columns[value(get(m[ref_id(e)], 'column-id'))]: value(get(m[ref_id(e)], 'value'))
                                    for e in items(get(m[ref_id(row)], 'elements'))} for row in items(get(dataset, 'rows'))]
            output.append(summary)
        return output
    for package, node in idx['root'].get('children', {}).items():
        stem = node.get('parts', {}).get('package')
        if not stem or not (folder / (stem + '.json')).exists():
            continue
        doc = document(stem)
        if rtype(root(doc)) != 'Axure:Page':
            continue
        pguid = str(uuid.UUID(package))
        diagram = by_id(doc)[ref_id(get(root(doc), 'diagram'))]
        result['pages'].append({'guid': pguid, 'name': names.get(pguid), 'package_stem': stem,
                                'page_alignment': page_alignment(doc, design), 'widgets': widgets(doc, diagram, stem)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--axure-dir', type=Path, default=Path(os.environ.get('AXURE9_DIR', DEFAULT_INSTALL)))
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor')
    schemas = sub.add_parser('models'); schemas.add_argument('--model'); schemas.add_argument('--enum')
    c = sub.add_parser('create'); c.add_argument('--spec', required=True, type=Path); c.add_argument('--output', required=True, type=Path)
    i = sub.add_parser('inspect'); i.add_argument('file', type=Path)
    v = sub.add_parser('verify'); v.add_argument('file', type=Path); v.add_argument('--render-dir', type=Path)
    h = sub.add_parser('export-html'); h.add_argument('file', type=Path); h.add_argument('--output', required=True, type=Path)
    e = sub.add_parser('edit'); e.add_argument('--input', required=True, type=Path); e.add_argument('--patch', required=True, type=Path); e.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            result = {'ok': True, 'version': '9.0.0.3744', 'sha256': check_install(args.axure_dir), 'install': str(args.axure_dir), 'ui_automation': False,
                      'official_read_api': (HERE.parent / '.cache/public-api/Axure.Document.dll').is_file()}
        elif args.command == 'models':
            check_install(args.axure_dir)
            schema = model_schema(args.axure_dir)
            if args.model:
                entries = [x for x in read(schema / 'catalog.json') if x.get('file', '').removesuffix('.json') == args.model]
                if len(entries) != 1:
                    raise ValueError('Unknown native model.')
                doc = read(schema / entries[0]['file'])
                result = {'model': entries[0]['type'], 'records': [{'type': rtype(o), 'fields': value(field(o, 'ebL0'))} for o in doc['objects']]}
            elif args.enum:
                result = read(schema / 'enums.json')[args.enum]
            else:
                result = {'models': read(schema / 'catalog.json'), 'enums': list(read(schema / 'enums.json'))}
        elif args.command == 'create':
            result = create(read(args.spec), args.output, args.axure_dir)
        elif args.command == 'edit':
            result = edit(args.input, read(args.patch), args.output, args.axure_dir)
        elif args.command == 'verify':
            result = verify(args.file, args.render_dir)
        elif args.command == 'export-html':
            result = export_html(args.file, args.output, args.axure_dir)
        else:
            check_install(args.axure_dir)
            result = inspect(args.file, args.axure_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    sys.exit(main())
