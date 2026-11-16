"""Clip-icon selection and deletion must use complete animation data."""
import copy
import types
import unittest
from unittest.mock import Mock

from qt_api import QColor, QImage, QPainter, QPen, QPointF, QRectF, Qt
from windows.views.timeline_backend.qwidget.clip import ClipInteractionMixin
from windows.views.timeline_backend.qwidget.keyframe import KeyframeMixin
from windows.views.timeline_backend.paint.keyframe import KeyframePainter, visible_keyframe_markers


def curve(frames):
    return {'Points':[{'co':{'X':f,'Y':f/100},'interpolation':1} for f in frames]}


class SelectionHelper(KeyframeMixin, ClipInteractionMixin):
    def __init__(self, effects=False):
        self.clip=types.SimpleNamespace(id='C1',data={'id':'C1','start':0,'end':10,'layer':1,
            'scale_x':curve(range(1,102)), 'alpha':curve(range(1,102)), 'effects':[]})
        if effects:
            self.clip.data['effects']=[{'id':'E1','class_name':'Distort','point_5_x':curve(range(1,102))}]
        self.fps_float=10
        self.pixels_per_second=10
        self._pending_clip_overrides={}
        self._pending_transition_overrides={}
        self._selected_keyframe_keys=set()
        self._panel_selected_keyframes={}
        self._panel_properties={}
        self._live_transform_drawing=False
        self._active_keyframe_marker=None
        self._press_keyframe=None
        self._dragging_keyframe=None
        self._dragging_panel_keyframes=None
        self._panel_box_track=None
        self._snap_keyframe_seconds=[]
        self._keyframes_dirty=False
        self.keyframe_painter=types.SimpleNamespace(size=10,fill=QColor('blue'))
        self.geometry=types.SimpleNamespace(ensure=Mock(),mark_dirty=Mock(),
            _current_view_state=lambda:{},iter_clips=lambda **kw:[(QRectF(100,40,100,40),self.clip,True)],
            iter_transitions=lambda **kw:[],iter_items=lambda:[(QRectF(100,40,100,40),self.clip,True,'clip')])
        self.clip_updates=[]
        def save(data,**kwargs):
            self.clip_updates.append(copy.deepcopy(data))
            self.clip.data=copy.deepcopy(data)
        self.win=types.SimpleNamespace(selected_clips=['C1'],selected_transitions=[],
            clearSelections=Mock(),addSelection=Mock(),timeline=types.SimpleNamespace(update_clip_data=save))
        self.update=Mock()
        self.changed=Mock()
        self._clear_panel_selection=Mock()
        self._update_track_panel_properties=Mock()
        self._panel_lane_at=lambda pos:None
        self._panel_track_at_pos=lambda pos:None
        self._selected_effect_ids=lambda:set()
        self.track_name_width=0
        self.width=lambda:400

    def box(self,rect,ctrl=False):
        mods=Qt.ControlModifier if ctrl else Qt.NoModifier
        self._last_event=types.SimpleNamespace(modifiers=lambda:mods,position=lambda:rect.topLeft())
        self._startBoxSelect()
        self._last_event=types.SimpleNamespace(modifiers=lambda:mods,position=lambda:rect.bottomRight())
        self._boxMove()
        self._finishBoxSelect()


