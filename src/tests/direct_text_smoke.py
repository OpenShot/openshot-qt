import os,tempfile,time,traceback,sys,importlib,copy,json
from unittest.mock import patch
root=tempfile.mkdtemp(prefix='openshot-text-smoke-')
original_expanduser=os.path.expanduser
os.path.expanduser=lambda path: root if path=='~' else original_expanduser(path)
from classes.app import OpenShotApp
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
        QTest.mouseClick(window.videoPreview,Qt.LeftButton,pos=window.videoPreview.rect().center())
        print('entry ms',1000*(time.perf_counter()-t),flush=True)
        assert controller.draft is not None
        deadline = time.monotonic() + 5
        while not controller.background_ready and time.monotonic() < deadline:
            QTest.qWait(10)
        assert controller.background_ready
        assert not controller.background_image.isNull()
        assert controller.background_image.pixelColor(20, 20).name() == "#16395d", controller.background_image.pixelColor(20, 20).name()
        QTest.keyClicks(controller.editor,'Hello')
        QTest.keyClick(controller.editor,Qt.Key_Return)
        controller.editor.insertPlainText('العربية café 🎉')
        assert 'Hello\n' in controller.editor.toPlainText()
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
        from qt_api import QPushButton
        done = next(widget for widget in controller.toolbar.findChildren(QPushButton) if widget.text() == "Done")
        assert done.isVisible()
        QTest.mouseClick(done, Qt.LeftButton)
        assert not Clip.get(id=clip.id).data['direct_text']['text'].endswith(' independent')
        # Native transform hit mapping at rotation and scaled preview.
        transformed=Clip.get(id=clip.id)
        transformed.data['rotation']['Points'][0]['co']['Y']=25
        transformed.data['scale_x']['Points'][0]['co']['Y']=0.8
        transformed.data['scale_y']['Points'][0]['co']['Y']=0.8
        transformed.save()
        window.preview_thread.current_frame=1
        from qt_api import QPointF,QInputMethodEvent,QCoreApplication,QEvent,QMouseEvent
        mapped=controller.geometry(transformed.data).map(QPointF(30,30))
        assert controller.hit(mapped)==clip.id
        controller.begin(clip.id)
        input_event=QInputMethodEvent()
        input_event.setCommitString('漢字')
        QCoreApplication.sendEvent(controller.editor,input_event)
        assert controller.editor.toPlainText().endswith('漢字')
        controller.finish()
        # Drive the real preview transform handlers with Qt mouse events.
        before_drag = Clip.get(id=clip.id).data['location_x']['Points'][0]['co']['Y']
        window.TransformSignal.emit([clip.id])
        QTest.qWait(30)
        point = controller.geometry(Clip.get(id=clip.id).data).map(QPointF(40, 40)).toPoint()
        QCoreApplication.sendEvent(window.videoPreview, QMouseEvent(QEvent.MouseMove, QPointF(point), Qt.NoButton, Qt.NoButton, Qt.NoModifier))
        QTest.mousePress(window.videoPreview, Qt.LeftButton, pos=point)
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
