"""Application checks for object menus and moving a complete track."""
import os, tempfile, json, traceback
from unittest.mock import patch
root = tempfile.mkdtemp(prefix='openshot-object-menus-')
expand = os.path.expanduser
os.path.expanduser = lambda p: root if p == '~' else expand(p)
from classes import version, info
version.get_current_Version = lambda: None
from classes.app import OpenShotApp
from classes.query import Clip, File, Track, Transition, Effect
from qt_api import QImage, Qt, QPointF, QPoint, QToolButton, QTimer
import importlib
from qt_api import QT_API
QTest = importlib.import_module({'pyqt5': 'PyQt5', 'pyqt6': 'PyQt6', 'pyside6': 'PySide6'}[QT_API] + '.QtTest').QTest
from tests.gui_test_helpers import run_gui_workflow
import openshot
app = OpenShotApp([], mode='unittest')
from windows.views.menu import StyledContextMenu
app.settings.set('tutorial_enabled', False)
app.settings.set('send_metrics', False)
passed = False

def get_menu(method, ident):
    with patch.object(StyledContextMenu, 'show_at', lambda m, p: m):
        return method(ident)

def verify():
    global passed
    try:
        w = app.window
        w.resize(1400, 900)
        tl = w.timeline
        img = QImage(320, 180, QImage.Format_RGBA8888)
        img.fill(Qt.darkRed)
        path = root + '/Sample clip.png'
        img.save(path)
        native = openshot.Clip(path)
        f = File()
        f.data = json.loads(native.Reader().Json())
        f.data.update(path=path, media_type='image', start=0.0, end=8.0, name='Sample clip')
        f.save()
        layers = sorted(app.project.get('layers'), key=lambda t: t['number'], reverse=True)
        track = layers[1]
        for pos in (0.0, 10.0):
            tl.addClip(f.id, QPointF(pos, 0), track['number'], call_manual_move=False)
        clips = Clip.filter(layer=track['number'])
        first = clips[0]
        tl.addTransition(os.path.join(info.PATH, 'transitions/common/circle_in_to_out.svg'), QPointF(2.0, 0), track['number'], call_manual_move=False)
        tran = Transition.filter(layer=track['number'])[0]
        tl.show_effects_tray(track['id'])
        tl._effects_tray._add_effect('Blur')
        effect = Effect.filter()[0]
        w.clearSelections()
        w.addSelection(first.id, 'clip', False)
        tl._apply_effect_to_clip(first, 'Bars')
        tl.setZoomFactor(4, emit=False)
        app.processEvents()
        old_clips = {c.id: json.loads(json.dumps(c.data)) for c in Clip.filter(layer=track['number'])}
        old_tran = json.loads(json.dumps(Transition.get(id=tran.id).data))
        tl._set_track_keyframes(track['number'], True)
        tl._move_track_from_menu(track['id'], -1)
        moved = Track.get(id=track['id'])
        assert moved.data['number'] > layers[0]['number']
        assert tl._track_panel_enabled.get(moved.data['number'])
        assert Effect.get(id=effect.id).parent['id'] == track['id']
        for ident, data in old_clips.items():
            new = Clip.get(id=ident).data
            assert new['layer'] == moved.data['number']
            assert new['position'] == data['position']
        assert Transition.get(id=tran.id).data['layer'] == moved.data['number']
        app.updates.undo()
        assert Track.get(id=track['id']).data['number'] == track['number']
        assert tl._track_panel_enabled.get(track['number'])
        assert all((Clip.get(id=i).data['layer'] == d['layer'] for i, d in old_clips.items()))
        assert Transition.get(id=tran.id).data['layer'] == old_tran['layer']
        app.updates.redo()
        assert Track.get(id=track['id']).data['number'] == moved.data['number']
        app.updates.undo()
        # Down, boundary and locked-track moves must be safe as well.
        tl._move_track_from_menu(track['id'], 1)
        assert Track.get(id=track['id']).data['number'] < layers[2]['number']
        app.updates.undo()
        history_count = len(app.updates.actionHistory)
        tl._move_track_from_menu(layers[0]['id'], -1)
        tl._move_track_from_menu(layers[-1]['id'], 1)
        assert len(app.updates.actionHistory) == history_count
        for theme in ('Cosmic Dusk', 'Humanity: Dark', 'Retro'):
            app.theme_manager.apply_theme(theme)
            app.processEvents()
            for kind, method, ident, selection in (('Clip', tl.ShowClipMenu, first.id, 'clip'), ('Track', tl.ShowTrackMenu, track['id'], None), ('Effect', tl.ShowEffectMenu, effect.id, 'effect'), ('Transition', tl.ShowTransitionMenu, tran.id, 'transition')):
                w.clearSelections()
                if selection:
                    w.addSelection(ident, selection, False)
                menu = get_menu(method, ident)
                menu.popup(QPoint(20, 20))
                app.processEvents()
                if os.environ.get('OPENSHOT_MENU_SCREENSHOT_DIR'):
                    menu.grab().save(os.path.join(os.environ['OPENSHOT_MENU_SCREENSHOT_DIR'], theme.replace(':', '').replace(' ', '-') + '-' + kind + '.png'))
                if kind == 'Track':
                    for key in ('muted', 'hidden'):
                        button = menu.findChild(QToolButton, key)
                        button.click()
                        app.processEvents()
                        assert menu.isVisible() and Track.get(id=track['id']).data[key]
                        button.click()
                        app.processEvents()
                        assert not Track.get(id=track['id']).data[key]
                if kind in ('Clip', 'Effect', 'Transition'):
                    copy = next((b for b in menu.findChildren(QToolButton) if b.text() == 'Copy'))
                    assert copy.menu(), (kind, 'missing Copy submenu')
                    opened = []
                    copy.menu().aboutToShow.connect(lambda: opened.append(True))
                    QTimer.singleShot(0, copy.menu().close)
                    QTest.mouseClick(copy, Qt.LeftButton)
                    assert opened, (kind, 'Copy did not open its submenu')
                    assert any((a.text().replace('&', '') == 'Properties' for a in menu.actions()))
                menu.close()
        tl._show_effect_keyframes_from_menu(effect.id)
        app.processEvents()
        assert effect.id in w.selected_effects
        assert tl._track_panel_enabled.get(track['number'])
        # Lock closes the menu and disables structural edits on reopening.
        menu = get_menu(tl.ShowTrackMenu, track['id'])
        menu.popup(QPoint(20, 20))
        app.processEvents()
        next(a for a in menu.actions() if a.text() == 'Lock').trigger()
        menu.close()
        assert not menu.isVisible() and Track.get(id=track['id']).data['lock']
        menu = get_menu(tl.ShowTrackMenu, track['id'])
        remove = next(a for a in menu.actions() if a.text().replace('&', '') == 'Remove')
        assert not remove.isEnabled()
        old_number = Track.get(id=track['id']).data['number']
        tl._move_track_from_menu(track['id'], -1)
        assert Track.get(id=track['id']).data['number'] == old_number
        tl._set_track_lock_from_menu(track['id'], False)
        # Cut only the clicked effect; its owner and neighboring clips survive.
        clip_ids = {clip.id for clip in Clip.filter()}
        tl._cut_effect_from_menu(effect.id)
        assert Effect.get(id=effect.id) is None
        assert {clip.id for clip in Clip.filter()} == clip_ids
        app.updates.undo()
        assert Effect.get(id=effect.id).parent['id'] == track['id']
        # Whole-track paste duplicates identity, not timing or editable stacks.
        from classes.track_clipboard import copy_track, paste_track
        from classes.clipboard import ClipboardManager
        from qt_api import QColor
        source_track = Track.get(id=track['id']).data
        source_clips = Clip.filter(layer=source_track['number'])
        assert copy_track(track['id'])
        assert isinstance(ClipboardManager.from_mime(app.clipboard().mimeData()), Track)
        copied_id = paste_track(track['id'])
        copied_track = Track.get(id=copied_id)
        assert copied_track.data['number'] > source_track['number']
        assert copied_track.id != track['id']
        assert copied_track.data['effects'][0]['id'] != source_track['effects'][0]['id']
        copied_clips = sorted(Clip.filter(layer=copied_track.data['number']), key=lambda c:c.data['position'])
        source_clips = sorted(source_clips, key=lambda c:c.data['position'])
        assert len(copied_clips) == len(source_clips)
        for source, copied in zip(source_clips, copied_clips):
            assert source.id != copied.id
            for key in ('position', 'start', 'end'):
                assert source.data[key] == copied.data[key]
            if source.data.get('effects'):
                assert source.data['effects'][0]['id'] != copied.data['effects'][0]['id']
        assert Transition.filter(layer=copied_track.data['number'])
        app.updates.undo()
        assert Track.get(id=copied_id) is None
        app.updates.redo()
        assert Track.get(id=copied_id)
        app.updates.undo()
        assert copy_track(track['id'], cut=True)
        assert Track.get(id=track['id']) is None
        app.updates.undo()
        assert Track.get(id=track['id'])
        # Track properties live in the regular dock and edits are undoable.
        tl._show_track_properties(track['id'])
        model = w.propertyTableView.clip_properties_model
        model.update_item_timeout()
        assert model.selected_ids == [(track['id'], 'track')]
        name = model.items['track.label']['row'][1]
        assert name.text() == 'Track %s' % (layers.index(track) * -1 + len(layers))
        assert name.flags() & Qt.ItemIsEditable
        from qt_api import QLineEdit
        view = w.propertyTableView
        view.setCurrentIndex(name.index())
        view.edit(name.index())
        editor = view.findChild(QLineEdit)
        assert editor is not None
        editor.setText('Track property test')
        QTest.keyClick(editor, Qt.Key_Return)
        app.processEvents()
        assert Track.get(id=track['id']).data['label'] == 'Track property test'
        app.updates.undo()
        # Timeline background uses the same RGBA/keyframe editing machinery.
        tl._show_timeline_properties()
        model.update_item_timeout()
        assert model.selected_ids == [('__timeline__', 'timeline')]
        model.update_frame(1)
        model.color_update(model.items['color']['row'][1], QColor(255,255,255,255), force_insert=True)
        model.update_frame(3)
        model.color_update(model.items['color']['row'][1], QColor(0,0,0,0), force_insert=True)
        assert app.project.get('color')['alpha']['Points'][-1]['co']['Y'] == 0
        assert w.timeline_sync.timeline.color.alpha.GetInt(3) == 0
        w.timeline_sync.timeline.SetMaxSize(8, 8)
        fps = app.project.get("fps")
        gap_frame = round(9 * fps["num"] / fps["den"]) + 1
        assert bytes(w.timeline_sync.timeline.GetFrame(gap_frame).GetPixelsBytes())[3] == 0
        app.updates.undo()
        assert w.timeline_sync.timeline.color.alpha.GetInt(3) == 255
        assert bytes(w.timeline_sync.timeline.GetFrame(gap_frame).GetPixelsBytes())[3] == 255
        app.updates.redo()
        assert w.timeline_sync.timeline.color.alpha.GetInt(3) == 0
        model.update_frame(3)
        model.remove_keyframe(model.items['color']['row'][1])
        assert w.timeline_sync.timeline.color.alpha.GetInt(3) == 255
        app.updates.undo()
        assert w.timeline_sync.timeline.color.alpha.GetInt(3) == 0
        model.update_frame(3)
        table = w.propertyTableView
        table.selected_item = model.items['color']['row'][1]
        table.color_callback(QColor(0,255,0,0))
        assert w.timeline_sync.timeline.color.green.GetInt(3) == 255
        app.updates.undo()
        assert w.timeline_sync.timeline.color.green.GetInt(3) == 0
        project_path = os.path.join(root, 'canvas.osp')
        app.project.save(project_path)
        with open(project_path) as stream:
            saved = json.load(stream)
        assert saved['color']['alpha']['Points'][-1]['co']['Y'] == 0
        tl._show_effect_keyframes_from_menu(effect.id)
        # Closing a real context menu must release every owned submenu/control.
        from qt_api import QCoreApplication, QEvent, QApplication
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        retained = len(w.findChildren(StyledContextMenu))
        for method, ident in ((tl.ShowClipMenu, first.id), (tl.ShowTrackMenu, track['id']),
                              (tl.ShowEffectMenu, effect.id), (tl.ShowTransitionMenu, tran.id)):
            def close_popup():
                popup = QApplication.activePopupWidget()
                if popup is not None:
                    popup.close()
            QTimer.singleShot(0, close_popup)
            method(ident)
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            assert len(w.findChildren(StyledContextMenu)) == retained
        print('OBJECT_MENUS_PASSED', flush=True)
        passed = True
    except Exception:
        traceback.print_exc()
    finally:
        app.project.has_unsaved_changes = False
        app.quit()
run_gui_workflow(app, verify)
raise SystemExit(not passed)