class ClipKeyframeSelectionTests(unittest.TestCase):
    def test_live_distort_markers_use_recorded_effect_before_commit(self):
        from windows.views.timeline_backend.qwidget.base import TimelineWidgetBase

        helper = SelectionHelper(effects=True)
        committed = helper.clip.data['effects'][0]
        committed['point_5_x'] = curve([1])
        live = copy.deepcopy(committed)
        live['point_5_x'] = curve([1, 31, 61])
        helper.win.videoPreview = types.SimpleNamespace(
            _live_transform_effects={'E1': types.SimpleNamespace(data=live)})
        helper._live_transform_pending = True
        TimelineWidgetBase.refresh_live_transform(helper)

        frames = {m['frame'] for m in helper._keyframe_markers
                  if m.get('effect_id') == 'E1'}
        self.assertEqual(frames, {1, 31, 61})
        self.assertEqual(committed['point_5_x'], curve([1]))
        self.assertFalse(helper._live_transform_drawing)
        helper.update.assert_called_once()

    def test_box_selects_hidden_frames_and_delete_preserves_clip(self):
        helper=SelectionHelper(effects=True)
        all_markers=helper._complete_keyframe_markers()
        visible=list(visible_keyframe_markers(all_markers,QRectF(0,0,400,200),5))
        helper.box(QRectF(125,73,20,13))
        self.assertIn(('clip','C1',31),helper._selected_keyframe_keys)
        self.assertIn(('clip','C1',32),helper._selected_keyframe_keys)
        self.assertIn(('effect','E1',32),helper._selected_keyframe_keys)
        visible_keys={marker['key'] for marker in visible}
        self.assertTrue(helper._selected_keyframe_keys-visible_keys)
        selected_frames={key[2] for key in helper._selected_keyframe_keys if key[0]=='clip'}
        helper.win.clearSelections.assert_not_called()
        self.assertTrue(helper.delete_selected_keyframes())
        self.assertEqual(len(helper.clip_updates),1)
        self.assertEqual(helper.clip.data['id'],'C1')
        for data in (helper.clip.data['scale_x'],helper.clip.data['alpha'],helper.clip.data['effects'][0]['point_5_x']):
            self.assertEqual({p['co']['X'] for p in data['Points']}, set(range(1,102))-selected_frames)
        self.assertEqual(helper._selected_keyframe_keys,set())

    def test_box_ignores_live_paint_sampling_and_ctrl_adds(self):
        helper=SelectionHelper()
        helper._live_transform_drawing=True
        helper.box(QRectF(125,73,10,13))
        first=set(helper._selected_keyframe_keys)
        self.assertTrue(helper._live_transform_drawing)
        helper.box(QRectF(165,73,10,13),ctrl=True)
        self.assertTrue(first < helper._selected_keyframe_keys)
        self.assertIn(('clip','C1',71),helper._selected_keyframe_keys)

    def test_box_without_keyframes_still_selects_clips(self):
        helper=SelectionHelper()
        helper.box(QRectF(110,45,30,15))
        self.assertFalse(helper._selected_keyframe_keys)
        helper.win.clearSelections.assert_called_once()
        helper.win.addSelection.assert_called_once_with('C1','clip',False)

    def test_delete_rebuilds_paths_after_another_edit(self):
        helper=SelectionHelper()
        helper._selected_keyframe_keys={('clip','C1',31)}
        helper.clip.data['scale_x']['Points'].insert(1,{'co':{'X':1.5,'Y':0},'interpolation':1})
        self.assertTrue(helper.delete_selected_keyframes())
        remaining={p['co']['X'] for p in helper.clip.data['scale_x']['Points']}
        self.assertNotIn(31,remaining)
        self.assertIn(30,remaining)
        self.assertIn(32,remaining)
        self.assertIn(1.5,remaining)

    def test_stale_keyframe_selection_consumes_delete(self):
        helper=SelectionHelper()
        helper._selected_keyframe_keys={('clip','gone',31)}
        self.assertTrue(helper.delete_selected_keyframes())
        self.assertFalse(helper.clip_updates)

    def test_selected_frame_has_priority_in_a_thinned_bucket(self):
        markers=[{'key':('clip','C1',1),'type':'clip','owner_id':'C1','rect':QRectF(10,10,10,10),'selected':True},
                 {'key':('clip','C1',2),'type':'clip','owner_id':'C1','rect':QRectF(11,10,10,10),
                  'selected':True,'keyframe_selected':True}]
        self.assertEqual(list(visible_keyframe_markers(markers,QRectF(0,0,100,100),10)),[markers[1]])

    def test_selected_icon_gets_visible_border_like_panel(self):
        key=('clip','C1',20)
        widget=types.SimpleNamespace(theme=types.SimpleNamespace(keyframe_fill=QColor('blue'),
            keyframe_border=QColor('white'),keyframe_size=10),track_name_width=0,ruler_height=0,
            scroll_bar_thickness=0,width=lambda:50,height=lambda:50,
            _keyframe_markers=[{'key':key,'type':'clip','owner_id':'C1','rect':QRectF(20,20,10,10),
                               'selected':True,'interpolation':'linear','color':QColor('blue')}],
            _selected_keyframe_keys=set(),keyframe_panel_painter=types.SimpleNamespace(marker_pen_selected=QPen(QColor('white'),1.2)))
        renderer=KeyframePainter(widget)
        counts=[]
        for selected in (False,True):
            widget._selected_keyframe_keys={key} if selected else set()
            image=QImage(50,50,QImage.Format_ARGB32_Premultiplied)
            image.fill(QColor('black'))
            painter=QPainter(image)
            renderer.paint(painter)
            painter.end()
            counts.append(sum(image.pixelColor(x,y).red() for x in range(50) for y in range(50)))
        self.assertGreater(counts[0],0)
        self.assertGreater(counts[1],counts[0])

    def test_click_targets_visible_glyph_not_hidden_neighbour(self):
        helper=SelectionHelper()
        helper.ruler_height=0
        helper.scroll_bar_thickness=0
        helper.height=lambda:200
        helper._ensure_keyframe_markers=Mock()
        first={'key':('clip','C1',1),'type':'clip','owner_id':'C1','rect':QRectF(10,10,10,10)}
        second={'key':('clip','C1',2),'type':'clip','owner_id':'C1','rect':QRectF(11,10,10,10)}
        helper._keyframe_markers=[first,second]
        self.assertIs(helper._get_keyframe_at(QPointF(15,15)),first)

    def test_dragged_key_keeps_selection_at_its_new_frame(self):
        helper=SelectionHelper()
        marker={'key':('clip','C1',31),'clip':helper.clip,'type':'clip','frame':41}
        helper._selected_keyframe_keys={('clip','C1',31),('clip','C1',15)}
        helper._dragging_keyframe={'marker':marker,'pending_frame':41,'current_frame':41,
                                  'moved':True,'transaction_started':False}
        helper._seek_to_marker_frame=Mock()
        helper._release_cursor=Mock()
        helper._finishKeyframeDrag()
        self.assertEqual(helper._selected_keyframe_keys,{('clip','C1',41),('clip','C1',15)})
        self.assertEqual(helper._active_keyframe_marker['key'],('clip','C1',41))


class KeyframeBoxGestureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from qt_api import QApplication
        from tests.qt_test_app import get_or_create_app
        cls.app, _ = get_or_create_app(lambda: QApplication([]))

    def make_widget(self, panel=False):
        from qt_api import QWidget
        from windows.views.timeline_backend.qwidget.base import TimelineWidgetBase, TimelineEvents
        from windows.views.timeline_backend.qwidget.keyframe_panel import KeyframePanelMixin

        class GestureWidget(SelectionHelper, KeyframePanelMixin, QWidget):
            _buildStateMachine = TimelineWidgetBase._buildStateMachine
            _event_signal = TimelineWidgetBase._event_signal
            _event_signal_bytes = TimelineWidgetBase._event_signal_bytes
            _add_simple_transition = TimelineWidgetBase._add_simple_transition
            _safe_disconnect = TimelineWidgetBase._safe_disconnect

            def __init__(self):
                QWidget.__init__(self)
                SelectionHelper.__init__(self)
                self.starts = 0
                self.finishes = 0
                self.panel_visible = True
                def clear_owners():
                    self.win.selected_clips = []
                    self.panel_visible = False
                self.win.clearSelections.side_effect = clear_owners
                self._transitions = []
                self.events = TimelineEvents(self)
                for name in ('_startPlayhead','_finishPlayhead','_playheadMove','_disable_playback_caching'):
                    setattr(self,name,Mock())
                self._press_hit = 'panel' if panel else 'background'
                self.normalize_track_number = lambda number: number
                if panel:
                    prop={'key':'scale_x','points':[
                        {'frame':31,'seconds':3.0},{'frame':32,'seconds':3.1},{'frame':80,'seconds':8.0}]}
                    lane={'track':1,'property':prop,'combined_rect':QRectF(100,100,100,40),
                          'lane_rect':QRectF(100,100,100,40),'lane_padding':0}
                    self._panel_properties={1:{'properties':[prop], 'item_type':'clip', 'item_id':'C1',
                        'context':{'item_type':'clip','item_id':'C1','clip_id':'C1'}}}
                    self._panel_lane_at=lambda pos:lane if lane['combined_rect'].contains(pos) else None
                    self._panel_bounds_for_track=lambda track:lane['combined_rect']
                    self._iter_panel_lanes=lambda:[lane]
                    self._panel_lane_padding=lambda:0
                    self._panel_marker_rect=lambda rect,padding,seconds:QRectF(95+seconds*10,115,10,10)
                self._buildStateMachine()

            def _startBoxSelect(self):
                self.starts += 1
                ClipInteractionMixin._startBoxSelect(self)

            def _finishBoxSelect(self):
                self.finishes += 1
                ClipInteractionMixin._finishBoxSelect(self)

        widget = GestureWidget()
        self.addCleanup(widget.deleteLater)
        self.app.processEvents()
        return widget

    def gesture(self,widget,rect,reverse=False):
        def event(position):
            return types.SimpleNamespace(position=lambda:position,modifiers=lambda:Qt.NoModifier)
        widget._last_event=event(rect.bottomRight() if reverse else rect.topLeft())
        widget.events.pressed.emit(widget._last_event)
        self.app.processEvents()
        widget._last_event=event(rect.topLeft() if reverse else rect.bottomRight())
        widget.events.moved.emit(widget._last_event)
        self.app.processEvents()
        widget.events.released.emit(widget._last_event)
        self.app.processEvents()
        self.app.processEvents()

    def test_clip_box_gesture_finishes_once_and_keeps_owner_and_panel(self):
        widget=self.make_widget()
        self.gesture(widget,QRectF(125,73,20,13))
        self.assertEqual(widget.starts,1)
        self.assertEqual(widget.finishes,1)
        self.assertIn(('clip','C1',31),widget._selected_keyframe_keys)
        self.assertEqual(widget.win.selected_clips,['C1'])
        self.assertTrue(widget.panel_visible)
        widget.win.clearSelections.assert_not_called()

    def test_panel_box_gesture_keeps_selected_frames_and_panel_open(self):
        widget=self.make_widget(panel=True)
        self.gesture(widget,QRectF(125,110,20,20))
        self.assertEqual(widget.starts,1)
        self.assertEqual(widget.finishes,1)
        self.assertEqual(widget._panel_selected_keyframes[1]['scale_x'],{31,32})
        self.assertEqual(widget.win.selected_clips,['C1'])
        self.assertTrue(widget.panel_visible)
        widget.win.clearSelections.assert_not_called()

    def test_panel_marquee_can_reach_clip_edge_and_select_both_levels(self):
        widget=self.make_widget(panel=True)
        self.gesture(widget,QRectF(125,73,20,57),reverse=True)
        self.assertEqual(widget.starts,1)
        self.assertEqual(widget.finishes,1)
        self.assertIn(('clip','C1',31),widget._selected_keyframe_keys)
        self.assertIn(('clip','C1',32),widget._selected_keyframe_keys)
        self.assertEqual(widget._panel_selected_keyframes[1]['scale_x'],{31,32})
        self.assertEqual(widget.win.selected_clips,['C1'])
        self.assertTrue(widget.panel_visible)
        widget.win.clearSelections.assert_not_called()

    def test_two_top_columns_select_all_five_child_rows_and_delete_them(self):
        widget=self.make_widget(panel=True)
        context={'item_type':'clip','item_id':'C1','clip_id':'C1'}
        properties=[]
        for name in ('scale_x','alpha','scale_y','location_x','location_y'):
            widget.clip.data[name]=curve((1,31,32,80))
            properties.append({'key':name,'context':context,
                'source_meta':{'owner':'clip','clip':widget.clip},
                'points':[{'frame':f,'seconds':(f-1)/10,
                    'path':(('dict',name),('dict','Points'),('list',(1,31,32,80).index(f)))} for f in (31,32,80)]})
        widget._panel_properties[1]['properties']=properties
        # Only the two edge icons: no panel row lies inside this rectangle.
        self.gesture(widget,QRectF(129.75,73,1.5,13))
        self.assertEqual(widget._selected_keyframe_keys,{('clip','C1',31),('clip','C1',32)})
        for prop in properties:
            self.assertEqual({point['frame'] for point in prop['points'] if point.get('selected')},{31,32})
        self.assertTrue(widget.delete_selected_keyframes())
        self.assertEqual(len(widget.clip_updates),1)
        for name in ('scale_x','alpha','scale_y','location_x','location_y'):
            self.assertNotIn(31,{p['co']['X'] for p in widget.clip.data[name]['Points']})
            self.assertNotIn(32,{p['co']['X'] for p in widget.clip.data[name]['Points']})
            self.assertIn(80,{p['co']['X'] for p in widget.clip.data[name]['Points']})

    def test_dragging_selected_top_column_moves_both_columns_in_all_rows(self):
        widget=self.make_widget(panel=True)
        context={'item_type':'clip','item_id':'C1','clip_id':'C1'}
        properties=[]
        for name in ('scale_x','alpha','scale_y','location_x','location_y'):
            widget.clip.data[name]=curve((1,31,32,80))
            properties.append({'key':name,'context':context,
                'source_meta':{'owner':'clip','clip':widget.clip},
                'points':[{'frame':f,'seconds':(f-1)/10,
                    'path':(('dict',name),('dict','Points'),('list',(1,31,32,80).index(f)))} for f in (31,32,80)]})
        widget._panel_properties[1]['properties']=properties
        self.gesture(widget,QRectF(129.75,73,1.5,13))
        marker=next(m for m in widget._complete_keyframe_markers() if m['key']==('clip','C1',31))
        widget._press_keyframe=marker
        widget._press_hit='keyframe'
        widget._press_keyframe_clear=False
        widget._compute_keyframe_snap_targets=lambda marker:[]
        widget._fix_cursor=Mock()
        widget._release_cursor=Mock()
        widget.cursors={}
        widget._snap_time=lambda seconds:seconds
        widget._apply_keyframe_snapping=lambda drag,seconds:seconds
        widget._seek_to_marker_frame=Mock()
        widget.win.timeline.StartKeyframeDrag=Mock()
        widget.win.timeline.FinalizeKeyframeDrag=Mock()
        event=lambda x:types.SimpleNamespace(position=lambda:QPointF(x,79.5),modifiers=lambda:Qt.NoModifier)
        widget._last_event=event(130)
        widget.events.pressed.emit(widget._last_event)
        self.app.processEvents()
        self.assertEqual(len(widget._dragging_keyframe['selected_markers']),2)
        widget._last_event=event(135)
        widget.events.moved.emit(widget._last_event)
        self.app.processEvents()
        for prop in properties:
            self.assertEqual({point['frame'] for point in prop['points'] if point.get('selected')},{36,37})
        widget.events.released.emit(widget._last_event)
        self.app.processEvents()
        self.assertEqual(len(widget.clip_updates),1)
        for name in ('scale_x','alpha','scale_y','location_x','location_y'):
            self.assertEqual([p['co']['X'] for p in widget.clip.data[name]['Points']],[1,36,37,80])
        self.assertEqual(widget._selected_keyframe_keys,{('clip','C1',36),('clip','C1',37)})
        widget.win.timeline.StartKeyframeDrag.assert_called_once()
        widget.win.timeline.FinalizeKeyframeDrag.assert_called_once()
