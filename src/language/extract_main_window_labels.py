#!/usr/bin/env python3
"""Extract the deliberately bounded main-window translation review surface.

Run from any directory; requires the same Qt binding as OpenShot, but no GUI or
libopenshot. XML/AST parsing preserves multiline strings, punctuation and context.
The explicit dynamic-string allowlist prevents dialog/context-menu scope creep.
"""
import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from qt_api import QCoreApplication, QTranslator

# openshot-site/openshot_site2/settings/base.py LANGUAGES (2026-09-26).
# 25 translations plus the English source. Portuguese is pt, not pt_BR.
LANGUAGES = {
    'ar': 'ar', 'bn': 'bn', 'zh-hans': 'zh_CN', 'zh-hant': 'zh_TW',
    'hr': 'hr', 'nl': 'nl', 'fr': 'fr', 'fi': 'fi', 'en': None,
    'de': 'de', 'hi': 'hi', 'is': 'is', 'id': 'id', 'it': 'it',
    'ja': 'ja', 'ko': 'ko', 'nb': 'nb', 'fa': 'fa', 'pl': 'pl',
    'pt': 'pt', 'ro': 'ro', 'ru': 'ru', 'es': 'es', 'tr': 'tr',
    'vi': 'vi', 'uk': 'uk',
}
DYNAMIC = {
    'src/themes/base.py': {'Play', 'Pause'},
    'src/windows/main_window.py': {
        'Disable Snapping', 'Enable Snapping', 'Disable Razor', 'Enable Razor',
        'Disable Timing', 'Enable Timing', 'Filter', 'Untitled Project',
        'My Views', 'Recording View', 'Docks', 'Scopes', 'Recent Projects',
        'Recovery', 'Enter caption text...', 'Caption Toolbar', 'Luma Waveform',
        'Histogram', 'Vectorscope', 'Audio Levels', 'Recording', 'Color View',
    },
    'src/windows/views/zoom_slider.py': {
        'Zoom left edge', 'Zoom right edge', 'Pan timeline',
        'Click: center · Drag: zoom',
    },
    'src/windows/views/timeline_backend/qwidget/base.py': {
        'Unlock track', 'Lock track', 'Hide keyframes', 'Show keyframes',
        'Effect: %s', 'Effect', 'Transition: %s', 'Transition', 'Clip', 'Clip: %s',
    },
    'src/windows/views/timeline_backend/qwidget/track.py': {'Track %s'},
    'src/windows/models/files_model.py': {'Thumb', 'Name', 'Tags'},
    'src/windows/models/properties_model.py': {'Property', 'Value'},
}


def extract():
    labels = {}

    def add(source, location):
        if source:
            labels.setdefault(source, set()).add(location)

    path = 'src/windows/ui/main-window.ui'
    ui = ET.parse(ROOT / path).getroot()
    objects = {e.get('name'): e for e in ui.iter() if e.get('name') and e.tag in ('widget', 'action')}
    menus = [a.get('name') for a in objects['menubar'].findall('addaction')]
    selected = set(menus)
    for name in menus:
        selected.update(a.get('name') for a in objects[name].findall('addaction'))
    # Toolbar actions are assembled by themes and setup_toolbars, not the .ui.
    for file in ['src/themes/base.py', 'src/themes/cosmic/theme.py']:
        tree = ast.parse((ROOT / file).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value == 'action' and isinstance(value, ast.Attribute):
                        selected.add(value.attr)
    tree = ast.parse((ROOT / 'src/windows/main_window.py').read_text())
    setup = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'setup_toolbars')
    for node in ast.walk(setup):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'addAction':
            for arg in node.args:
                if isinstance(arg, ast.Attribute):
                    selected.add(arg.attr)
    selected.update(e.get('name') for e in ui.iter('widget') if e.get('class') in ('QDockWidget', 'QToolBar', 'QLineEdit'))
    selected.difference_update({'actionRecentProjects', 'actionRecoveryProjects'})  # replaced at runtime
    for name in sorted(selected):
        if name not in objects:
            continue
        for prop in objects[name].findall('property'):
            string = prop.find('string')
            if string is not None and string.get('notr') != 'true' and prop.get('name') in ('text', 'title', 'toolTip', 'windowTitle', 'placeholderText'):
                add(string.text, f'{path}#{name}.{prop.get("name")}')
    for file, wanted in DYNAMIC.items():
        tree = ast.parse((ROOT / file).read_text())
        found = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            if not ((isinstance(func, ast.Name) and func.id == '_') or (isinstance(func, ast.Attribute) and func.attr == '_tr')):
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and arg.value in wanted:
                add(arg.value, f'{file}:{node.lineno}')
                found.add(arg.value)
        if wanted - found:
            raise ValueError(f'Stale dynamic allowlist in {file}: {sorted(wanted - found)}')
    return [{'source': s, 'locations': sorted(loc)} for s, loc in sorted(labels.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'doc/translation-review')
    args = parser.parse_args()
    app = QCoreApplication.instance() or QCoreApplication([])
    labels = extract()
    rows = []
    catalogs = {}
    for website, locale in LANGUAGES.items():
        translator = QTranslator()
        if locale:
            path = ROOT / 'src/language' / f'OpenShot_{locale}.qm'
            if not translator.load(str(path)):
                raise RuntimeError(f'Cannot load {path}')
            catalogs[website] = {'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        for label in labels:
            source = label['source']
            # OpenShotApp._tr and ui_util use the empty Qt translation context.
            try:
                translated = translator.translate('', source) if locale else source
            except UnicodeEncodeError:
                # PyQt's QTranslator char* overload needs UTF-8 bytes.
                translated = translator.translate('', source.encode('utf-8'))
            status = 'english-source' if locale is None else ('translated' if translated else 'missing')
            text = translated or source
            if locale and translated == source:
                status = 'same-as-source'  # not necessarily wrong: Video, Histogram, etc.
            if sorted(re.findall(r'%[sd]', source)) != sorted(re.findall(r'%[sd]', text)):
                raise ValueError(f'Placeholder mismatch: {website}: {source!r}: {text!r}')
            rows.append({'language': website, 'qt_locale': locale or 'en', 'source': source,
                         'translation': text, 'status': status,
                         'locations': '; '.join(label['locations'])})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {'scope': 'Main menus (one level), toolbar actions, dock headings, media filters, zoom/track/clip tooltips; excludes dialog and context-menu contents.',
               'catalogs': catalogs, 'labels': labels, 'translations': rows}
    (args.output_dir / 'main-window-labels.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    with (args.output_dir / 'main-window-labels.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f'{len(labels)} unique labels × {len(LANGUAGES)} languages = {len(rows)} rows')
    print(f'Missing translations: {sum(r["status"] == "missing" for r in rows)}')


if __name__ == '__main__':
    main()
