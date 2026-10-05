import os,tempfile,time,traceback,sys,importlib,copy,json
from unittest.mock import patch
root=tempfile.mkdtemp(prefix='openshot-text-smoke-')
original_expanduser=os.path.expanduser
os.path.expanduser=lambda path: root if path=='~' else original_expanduser(path)
from classes.app import OpenShotApp
from classes import version
# UI workflow checks must not depend on the external update service.
version.get_current_Version = lambda: None
from qt_api import QTimer,Qt,QPoint,QT_API,QThreadPool
from classes.query import Clip
app=OpenShotApp([],mode='unittest')
app.settings.set('tutorial_enabled',False)
app.settings.set('send_metrics',False)
QTest=importlib.import_module({'pyqt5':'PyQt5','pyqt6':'PyQt6','pyside6':'PySide6'}[QT_API]+'.QtTest').QTest
passed=False

def verify():
    global passed
    try:
        window=app.window
        window.raise_()
        window.activateWindow()
        QTest.qWaitForWindowActive(window, 5000)
        controller=window.direct_text
        # A real background reader must survive runtime FrameMapper cloning.
        from qt_api import QImage, QColor
        import openshot
        background = QImage(160, 90, QImage.Format_RGBA8888)
        background.fill(QColor("#16395d"))
        background.save(root + "/background.png")
        native_background = openshot.Clip(root + "/background.png")
        background_clip = Clip()
        background_clip.data = json.loads(native_background.Json())
        background_clip.data.update(start=0.0, end=20.0, duration=20.0, position=0.0,
                                    layer=app.project.get("layers")[0]["number"])
        background_clip.save()
        button=window.videoToolbar.widgetForAction(window.actionDirectText)
        assert button is not None and button.isVisible() and not window.actionDirectText.icon().isNull()
        t=time.perf_counter()
        QTest.mouseClick(button,Qt.LeftButton)
        print('entry ms',1000*(time.perf_counter()-t),flush=True)
        assert controller.draft is not None
        created = Clip.get(id=controller.clip_id)
        assert created is not None and created.data["direct_text"]["text"] == "Text"
        assert window.selected_clips == [created.id]
        assert controller.editor.hasFocus() and controller.editor.textCursor().selectedText() == "Text"
        assert not hasattr(controller, "toolbar")
        raster = QImage(created.data["reader"]["path"])
        glyphs = [QPoint(x, y) for y in range(raster.height()) for x in range(raster.width())
                  if raster.pixelColor(x, y).alpha() > 0]
        assert len(glyphs) > 100, len(glyphs)
        assert abs(sum(p.x() for p in glyphs) / len(glyphs) - raster.width() / 2) < raster.width() / 8
        screenshot_dir = os.environ.get("OPENSHOT_TEXT_SCREENSHOT_DIR")
        if screenshot_dir:
            os.makedirs(screenshot_dir, exist_ok=True)
            window.grab().save(os.path.join(screenshot_dir, "text-created.png"))
        deadline = time.monotonic() + 5
        while not controller.background_ready and time.monotonic() < deadline:
            QTest.qWait(10)
        assert controller.background_ready
        assert not controller.background_image.isNull()
        assert controller.background_image.pixelColor(20, 20).name() == "#16395d", controller.background_image.pixelColor(20, 20).name()
        # Dock resizing must leave the actual selected timeline clip visible.
        timeline_widget = window.timeline
        if hasattr(timeline_widget, "geometry"):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                QTest.qWait(10)
                timeline_widget.geometry.ensure()
                visible_rects = [(rect, selected) for rect, item, selected in timeline_widget.geometry.iter_clips()
                                 if item.id == created.id and rect.right() > timeline_widget.track_name_width
                                 and rect.left() < timeline_widget.width() and rect.bottom() > timeline_widget.ruler_height
                                 and rect.top() < timeline_widget.height()]
                if visible_rects and visible_rects[0][1] and not timeline_widget.delayed_resize_timer.isActive():
                    break
            else:
                raise AssertionError("New Text timeline clip is outside the visible viewport")
            QTest.qWait(500)
            timeline_widget.geometry.ensure()
            assert any(item.id == created.id and selected and rect.right() > timeline_widget.track_name_width
                       and rect.left() < timeline_widget.width() and rect.top() < timeline_widget.height()
                       for rect, item, selected in timeline_widget.geometry.iter_clips())
            painter = timeline_widget.clip_painter
            thumbnail = painter.thumb_cache.get((painter._clip_key(created), ("direct-text", created.data["reader"]["path"])))
            assert thumbnail is not None and not thumbnail.isNull(), "Visible Text clip has no painted thumbnail"
            thumb_image = thumbnail.toImage()
            assert any(thumb_image.pixelColor(x, y).alpha() > 0 for y in range(thumb_image.height())
                       for x in range(thumb_image.width())), "Text thumbnail contains no glyph pixels"
        # Nonempty native glyphs are composited above real overlapping media.
        native_frame = window.timeline_sync.timeline.GetFrame(1)
        native_image = QImage(native_frame.GetPixelsBytes(), native_frame.GetWidth(), native_frame.GetHeight(), native_frame.GetWidth() * 4, QImage.Format_RGBA8888).copy()
        assert any(native_image.pixelColor(x, y).red() > 220 for y in range(native_image.height()) for x in range(native_image.width())), "No native white text pixels over background"
        original_size = created.data["direct_text"]["font_size"]
        assert controller.apply_property(created.id, "direct_text.font_size", original_size + 5)
        assert controller.draft["font_size"] == original_size + 5 and controller.view.isVisible()
        app.updates.undo()
        assert controller.draft["font_size"] == original_size
        controller.finish()
        assert Clip.get(id=created.id).data["direct_text"]["font_size"] == original_size
        # Corner and border presses originate on the live caret overlay.
        from qt_api import QPointF, QCoreApplication, QEvent, QMouseEvent
        preview = window.videoPreview
        controller.begin(created.id)
        QTest.qWait(80)
        before_scale = Clip.get(id=created.id).data["scale_x"]["Points"][0]["co"]["Y"]
        corner = preview.transform.map(preview.bottomRightHandle.center()).toPoint()
        QTest.mousePress(controller.view.viewport(), Qt.LeftButton, pos=corner)
        assert controller.draft is None and preview.mouse_pressed
        assert preview.transform_mode == "scale_bottom_right", preview.transform_mode
        QCoreApplication.sendEvent(preview, QMouseEvent(QEvent.MouseMove, QPointF(corner + QPoint(25, 15)), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.mouseRelease(preview, Qt.LeftButton, pos=corner + QPoint(25, 15))
        assert not preview.mouse_pressed and not app.updates.ignore_history and not controller.forwarded_drag
        assert Clip.get(id=created.id).data["scale_x"]["Points"][0]["co"]["Y"] != before_scale
        controller.begin(created.id)
        QTest.qWait(80)
        before_move = Clip.get(id=created.id).data["location_x"]["Points"][0]["co"]["Y"]
        border = preview.transform.map(QPointF(preview.clipBounds.width() * .25, 0)).toPoint()
        QTest.mousePress(controller.view.viewport(), Qt.LeftButton, pos=border)
        assert controller.draft is None and preview.transform_mode == "location", preview.transform_mode
        QCoreApplication.sendEvent(preview, QMouseEvent(QEvent.MouseMove, QPointF(border + QPoint(20, 10)), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.mouseRelease(preview, Qt.LeftButton, pos=border + QPoint(20, 10))
        assert not preview.mouse_pressed and not app.updates.ignore_history and not controller.forwarded_drag
        assert Clip.get(id=created.id).data["location_x"]["Points"][0]["co"]["Y"] != before_move
        controller.begin(created.id)
        controller.editor.selectAll()
        QTest.keyClicks(controller.editor,'Hello')
        QTest.keyClick(controller.editor,Qt.Key_Return)
        controller.editor.insertPlainText('العربية café 🎉')
        assert 'Hello\n' in controller.editor.toPlainText()
        if screenshot_dir:
            window.grab().save(os.path.join(screenshot_dir, 'text-typing.png'))
        QTest.keyClick(controller.editor,Qt.Key_Escape)
        clips=[item for item in Clip.filter() if item.data.get("direct_text")]
        assert len(clips)==1,len(clips)
        clip=clips[0]
        assert clip.data['direct_text']['text']=='Hello\nالعربية café 🎉',clip.data
        print('created',clip.id,clip.data['reader']['path'],flush=True)
        old=copy.deepcopy(clip.data)
        controller.begin(clip.id)
        QTest.qWait(150)
        QTest.keyClicks(controller.editor,' edited')
        controller.finish()
        assert Clip.get(id=clip.id).data['direct_text']['text'].endswith(' edited')
        app.updates.undo()
        assert Clip.get(id=clip.id).data['direct_text']==old['direct_text']
        app.updates.redo()
        assert Clip.get(id=clip.id).data['direct_text']['text'].endswith(' edited')
        # Copy/paste duplicates semantic data, then editing changes only one raster.
        window.selected_items=[{'id':clip.id,'type':'clip'}]
        window.copyAll()
        window.pasteAll()
        duplicates=[x for x in Clip.filter() if x.id!=clip.id and x.data.get("direct_text")]
        assert len(duplicates)==1
        duplicate=duplicates[0]
        controller.begin(duplicate.id)
        controller.editor.insertPlainText(' independent')
        QTest.keyClick(controller.editor, Qt.Key_Escape)
        assert not Clip.get(id=clip.id).data['direct_text']['text'].endswith(' independent')
        # Native transform hit mapping at rotation and scaled preview.
        transformed=Clip.get(id=clip.id)
        transformed.data['rotation']['Points'][0]['co']['Y']=25
        transformed.data['scale_x']['Points'][0]['co']['Y']=0.8
        transformed.data['scale_y']['Points'][0]['co']['Y']=0.8
        transformed.save()
        fps = app.project.get("fps")
        target_frame = round(transformed.data["position"] * fps["num"] / fps["den"]) + 1
        window.SeekSignal.emit(target_frame, True)
        deadline = time.monotonic() + 5
        while window.preview_thread.current_frame != target_frame and time.monotonic() < deadline:
            QTest.qWait(10)
        assert window.preview_thread.current_frame == target_frame
        from qt_api import QPointF,QInputMethodEvent,QCoreApplication,QEvent,QMouseEvent
        mapped=controller.geometry(transformed.data).map(QPointF(30,30))
        assert controller.hit(mapped)==clip.id, (controller.hit(mapped), clip.id, window._current_timeline_seconds(), transformed.data["position"])
        controller.begin(clip.id)
        input_event=QInputMethodEvent()
        input_event.setCommitString('漢字')
        QCoreApplication.sendEvent(controller.editor,input_event)
        assert controller.editor.toPlainText().endswith('漢字')
        controller.finish()
        assert window.selected_clips == [clip.id], window.selected_clips
        # Drive the real preview transform handlers with Qt mouse events.
        before_drag = Clip.get(id=clip.id).data['location_x']['Points'][0]['co']['Y']
        window.TransformSignal.emit([clip.id])
        preview = window.videoPreview
        deadline = time.monotonic() + 5
        readiness = None
        while time.monotonic() < deadline:
            QTest.qWait(10)
            selected = preview.transforming_clip
            if (not selected or selected.id != clip.id
                    or len(preview.transforming_clips) != 1
                    or preview.transform is None or preview.clipBounds is None
                    or preview.delayed_resize_timer.isActive()):
                continue
            fps = app.project.get("fps")
            frame_number = preview._get_clip_frame_number(selected, fps["num"] / fps["den"])
            rect, properties = preview._clip_rect(
                selected, preview.transforming_clip_object,
                preview.centeredViewport(preview.width(), preview.height()), frame_number)
            expected = preview._build_clip_transform(
                rect.x(), rect.y(), rect.width(), rect.height(), properties)[0]
            local_points = (QPointF(0, 0), QPointF(rect.width(), rect.height()))
            readiness = [abs(expected.map(p).x() - preview.transform.map(p).x())
                         + abs(expected.map(p).y() - preview.transform.map(p).y())
                         for p in local_points]
            if (max(readiness) < 0.5
                    and abs(preview.clipBounds.width() - rect.width()) < 0.5
                    and abs(preview.clipBounds.height() - rect.height()) < 0.5):
                break
        else:
            raise AssertionError("Transform overlay did not match selected clip: %r" % readiness)
        assert preview.transforming_clip.id == clip.id
        assert preview.transforming_clip_object.Id() == clip.id
        # Target the painted block's interior, away from corner/shear/origin handles.
        # Hiding the text toolbar changes the viewport; its old source-space
        # target is not a reliable pointer position until layout and paint settle.
        local_point = QPointF(preview.clipBounds.width() * 0.25,
                             preview.clipBounds.height() * 0.35)
        point = preview.transform.map(local_point).toPoint()
        QCoreApplication.sendEvent(window.videoPreview, QMouseEvent(QEvent.MouseMove, QPointF(point), Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        assert preview.hover_transform_mode == "location", preview.hover_transform_mode
        QTest.mousePress(window.videoPreview, Qt.LeftButton, pos=point)
        assert preview.mouse_pressed and preview.transform_mode == "location"
        QCoreApplication.sendEvent(window.videoPreview, QMouseEvent(QEvent.MouseMove, QPointF(point + QPoint(30, 15)), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.mouseRelease(window.videoPreview, Qt.LeftButton, pos=point + QPoint(30, 15))
        assert Clip.get(id=clip.id).data['location_x']['Points'][0]['co']['Y'] != before_drag
        # Ordinary dragging after the playhead moved updates the initial static point.
        window.videoPreview.updateClipProperty(clip.id,60,'location_x',0.1)
        assert len(Clip.get(id=clip.id).data['location_x']['Points'])==1
        app.project.save(root+'/project.osp')
        assert os.path.exists(Clip.get(id=clip.id).data['reader']['path'])
        app.project.save(root+'/copy.osp')
        assert os.path.exists(Clip.get(id=clip.id).data['reader']['path'])
        app.project.load(root+'/copy.osp')
        assert Clip.get(id=clip.id).data['direct_text']['text'].endswith('漢字')
        print('saved/reopened',flush=True)
        # Export one real lossless frame and compare decoded pixels to native rendering.
        import openshot
        timeline=window.timeline_sync.timeline
        timeline.SetMaxSize(app.project.get('width'),app.project.get('height'))
        frame=timeline.GetFrame(1)
        writer=openshot.FFmpegWriter(root+'/text.mov')
        writer.SetVideoOptions(True,'png',openshot.Fraction(30,1),frame.GetWidth(),frame.GetHeight(),openshot.Fraction(1,1),False,False,2000000)
        writer.Open()
        writer.WriteFrame(frame)
        writer.Close()
        reader=openshot.FFmpegReader(root+'/text.mov')
        reader.Open()
        decoded=reader.GetFrame(1)
        expected=frame.GetPixelsBytes()
        actual=decoded.GetPixelsBytes()
        assert expected==actual, 'Lossless export pixels differ'
        reader.Close()
        # External export action commits drafts before constructing its dialog.
        controller.begin(clip.id)
        controller.editor.insertPlainText(' export')
        with patch('windows.export.Export') as dialog:
            window.actionExportVideo_trigger()
        assert controller.draft is None and Clip.get(id=clip.id).data['direct_text']['text'].endswith(' export')
        # Failed/obsolete snapshots do not change persisted alpha or reopen an editor.
        alpha=copy.deepcopy(Clip.get(id=clip.id).data["alpha"])
        controller.begin(clip.id)
        controller.snapshot_ready(None,controller.generation,"intentional test failure")
        assert Clip.get(id=clip.id).data["alpha"]==alpha
        controller.cancel()
        QTest.qWait(100)
        assert not controller.view.isVisible()
        # New playhead reuses actual last text style and evaluated static geometry.
        controller.begin(clip.id)
        assert controller.apply_property(clip.id, "font_bold", True)
        controller.finish()
        previous = copy.deepcopy(Clip.get(id=clip.id).data)
        window.SeekSignal.emit(900, True)
        QTest.qWait(80)
        QTest.mouseClick(button, Qt.LeftButton)
        new_id = controller.clip_id
        new_data = Clip.get(id=new_id).data
        assert new_data["direct_text"]["text"] == "Text"
        assert controller.editor.textCursor().selectedText() == "Text" and controller.editor.hasFocus()
        assert new_data["position"] != previous["position"]
        for key in ("font_family", "font_size", "font_bold", "font_italic", "color", "background", "alignment", "width"):
            assert new_data["direct_text"].get(key, False) == previous["direct_text"].get(key, False), key
        for key in ("location_x", "location_y", "scale_x", "scale_y", "rotation"):
            assert len(new_data[key]["Points"]) == 1
            assert new_data[key]["Points"][0]["co"]["Y"] == previous[key]["Points"][0]["co"]["Y"], key
        controller.cancel()
        assert Clip.get(id=new_id) is not None
        controller.begin(clip.id)
        Clip.get(id=clip.id).delete()
        assert controller.draft is None
        controller.finish()
        assert Clip.get(id=clip.id) is None
        print('TEXT_WORKFLOW_PASSED',flush=True)
        controller.snapshot_pool.waitForDone(10000)
        passed=True
    except Exception:
        traceback.print_exc()
    finally:
        app.quit()
assert app.gui()
QTimer.singleShot(4000,verify)
app.exec_()
assert passed
