"""One-time migration of the timeline keyboard defaults."""

from qt_api import QKeySequence

LEGACY_TIMELINE_SHORTCUTS = {
    'seekPreviousFrame': 'Left | ,',
    'seekNextFrame': 'Right | .',
    'playToggle': 'Space | Up | Down | K',
    'actionCenterOnPlayhead': 'Shift+C | Alt+Up',
    'nudgeLeft': 'Ctrl+Left',
    'nudgeRight': 'Ctrl+Right',
    'nudgeLeftBig': 'Shift+Ctrl+Left',
    'nudgeRightBig': 'Shift+Ctrl+Right',
}


def _keys(value):
    return {QKeySequence(key.strip()).toString() for key in value.split('|') if key.strip()}


def migrate_timeline_shortcuts(defaults, user):
    """Move stock bindings once, preserving customized commands and their keys.

    A new command which conflicts with a custom binding receives an unused
    Ctrl+Alt+Shift shortcut, so both commands remain reachable.
    """
    saved = {item['setting']: item for item in user if 'setting' in item}
    version = saved.get('timeline-keyboard-version', {}).get('value', 0)
    if version >= 3:
        return user
    keyboard = {item['setting']: item for item in defaults if item.get('category') == 'Keyboard'}
    previous_defaults = LEGACY_TIMELINE_SHORTCUTS if version < 1 else {}
    if version == 2:
        previous_defaults = {'focusEffects': 'Shift+7', 'focusTransitions': 'Shift+8'}
    changed = set(previous_defaults) | {k for k in keyboard if k not in saved}
    custom = set()
    for name, item in saved.items():
        if name not in keyboard:
            continue
        baseline = previous_defaults.get(name, keyboard[name]['value'])
        if _keys(item.get('value', '')) != _keys(baseline):
            custom.add(name)
    occupied = set()
    for name, item in keyboard.items():
        if name not in changed or name in custom:
            occupied.update(_keys(saved.get(name, item)['value']))
    for name, item in keyboard.items():
        if name not in changed or name in custom:
            continue
        keys = []
        for key in item['value'].split('|'):
            key = key.strip()
            if not key:
                continue
            if _keys(key) & occupied:
                # Use a discoverable modified version of the same physical key.
                base = key.split('+')[-1]
                candidates = [f'Ctrl+Alt+Shift+{base}'] + [f'Ctrl+Alt+Shift+F{i}' for i in range(1, 13)]
                key = next((candidate for candidate in candidates if not _keys(candidate) & occupied), '')
            if key:
                keys.append(key)
                occupied.update(_keys(key))
        saved[name] = dict(item, value=' | '.join(keys))
    saved['timeline-keyboard-version'] = {'setting': 'timeline-keyboard-version', 'value': 3}
    return list(saved.values())
