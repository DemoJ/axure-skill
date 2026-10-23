"""RP9 intermediate model helpers; names match verified build 9.0.0.3744."""
import copy
import uuid

ZERO = '00000000-0000-0000-0000-000000000000'

def field(node, name):
    return next((v for k, v in node.get('f', {}).items() if k.endswith('::' + name)), None)

def value(node):
    if node is None:
        return None
    if 'v' in node:
        return node['v']
    if 'l' in node:
        return [value(v) for v in node['l']]
    if 'd' in node:
        return {str(value(k)): value(v) for k, v in node['d']}
    if node.get('t') == 'XbPW.sbPe':
        return {'ref': value(field(node, 'abPc'))}
    fs = node.get('f', {})
    if len(fs) == 1:
        return value(next(iter(fs.values())))
    return {k.split('::')[-1]: value(v) for k, v in fs.items()}

def pairs(node):
    if 'd' in node:
        return node['d']
    return field(node, 'ebL0')['d']

def get(node, key, default=None):
    return next((v for k, v in pairs(node) if str(value(k)) == str(key)), default)

def put(node, key, val):
    entries = pairs(node)
    for pair in entries:
        if str(value(pair[0])) == str(key):
            pair[1] = val
            return
    entries.append([{'t': 'System.String', 'v': str(key)}, val])

def drop(node, key):
    pairs(node)[:] = [p for p in pairs(node) if str(value(p[0])) != str(key)]

def items(node):
    return field(node, 'zbZy')['l']

def scalar(v, kind=None):
    if kind is None:
        kind = 'System.Boolean' if isinstance(v, bool) else 'System.Int32' if isinstance(v, int) else 'System.Double' if isinstance(v, float) else 'System.String'
    if kind in ('System.Double', 'System.Single'):
        v = str(v)
    # Wrappers are harvested from actual native templates, not constructed here.
    return {'t': kind, 'v': v}

def set_value(node, new):
    if 'v' in node:
        node['v'] = str(new) if node['t'] in ('System.Double', 'System.Single') else new
        return
    fs = node.get('f', {})
    if len(fs) != 1:
        raise ValueError('Expected scalar wrapper: ' + str(node.get('t')))
    set_value(next(iter(fs.values())), new)

def oid(record):
    return value(field(record, 'QbLz'))

def rtype(record):
    return value(field(record, 'FbPd'))

def by_id(doc):
    return {oid(o): o for o in doc['objects']}

def root(doc):
    return by_id(doc)[doc['root']]

def ref_id(node):
    return value(field(node, 'abPc'))

def reference(template, identifier):
    result = copy.deepcopy(template)
    set_value(field(result, 'abPc'), identifier)
    set_value(field(result, 'mbPZ'), identifier)
    return result

def new_id():
    return str(uuid.uuid4())

def remap(node, mapping):
    if isinstance(node, dict):
        if 'v' in node and node['t'] == 'System.Guid' and node['v'] in mapping:
            node['v'] = mapping[node['v']]
        elif 'v' in node and node['t'] == 'System.String' and node['v'] in mapping:
            node['v'] = mapping[node['v']]
        for v in node.values():
            remap(v, mapping)
    elif isinstance(node, list):
        for v in node:
            remap(v, mapping)

def clone_records(records):
    result = copy.deepcopy(records)
    mapping = {oid(o): new_id() for o in result}
    remap(result, mapping)
    return result, mapping
