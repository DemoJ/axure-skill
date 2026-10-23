"""RP9 native model compiler: containers, event trees, expressions and actions."""
import copy
from pathlib import Path
import shutil
import re

from model import *


EXTRA_KINDS = {
    'panel': 'Dynamic Panel', 'repeater': 'Repeater', 'ellipse': 'Ellipse',
    'textarea': 'Text Area', 'radio': 'Radio Button', 'droplist': 'Droplist',
    'listbox': 'List Box', 'hotspot': 'Hot Spot', 'iframe': 'Inline Frame',
    'line': 'Horizontal Line', 'vline': 'Vertical Line', 'arrow': 'Horizontal Arrow',
    'placeholder': 'Placeholder', 'table': 'Table', 'tree': 'Tree',
    'menu': 'Classic Menu - Horizontal', 'vmenu': 'Classic Menu - Vertical',
    'image': 'Image', 'heading1': 'Heading 1', 'heading2': 'Heading 2',
    'heading3': 'Heading 3', 'label': 'Label', 'link': 'Link Button',
}


class NativeCompiler:
    def __init__(self, api, library, templates, design, work, index, props, rich, node_ref, install):
        self.a, self.library, self.templates = api, library, templates
        self.design, self.work, self.index = design, work, index
        self.props, self.rich, self.ref = props, rich, node_ref
        self.schema = api.model_schema(install)
        self.models = {Path(x['file']).stem: x for x in api.read(self.schema / 'catalog.json') if 'file' in x}
        self.enums = api.read(self.schema / 'enums.json')
        self.symbols, self.pages, self.docs, self.pending = {}, {}, {}, []
        self.children, self.metadata, self.panel_states = {}, {}, {}
        self.counter = 0
        source = api.locate(library)
        self.state_source = source['Axure:PanelState'][0]
        self.node_template = next(o for o in design['objects'] if rtype(o) == 'Axure:Tree')
        # The design's node template was removed by the basic scaffolding step.
        any_design = api.locate(library)['Axure:DesignDocument'][0][1]
        self.node_template = next(o for o in any_design['objects'] if rtype(o) == 'Axure:Node')
        self.panel_info_template = next(o for o in any_design['objects'] if rtype(o) == 'Axure:DynamicPanelInfo')
        self.state_info_template = next(o for o in any_design['objects'] if rtype(o) == 'Axure:PanelDiagramInfo')
        self.path_template = next(o for _, d in source['Axure:Page'] for o in d['objects'] if rtype(o) == 'Axure:DiagramObjectPath')
        self.map_source = next(d for _, d in source['Axure:Page'] if get(root(d), 'interactionmap'))
        self.variables = {}
        self.page_stems = {}
        self.repeater_stack, self.repeater_columns = [], {}
        repeater_source = self.templates['repeater'][1]
        self.expression_template = next(o for o in repeater_source['objects'] if rtype(o) == 'Axure:Expr:StringLiteral')
        self.identifier_template = next(o for o in repeater_source['objects'] if rtype(o) == 'Axure:Expr:TextVariableIdentifier')

    def existing(self, inspection):
        """Register the original graph for event edits, preserving all other records."""
        mapping = by_id(self.design)
        variables = next(o for o in self.design['objects'] if rtype(o) == 'Axure:GlobalVariableSet')
        for vr in items(get(variables, 'global-variables')):
            record = mapping[ref_id(vr)]
            self.variables[value(get(record, 'name'))] = value(get(record, 'variable-id'))
        def document(stem):
            if stem not in self.docs:
                self.docs[stem] = self.a.read(self.work / (stem + '.json'))
            return self.docs[stem]
        def register(widgets, page_id, repeaters):
            for w in widgets:
                doc = document(w['package_stem'])
                record = by_id(doc)[w['guid']]
                symbol = {'record': record, 'doc': doc, 'spec': {}, 'repeaters': repeaters}
                self.symbols[(page_id, w['guid'])] = symbol
                key = (page_id, w['name'])
                self.symbols[key] = symbol if key not in self.symbols else None
                if w.get('states'):
                    states = {state['name']: state['guid'] for state in w['states']}
                    self.panel_states[(page_id, w['guid'])] = states
                    self.panel_states[key] = states
                    for state in w['states']: register(state['widgets'], page_id, repeaters)
                if 'data' in w:
                    dataset = by_id(doc)[ref_id(get(record, 'Data'))]
                    cols = {value(get(by_id(doc)[ref_id(c)], 'name')): value(get(by_id(doc)[ref_id(c)], 'variable-id')) for c in items(get(dataset, 'columns'))}
                    self.repeater_columns[(page_id, w['guid'])] = cols
                    self.repeater_columns[key] = cols
                    register(w.get('children', []), page_id, repeaters + [w['guid']])
        for page in inspection['pages']:
            self.pages[page['guid']] = page['guid']
            self.pages[page['name']] = page['guid']
            register(page['widgets'], page['guid'], [])

    def global_variables(self, variables):
        variable_set = next(o for o in self.design['objects'] if rtype(o) == 'Axure:GlobalVariableSet')
        template = next(o for o in self.design['objects'] if rtype(o) == 'Axure:GlobalVariable')
        refs = items(get(variable_set, 'global-variables'))
        refs.clear()
        for name, default in variables.items():
            variable = self.record(self.design, template)
            identifier = new_id()
            self.variables[name] = identifier
            self.set(variable, 'name', name)
            self.set(variable, 'variable-id', identifier)
            self.set(variable, 'default-value', str(default))
            refs.append(reference(self.ref, oid(variable)))

    def clone(self, doc, model):
        if model not in self.models:
            raise ValueError('Unknown or unavailable native model: ' + str(model))
        source = self.a.read(self.schema / self.models[model]['file'])
        records, mapping = clone_records(source['objects'])
        doc['objects'].extend(records)
        return next(o for o in records if oid(o) == mapping[source['root']])

    def record(self, doc, template):
        records, _ = clone_records([template])
        doc['objects'].extend(records)
        return records[0]

    def set(self, record, key, val):
        existing = get(record, key)
        if existing is None:
            raise ValueError('Native field does not exist: ' + rtype(record) + '.' + key)
        set_value(existing, val)

    def link(self, record, key, target):
        put(record, key, reference(self.ref, oid(target) if isinstance(target, dict) else target))

    def enum(self, family, name):
        values = self.enums[family]
        if isinstance(name, int) and name in values.values():
            return name
        if name not in values:
            raise ValueError('Unknown enum ' + family + ': ' + str(name))
        return values[name]

    def closure(self, source, identifier):
        mapping, found = by_id(source), set()
        def visit(guid):
            if guid in found or guid not in mapping:
                return
            found.add(guid)
            for node in self.a.walk(mapping[guid]):
                if field(node, 'abPc') is not None:
                    visit(ref_id(node))
        visit(identifier)
        return [o for o in source['objects'] if oid(o) in found]

    def register_page(self, spec, doc, stem):
        self.page_stems[spec['id']] = stem
        self.pages[spec['id']] = doc['root']
        self.docs[stem] = doc
        self.children[stem] = {}
        self.metadata[stem] = []
        if spec.get('events'):
            self.pending.append((doc, root(doc), spec['id'], spec['events'], True))

    def add_widget(self, doc, diagram, spec, page_id, stem):
        source_stem, source = self.templates[spec['kind']]
        original_diagram = by_id(source)[ref_id(get(root(source), 'diagram'))]
        original_widget_id = ref_id(items(get(original_diagram, 'diagram-objects'))[0])
        records, mapping = clone_records(self.closure(source, original_widget_id))
        remap(records, {oid(original_diagram): oid(diagram)})
        doc['objects'].extend(records)
        widget = by_id(doc)[mapping[original_widget_id]]
        self.a.modify_widget(doc, widget, spec, self.props, self.rich)
        if 'hidden' in spec:
            style = by_id(doc)[ref_id(get(widget, 'MyStyle'))]
            code = -1073741824 + self.enums['Axure.Constants.PName']['VISIBLE']
            self.a.style_prop(style, code, not spec['hidden'], self.props[code])
        style = by_id(doc)[ref_id(get(widget, 'MyStyle'))]
        if spec.get('native_style'):
            self.style_fields(style, spec['native_style'])
        for state, fields in spec.get('state_styles', {}).items():
            if state not in ('MouseOver', 'MouseDown', 'Selected', 'Disabled', 'Focused', 'SelectedFocused', 'SelectedDisabled', 'Hint', 'HintSelected', 'HintDisabled', 'Custom1', 'Custom2', 'Custom3', 'Custom4', 'Custom5'):
                raise ValueError('Unknown interaction style state: ' + state)
            effect = self.record(doc, style)
            self.set(effect, 'Id', new_id())
            self.set(effect, 'style-name', state)
            items(get(effect, 'PropList')).clear()
            self.style_fields(effect, fields)
            code = -1073741803
            prop = next((p for p in items(get(style, 'PropList')) if value(get(p, 'DOAName')) == code), None)
            if prop is None:
                prop = copy.deepcopy(self.props[code]); items(get(style, 'PropList')).append(prop)
                pairs(get(prop, 'Value')).clear()
            put(get(prop, 'Value'), state, reference(self.ref, oid(effect)))
        items(get(diagram, 'diagram-objects')).append(reference(self.ref, oid(widget)))
        symbol = (page_id, spec['id'])
        if symbol in self.symbols:
            raise ValueError('Widget IDs must be unique across a page and its containers: ' + spec['id'])
        self.symbols[symbol] = {'record': widget, 'doc': doc, 'spec': spec, 'repeaters': self.repeater_stack[:]}
        # Default library examples can carry demo events and adaptive variants.
        # New widgets start from the requested base design, not those examples.
        if get(widget, 'InteractionMap'):
            drop(widget, 'InteractionMap')
        if get(widget, 'AdaptiveStyles'):
            items(get(widget, 'AdaptiveStyles')).clear()
        for key, native in [('hidden', 'VisibleFromSettings'), ('disabled', 'Disabled'), ('selected', 'Selected'), ('tooltip', 'tooltip')]:
            if key in spec and get(widget, native) is not None:
                self.set(widget, native, not spec[key] if key == 'hidden' else spec[key])
        if spec.get('events'):
            self.pending.append((doc, widget, page_id, spec['events'], False))
        if spec['kind'] == 'panel':
            self.add_states(doc, widget, spec, page_id, stem)
        elif spec['kind'] == 'repeater':
            # Native default repeater graph contains its base diagram and real dataset.
            self.repeater(doc, widget, spec, page_id, stem)
        if 'selection_group' in spec:
            self.set(widget, 'SelectedStyleGroup', spec['selection_group'])
        if 'options' in spec:
            options = items(get(widget, 'list-options')); options.clear()
            self.set(widget, 'multiple', spec.get('multiple', False))
            for option_spec in spec['options']:
                option = self.clone(doc, 'SelectableListItem')
                self.set(option, 'object', option_spec if isinstance(option_spec, str) else option_spec['text'])
                self.set(option, 'selected', False if isinstance(option_spec, str) else option_spec.get('selected', False))
                options.append(reference(self.ref, oid(option)))
        if spec.get('native'):
            self.configure(doc, widget, spec['native'], page_id)
        return widget

    def style_fields(self, style, fields):
        for name, val in fields.items():
            code = -1073741824 + self.enum('Axure.Constants.PName', name)
            if code not in self.props:
                raise ValueError('No native value template for style property: ' + name)
            prop = copy.deepcopy(self.props[code])
            target = get(prop, 'Value')
            if isinstance(val, str) and val.startswith('#') and field(target, 'ebL0'):
                set_value(get(target, 'fill-color'), self.a.argb(val))
            elif isinstance(val, dict):
                for key, child in val.items():
                    node = get(target, key)
                    if node is None: raise ValueError('Unknown structured style field: ' + name + '.' + key)
                    if key == 'Color' and isinstance(child, str) and child.startswith('#'):
                        child = self.a.argb(child)
                    set_value(node, child)
            else:
                set_value(target, val)
            self.a.style_prop(style, code, target, prop)

    def add_states(self, owner_doc, widget, spec, page_id, owner_stem):
        state_refs = items(get(widget, 'panel-diagrams'))
        package_ref = copy.deepcopy(state_refs[0])
        state_refs.clear()
        panel_info = self.record(self.design, self.panel_info_template)
        self.set(panel_info, 'name', spec['id'])
        self.set(panel_info, 'object-id', oid(widget))
        metadata_refs = items(get(panel_info, 'panel-diagram-infos'))
        metadata_refs.clear()
        self.metadata[owner_stem].append(reference(self.ref, oid(panel_info)))
        self.panel_states[(page_id, spec['id'])] = {}
        states = spec.get('states', [{'name': 'State1', 'widgets': []}])
        names = [s['name'] for s in states]
        if spec.get('initial_state'):
            first = names.index(spec['initial_state'])
            states = [states[first]] + states[:first] + states[first+1:]
        for state_spec in states:
            self.counter += 1
            stem = 'state-' + str(self.counter)
            source_stem, doc = copy.deepcopy(self.state_source)
            doc['objects'], mapping = clone_records(doc['objects'])
            doc['root'] = mapping[doc['root']]
            diagram = by_id(doc)[ref_id(get(root(doc), 'diagram'))]
            doc['package'] = oid(diagram)
            self.set(diagram, 'Name', state_spec['name'])
            items(get(diagram, 'diagram-objects')).clear()
            if get(root(doc), 'StyleCache') is None:
                put(root(doc), 'StyleCache', copy.deepcopy(get(root(owner_doc), 'StyleCache')))
            self.docs[stem], self.children[stem], self.metadata[stem] = doc, {}, []
            for child in state_spec.get('widgets', []):
                self.add_widget(doc, diagram, child, page_id, stem)
            pr = copy.deepcopy(package_ref)
            for field_name in ('nbcv', 'Qbcj'):
                set_value(field(pr, field_name), doc['package'])
            state_refs.append(pr)
            self.panel_states[(page_id, spec['id'])][state_spec['name']] = doc['package']
            state_info = self.record(self.design, self.state_info_template)
            self.set(state_info, 'name', state_spec['name'])
            put(state_info, 'PackageId', copy.deepcopy(pr))
            items(get(state_info, 'contained-panel-infos'))[:] = self.metadata[stem]
            metadata_refs.append(reference(self.ref, oid(state_info)))
            # RP9 locates every state package relative to the owning PAGE,
            # including states belonging to panels nested several levels deep.
            self.children[self.page_stems[page_id]][doc['package'].replace('-', '')] = {'parts': {'package': stem}}
            shutil.copy2(self.library / (source_stem + '.raw'), self.work / (stem + '.raw'))
            shutil.copy2(self.library / (source_stem + '.part'), self.work / (stem + '.part'))
            if state_spec.get('events'):
                self.pending.append((doc, root(doc), page_id, state_spec['events'], True))
        for key, native in [('fit_to_content', 'fit-to-content'), ('fixed', 'is-fixed'), ('scrollbars', 'scrollbars')]:
            if key in spec:
                self.set(widget, native, spec[key])

    def repeater(self, doc, widget, spec, page_id, stem):
        mapping = by_id(doc)
        diagram = mapping[ref_id(get(widget, 'BaseDiagram'))]
        self.set(widget, 'FitToContent', spec.get('fit_to_content', False))
        panel_info = self.record(self.design, self.panel_info_template)
        self.set(panel_info, 'name', spec['id']); self.set(panel_info, 'object-id', oid(widget))
        self.set(panel_info, 'subdiagram-parent-type', 'Axure:DiagramObject:Repeater')
        state_info = self.record(self.design, self.state_info_template)
        self.set(state_info, 'name', '')
        self.set(state_info, 'IsSubPackage', False)
        pr = get(state_info, 'PackageId')
        for key in ('nbcv', 'Qbcj'): set_value(field(pr, key), oid(diagram))
        items(get(state_info, 'contained-panel-infos')).clear()
        items(get(panel_info, 'panel-diagram-infos'))[:] = [reference(self.ref, oid(state_info))]
        self.metadata[stem].append(reference(self.ref, oid(panel_info)))
        items(get(diagram, 'diagram-objects')).clear()
        self.repeater_stack.append(spec['id'])
        try:
            for child in spec['item_widgets']:
                self.add_widget(doc, diagram, child, page_id, stem)
        finally:
            self.repeater_stack.pop()
        dataset = mapping[ref_id(get(widget, 'Data'))]
        columns, rows = items(get(dataset, 'columns')), items(get(dataset, 'rows'))
        col_template = copy.deepcopy(mapping[ref_id(columns[0])])
        row_template = copy.deepcopy(mapping[ref_id(rows[0])])
        element_template = copy.deepcopy(mapping[ref_id(items(get(row_template, 'elements'))[0])])
        columns.clear(); rows.clear()
        names = spec['columns']
        ids = {}
        self.repeater_columns[(page_id, spec['id'])] = ids
        for name in names:
            col = self.record(doc, col_template)
            ids[name] = new_id()
            self.set(col, 'name', name); self.set(col, 'variable-id', ids[name])
            columns.append(reference(self.ref, oid(col)))
        for data in spec['data']:
            row = self.record(doc, row_template)
            elements = items(get(row, 'elements')); elements.clear()
            for name in names:
                element = self.record(doc, element_template)
                self.set(element, 'column-id', ids[name]); self.set(element, 'value', str(data.get(name, '')))
                elements.append(reference(self.ref, oid(element)))
            rows.append(reference(self.ref, oid(row)))

    def path(self, doc, page_id, target):
        if not self.symbols.get((page_id, target)):
            raise ValueError('Unknown or ambiguous widget target (use its GUID): ' + str(target))
        path = self.record(doc, self.path_template)
        items(get(path, 'rdo-path')).clear(); items(get(path, 'repeater-path')).clear()
        symbol = self.symbols[(page_id, target)]
        for repeater in symbol['repeaters']:
            guid_pair = copy.deepcopy(get(path, 'object-id'))
            for key in ('abcZ', 'wbc6'):
                set_value(field(guid_pair, key), oid(self.symbols[(page_id, repeater)]['record']))
            items(get(path, 'repeater-path')).append(guid_pair)
        guid = oid(symbol['record'])
        for key in ('abcZ', 'wbc6'):
            set_value(field(get(path, 'object-id'), key), guid)
        return path

    def expr(self, doc, spec, page_id):
        if isinstance(spec, dict):
            forms = {'widget': {'widget'}, 'widget_text': {'widget_text'}, 'var': {'var'},
                     'variable_ref': {'variable_ref'}, 'call': {'call', 'args'},
                     'op': {'op', 'left', 'right'}, 'expr': {'expr', 'repeater'},
                     'native_model': {'native_model', 'fields'}}
            chosen = [k for k in forms if k in spec]
            if len(chosen) != 1 or set(spec) - forms[chosen[0]]:
                raise ValueError('Invalid or unknown expression fields: ' + str(spec))
        elif spec is None or isinstance(spec, list):
            raise ValueError('Expression must be a scalar or expression object.')
        if isinstance(spec, bool):
            result = self.clone(doc, 'BooleanLiteral'); self.set(result, 'value', str(spec))
        elif not isinstance(spec, dict):
            result = self.clone(doc, 'StringLiteral'); self.set(result, 'value', str(spec))
        elif 'widget' in spec:
            result = self.clone(doc, 'DiagramObjectPathLiteral')
            self.link(result, 'value', self.path(doc, page_id, spec['widget']))
        elif 'widget_text' in spec:
            return self.expr(doc, {'call': 'GetWidgetText', 'args': [{'widget': spec['widget_text']}]}, page_id)
        elif 'var' in spec:
            return self.expr(doc, {'call': 'GetGlobalVariableValue', 'args': [{'variable_ref': spec['var']}]}, page_id)
        elif 'variable_ref' in spec:
            name = spec['variable_ref']
            if name not in self.variables:
                raise ValueError('Unknown variable: ' + name)
            result = self.clone(doc, 'GlobalVariableLiteral')
            self.set(result, 'value', self.variables[name]); self.set(result, 'variable-name', name)
        elif 'call' in spec:
            result = self.clone(doc, 'FCall'); self.set(result, 'function-name', spec['call'])
            args = items(get(result, 'args')); args.clear()
            for arg in spec.get('args', []):
                args.append(reference(self.ref, oid(self.expr(doc, arg, page_id))))
        elif 'op' in spec:
            result = self.clone(doc, 'BinaryExpr')
            self.set(result, 'operation', self.enum('Axure.Platform.LogicalComparison', spec['op']))
            self.link(result, 'left-expr', self.expr(doc, spec['left'], page_id))
            self.link(result, 'right-expr', self.expr(doc, spec['right'], page_id))
        elif 'expr' in spec:
            result = self.record(doc, self.expression_template)
            self.set(result, 'value', spec['expr'])
            identifiers = items(get(result, 'variable-identifiers')); identifiers.clear()
            if spec.get('repeater'):
                repeater_symbol = self.symbols[(page_id, spec['repeater'])]
                dataset_id = ref_id(get(repeater_symbol['record'], 'Data'))
                if repeater_symbol['doc'] is not doc:
                    known = by_id(doc)
                    doc['objects'].extend(copy.deepcopy(o) for o in self.closure(repeater_symbol['doc'], dataset_id) if oid(o) not in known)
                self.link(result, 'repeater-scope', dataset_id)
            else:
                self.link(result, 'repeater-scope', ZERO)
            for match in set(re.findall(r'\bItem\.([A-Za-z_][A-Za-z_0-9]*)', spec['expr'])):
                column = self.repeater_columns[(page_id, spec['repeater'])][match]
                identifier = self.record(doc, self.identifier_template)
                self.set(identifier, 'Id', column); self.set(identifier, 'Name', 'Item.' + match)
                self.link(identifier, 'Expr', result)
                identifiers.append(reference(self.ref, oid(identifier)))
            for name, guid in self.variables.items():
                if re.search(r'\b' + re.escape(name) + r'\b', spec['expr']):
                    identifier = self.record(doc, self.identifier_template)
                    self.set(identifier, 'Id', guid); self.set(identifier, 'Name', name)
                    self.link(identifier, 'Expr', result)
                    identifiers.append(reference(self.ref, oid(identifier)))
        elif 'native_model' in spec:
            if not self.models.get(spec['native_model'], {}).get('type', '').startswith('Axure.DocumentModel.Expressions.'):
                raise ValueError('native_model must name an exported expression model.')
            result = self.clone(doc, spec['native_model'])
            self.configure(doc, result, spec.get('fields', {}), page_id)
        else:
            raise ValueError('Unsupported expression: ' + str(spec))
        return result

    def configure(self, doc, record, fields, page_id):
        """Typed native escape hatch; fields come from exported local model schemas."""
        for key, val in fields.items():
            node = get(record, key)
            if node is None:
                raise ValueError('Unknown native field ' + rtype(record) + '.' + key)
            if isinstance(val, dict) and '$expr' in val:
                self.link(record, key, self.expr(doc, val['$expr'], page_id))
            elif isinstance(val, dict) and '$widget_path' in val:
                self.link(record, key, self.path(doc, page_id, val['$widget_path']))
            elif isinstance(val, dict):
                # Structured native value (point, color, package ID, etc.).
                for child, scalar_value in val.items():
                    child_node = get(node, child) if 'd' in node or field(node, 'ebL0') else field(node, child)
                    if child_node is None:
                        raise ValueError('Unknown native subfield ' + key + '.' + child)
                    set_value(child_node, scalar_value)
            else:
                set_value(node, val)

    def mapped_action(self, doc, page_id, spec, model, paths_key, infos_key, info_model):
        action = self.clone(doc, model)
        paths, infos = items(get(action, paths_key)), items(get(action, infos_key))
        targets = spec.get('targets', [spec.get('target')])
        for target in targets:
            path = self.path(doc, page_id, target)
            info = self.clone(doc, info_model)
            paths.append(reference(self.ref, oid(path))); infos.append(reference(self.ref, oid(info)))
            yield action, info

    def action(self, doc, spec, page_id):
        if not isinstance(spec, dict) or not isinstance(spec.get('type'), str):
            raise ValueError('Action requires a type.')
        kind = spec['type']
        fields = {
            'open_page': 'page window', 'open_url': 'url window', 'back': 'window', 'reload': 'window',
            'wait': 'ms', 'close': '', 'focus': 'target select_text', 'scroll_to': 'target duration direction',
            'set_text': 'target value', 'set_selected': 'target value', 'set_variable': 'variable value',
            'function': 'name args', 'set_panel_state': 'target state value mode show duration enter_animation exit_animation native_info',
            'show': 'target targets duration show_type animation native_info',
            'hide': 'target targets duration show_type animation native_info',
            'toggle': 'target targets duration show_type animation native_info',
            'move': 'target targets x y mode duration native_info', 'resize': 'target targets width height duration anchor native_info',
            'opacity': 'target targets value duration native_info', 'enable': 'target targets native_info',
            'disable': 'target targets native_info', 'rotate': 'target targets degrees clockwise duration offset_x offset_y anchor native_info',
            'front': 'target targets native_info', 'back_order': 'target targets native_info',
            'filter': 'target targets name replace value native_info', 'sort': 'target column name ascending toggle sort_type native_info',
            'items_per_page': 'target targets unlimited value native_info', 'repeater_page': 'target targets mode value native_info',
            'native': 'model fields target targets paths_field infos_field info_model info',
        }
        if kind not in fields or set(spec) - ({'type'} | set(fields[kind].split())):
            raise ValueError('Unknown action or action fields: ' + str(spec))
        if 'targets' in spec and ('target' in spec or not isinstance(spec['targets'], list) or not spec['targets']):
            raise ValueError('Use a nonempty targets list or one target.')
        if 'target' in spec and (not isinstance(spec['target'], str) or not spec['target']):
            raise ValueError('target must be one widget ID string; use targets:["id1","id2"] for multiple widgets.')
        if 'targets' in spec and any(not isinstance(t, str) or not t for t in spec['targets']):
            raise ValueError('Each targets entry must be a nonempty widget ID string.')
        if 'duration' in spec and (isinstance(spec['duration'], bool) or not isinstance(spec['duration'], (int, float)) or spec['duration'] < 0):
            raise ValueError('duration must be nonnegative milliseconds.')
        if kind == 'set_panel_state' and spec.get('mode', 'Diagram') == 'Diagram' and 'state' not in spec:
            raise ValueError('Diagram mode requires a named panel state.')
        if kind == 'native' and spec.get('info_model') and not {'paths_field', 'infos_field'} <= set(spec):
            raise ValueError('Mapped native actions require paths_field and infos_field.')
        if kind in ('open_page', 'open_url', 'back', 'reload'):
            action = self.clone(doc, 'IxLinkWindowAction'); target = self.clone(doc, 'IxTarget')
            self.link(action, 'target', target)
            self.set(action, 'link-type', self.enum('Axure.DocumentModel.Interaction.LinkType', spec.get('window', 'Current')))
            target_type = {'open_page': 'Page', 'open_url': 'WebUrl', 'back': 'BackUrl', 'reload': 'ReloadPage'}[kind]
            self.set(target, 'target-type', self.enum('Axure.DocumentModel.Interaction.IxTargetType', target_type))
            if kind == 'open_page':
                guid = self.pages[spec['page']]
                for key in ('nbcv', 'Qbcj'):
                    set_value(field(get(target, 'target-page-id'), key), guid)
            elif kind == 'open_url':
                self.link(target, 'target-literal', self.expr(doc, spec['url'], page_id))
        elif kind == 'wait':
            action = self.clone(doc, 'IxWaitAction'); self.set(action, 'wait_time', spec['ms'])
        elif kind == 'close':
            action = self.clone(doc, 'IxCloseCurrentAction')
        elif kind == 'focus':
            action = self.clone(doc, 'IxSetFocusOnWidgetAction')
            items(get(action, 'panelobjectpaths')).append(reference(self.ref, oid(self.path(doc, page_id, spec['target']))))
            self.set(action, 'SelectTextOnFocus', spec.get('select_text', False))
        elif kind == 'scroll_to':
            action = self.clone(doc, 'IxScrollToWidgetAction')
            self.link(action, 'targetwidgetpath', self.path(doc, page_id, spec['target']))
            self.set(action, 'duration', spec.get('duration', 0))
            self.set(action, 'scrolldirection', spec.get('direction', 1))
        elif kind in ('set_text', 'set_selected', 'set_variable', 'function'):
            function = {'set_text': 'SetWidgetRichText', 'set_selected': 'SetCheckState', 'set_variable': 'SetGlobalVariableValue'}.get(kind, spec.get('name'))
            if kind == 'set_text':
                target = self.symbols.get((page_id, spec['target']))
                if not target: raise ValueError('Missing or ambiguous set_text target.')
                is_form = rtype(target['record']) in ('Axure:DiagramObject:TextBox', 'Axure:DiagramObject:TextArea')
                function = 'SetWidgetFormText' if is_form else 'SetWidgetRichText'
                args = [{'widget': spec['target']}, spec['value']] + ([] if is_form else [True])
            elif kind == 'set_selected': args = [{'widget': spec['target']}, spec['value']]
            elif kind == 'set_variable': args = [{'variable_ref': spec['variable']}, spec['value']]
            else: args = spec.get('args', [])
            action = self.clone(doc, 'IxActionSetFunction'); self.set(action, 'SetFunction', function)
            block = by_id(doc)[ref_id(get(action, 'action'))]
            items(get(block, 'subexpressions')).append(reference(self.ref, oid(self.expr(doc, {'call': function, 'args': args}, page_id))))
        else:
            mappings = {
                'set_panel_state': ('IxSetPanelStateAction', 'PanelPaths', 'SetStateInfos', 'SetPanelStateInfo'),
                'show': ('IxFadeWidgetAction', 'WidgetPaths', 'FadeInfos', 'FadeWidgetInfo'),
                'hide': ('IxFadeWidgetAction', 'WidgetPaths', 'FadeInfos', 'FadeWidgetInfo'),
                'toggle': ('IxFadeWidgetAction', 'WidgetPaths', 'FadeInfos', 'FadeWidgetInfo'),
                'move': ('IxMoveWidgetAction', 'WidgetPaths', 'MoveInfos', 'MoveWidgetInfo'),
                'resize': ('IxSetWidgetSizeAction', 'WidgetPaths', 'SetSizeInfos', 'SetWidgetSizeInfo'),
                'opacity': ('IxSetOpacityAction', 'Paths', 'Infos', 'SetOpacityInfo'),
                'enable': ('IxEnableDisableWidgetsAction', 'WidgetPaths', 'EnableDisableInfos', 'EnableDisableWidgetsInfo'),
                'disable': ('IxEnableDisableWidgetsAction', 'WidgetPaths', 'EnableDisableInfos', 'EnableDisableWidgetsInfo'),
                'rotate': ('IxRotateWidgetAction', 'Paths', 'Infos', 'RotateWidgetInfo'),
                'front': ('IxSetPanelOrderAction', 'PanelPaths', 'SetOrderInfos', 'SetPanelOrderInfo'),
                'back_order': ('IxSetPanelOrderAction', 'PanelPaths', 'SetOrderInfos', 'SetPanelOrderInfo'),
                'filter': ('IxAddFilterToRepeaterAction', 'RepeaterPaths', 'AddFilterInfos', 'AddFilterToRepeaterInfo'),
                'sort': ('IxAddSortToRepeaterAction', 'RepeaterPaths', 'AddSortInfos', 'AddSortToRepeaterInfo'),
                'items_per_page': ('IxSetItemsPerRepeaterPageAction', 'RepeaterPaths', 'SetItemsPerPageInfos', 'SetItemsPerRepeaterPageInfo'),
                'repeater_page': ('IxSetRepeaterToPageAction', 'RepeaterPaths', 'SetPageInfos', 'SetRepeaterToPageInfo'),
            }
            if kind == 'native':
                model_type = self.models.get(spec.get('model'), {}).get('type', '')
                if not model_type.startswith('Axure.DocumentModel.Interaction.') or 'Action' not in model_type.rsplit('.', 1)[-1]:
                    raise ValueError('native action model must name an exported interaction action.')
                if spec.get('info_model'):
                    for action, info in self.mapped_action(doc, page_id, spec, spec['model'], spec['paths_field'], spec['infos_field'], spec['info_model']):
                        self.configure(doc, info, spec.get('info', {}), page_id)
                else:
                    action = self.clone(doc, spec['model'])
                self.configure(doc, action, spec.get('fields', {}), page_id)
                return action
            if kind not in mappings:
                raise ValueError('Unknown action type: ' + kind)
            for action, info in self.mapped_action(doc, page_id, spec, *mappings[kind]):
                if kind == 'set_panel_state':
                    self.link(info, 'state-value', self.expr(doc, spec.get('value', ''), page_id))
                    self.set(info, 'set-state-type', self.enum('Axure.DocumentModel.Interaction.SetStateType', spec.get('mode', 'Diagram')))
                    if spec.get('state'):
                        state_id = self.panel_states[(page_id, spec['target'])][spec['state']]
                        for key in ('abcZ', 'wbc6'):
                            set_value(field(get(info, 'diagram-id'), key), state_id)
                    self.set(info, 'show-when-set', spec.get('show', True))
                    for key in ('enter', 'exit'):
                        self.set(info, key + '-duration', spec.get('duration', 0))
                        self.set(info, key + '-easing', self.enum('Axure.DocumentModel.Expressions.FadeEasingType', spec.get(key + '_animation', 'None')))
                elif kind in ('show', 'hide', 'toggle'):
                    self.set(info, 'fade-action-type', {'show': 1, 'hide': 0, 'toggle': 2}[kind])
                    self.set(info, 'duration', spec.get('duration', 0)); self.set(info, 'DurationHide', spec.get('duration', 0))
                    self.set(info, 'show-type', self.enum('Axure.DocumentModel.Interaction.ShowType', spec.get('show_type', 'None')))
                    self.set(info, 'easing', self.enum('Axure.DocumentModel.Expressions.FadeEasingType', spec.get('animation', 'None')))
                elif kind == 'move':
                    self.link(info, 'XValue', self.expr(doc, spec['x'], page_id)); self.link(info, 'YValue', self.expr(doc, spec['y'], page_id))
                    self.set(info, 'MoveType', self.enum('Axure.DocumentModel.Expressions.MoveBehavior', spec.get('mode', 'Location')))
                    self.set(info, 'Duration', spec.get('duration', 0))
                elif kind == 'resize':
                    for key in ('width', 'height'):
                        self.link(info, key, self.expr(doc, spec[key], page_id))
                    self.set(info, 'duration', spec.get('duration', 0)); self.set(info, 'anchor', spec.get('anchor', 'top left'))
                elif kind == 'opacity':
                    self.link(info, 'Opacity', self.expr(doc, spec['value'], page_id)); self.set(info, 'Duration', spec.get('duration', 0))
                elif kind in ('enable', 'disable'):
                    self.set(info, 'enable', kind == 'enable')
                elif kind == 'rotate':
                    self.set(info, 'Clockwise', spec.get('clockwise', True))
                    self.link(info, 'Degree', self.expr(doc, spec['degrees'], page_id)); self.set(info, 'Duration', spec.get('duration', 0))
                    self.link(info, 'OffsetX', self.expr(doc, spec.get('offset_x', 0), page_id))
                    self.link(info, 'OffsetY', self.expr(doc, spec.get('offset_y', 0), page_id))
                    self.set(info, 'Anchor', spec.get('anchor', 'center'))
                elif kind in ('front', 'back_order'):
                    self.set(info, 'bring-to-front', kind == 'front')
                elif kind == 'filter':
                    self.set(info, 'Label', spec.get('name', 'filter'))
                    self.set(info, 'RemoveOtherFilters', spec.get('replace', True))
                    self.link(info, 'Filter', self.expr(doc, spec['value'], page_id))
                elif kind == 'sort':
                    column = self.repeater_columns[(page_id, spec['target'])][spec['column']]
                    for key in ('abcZ', 'wbc6'): set_value(field(get(info, 'column-id'), key), column)
                    self.set(info, 'column-name', spec['column'])
                    self.set(info, 'label', spec.get('name', 'sort'))
                    self.set(info, 'ascending', spec.get('ascending', True))
                    self.set(info, 'toggle', spec.get('toggle', False))
                    self.set(info, 'sort-type', spec.get('sort_type', 1))
                elif kind == 'items_per_page':
                    self.set(info, 'no-limit', spec.get('unlimited', False))
                    self.link(info, 'items-per-page', self.expr(doc, spec.get('value', 10), page_id))
                elif kind == 'repeater_page':
                    self.set(info, 'set-page-type', spec.get('mode', 0))
                    self.link(info, 'page-value', self.expr(doc, spec.get('value', 1), page_id))
                if spec.get('native_info'):
                    self.configure(doc, info, spec['native_info'], page_id)
        return action

    def event_map(self, doc, owner, page_id, events, is_page):
        if not isinstance(events, dict):
            raise ValueError('events must map event names to action/case lists.')
        if is_page and 'OnLoad' in events and 'OnPageLoad' in events:
            raise ValueError('Use either OnLoad or its OnPageLoad alias, not both.')
        source = self.map_source
        source_map = by_id(source)[ref_id(get(root(source), 'interactionmap'))]
        records, mapping = clone_records(self.closure(source, oid(source_map)))
        doc['objects'].extend(records)
        ixmap = by_id(doc)[mapping[oid(source_map)]]
        tree = by_id(doc)[ref_id(get(ixmap, 'tree'))]
        items(get(tree, 'children')).clear(); pairs(get(ixmap, 'node-table')).clear()
        self.link(owner, 'interactionmap' if is_page else 'InteractionMap', ixmap)
        def add_node(record, parent):
            node = self.record(doc, self.node_template)
            items(get(node, 'children')).clear()
            self.link(node, 'parent-node', parent); self.link(node, 'tree', tree)
            nr = reference(self.ref, oid(node))
            items(get(parent, 'children')).append(nr)
            pairs(get(ixmap, 'node-table')).append([copy.deepcopy(nr), reference(self.ref, oid(record))])
            return node
        for event_name, cases in events.items():
            if is_page and event_name == 'OnPageLoad':
                event_name = 'OnLoad'
            event = self.clone(doc, 'IxEvent')
            self.set(event, 'event-type', self.enum('Axure.Constants.IxEventType', event_name))
            event_node = add_node(event, tree)
            if not cases or not isinstance(cases, list):
                raise ValueError('Event must contain a nonempty action/case list.')
            if 'type' in cases[0]:
                cases = [{'name': 'Case1', 'actions': cases}]
            for number, case_spec in enumerate(cases):
                if not isinstance(case_spec, dict) or set(case_spec) - {'name', 'if', 'new_if', 'actions'} or not isinstance(case_spec.get('actions'), list):
                    raise ValueError('Case requires an actions list; fields are name/if/new_if/actions.')
                case = self.clone(doc, 'IxCase')
                self.set(case, 'Description', case_spec.get('name', 'Case' + str(number + 1)))
                self.set(case, 'IsNewIfGroup', case_spec.get('new_if', number == 0))
                if 'if' in case_spec:
                    self.link(case, 'Condition', self.expr(doc, case_spec['if'], page_id))
                case_node = add_node(case, event_node)
                for action_spec in case_spec['actions']:
                    add_node(self.action(doc, action_spec, page_id), case_node)

    def finish(self):
        for doc, owner, page, events, is_page in self.pending:
            self.event_map(doc, owner, page, events, is_page)
        for stem, doc in self.docs.items():
            self.a.write(self.work / (stem + '.json'), doc)
