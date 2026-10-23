"""Read native style value types without probing builds or reading bridge code."""
from model import field, get, items, rtype, value


COMMON_STYLES = ('CORNER_RADIUS', 'HORIZONTAL_ALIGNMENT', 'VERTICAL_ALIGNMENT',
                 'OUTER_SHADOW', 'INNER_SHADOW', 'FILL', 'BORDER_FILL',
                 'BORDER_WIDTH', 'BORDER_VISIBILITY', 'OPACITY')

STYLE_VALUES = {
    'HORIZONTAL_ALIGNMENT': {'left': 0, 'center': 1, 'right': 2},
    'VERTICAL_ALIGNMENT': {'top': 0, 'middle': 1, 'bottom': 2},
}


def describe(node):
    result = {'type': node.get('t'), 'default': value(node)}
    if 'v' in node:
        return result
    wrapped = node.get('f', {})
    if len(wrapped) == 1 and not field(node, 'ebL0'):
        return describe(next(iter(wrapped.values())))
    if field(node, 'ebL0'):
        result['fields'] = {str(value(k)): describe(v) for k, v in field(node, 'ebL0')['d']}
    return result


def style_info(api, install, name=None):
    library = api.cache(install)
    enums = api.read(api.model_schema(install) / 'enums.json')['Axure.Constants.PName']
    design = api.locate(library)['Axure:DesignDocument'][0][1]
    properties = {}
    for record in design['objects']:
        if rtype(record) == 'Axure:Style':
            for prop in items(get(record, 'PropList')):
                properties.setdefault(value(get(prop, 'DOAName')), get(prop, 'Value'))
    names = [name] if name else COMMON_STYLES
    result = {}
    for prop_name in names:
        if prop_name not in enums:
            raise ValueError('Unknown native style property: ' + prop_name)
        node = properties.get(-1073741824 + enums[prop_name])
        if node is None:
            if name:
                raise ValueError('No native value template for style property: ' + prop_name)
            continue
        result[prop_name] = describe(node)
        if prop_name in STYLE_VALUES:
            result[prop_name]['values'] = STYLE_VALUES[prop_name]
    return {'ok': True, 'properties': result}
