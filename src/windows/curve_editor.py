"""
 @file
 @brief This file creates the Curve Editor dock window to view and edit animation keys for OpenShot
 @author SuslikV
"""

import os
from sys import float_info
from enum import Enum
from PyQt5.QtWidgets import QDockWidget, QGraphicsScene, QGraphicsView, QGraphicsRectItem, QGraphicsPathItem, QWidget, QScrollBar, QHBoxLayout, QVBoxLayout, QDialogButtonBox, QSpinBox, QDialog, QFormLayout, QCheckBox
from PyQt5.QtGui import QBrush, QPen, QPalette, QPainterPath, QColor
from PyQt5.QtCore import Qt, QRectF, QLineF, QPointF
from classes import info, ui_util, settings
from datetime import timedelta
from classes.app import get_app
from classes.conversion import zoomToSeconds
from classes.logger import log
from classes.query import Clip, Transition, Effect

class CurveEditor(QDockWidget):
    """ This class is the Curve Editor dock window for OpenShot animations edit
    """

    def __init__(self, parent):
        super().__init__(parent)

        # View and Scene
        self.graph = None
        self.scene = None

        self.loadEditorUI()
        self.newGraphScene()

        # Initial Grid settings
        self.autoGrid = True
        self.shareTimelineScale = False

        # Slider connection is not yet established
        self.sliderCon = None

        self.settWindow = None
        geometry = self.getLoaded_Settings()
        if geometry:
            log.info("Loaded grid {}".format(geometry))
            self.applyGiven_Settings(geometry)
        else:
            # Apply defaults
            self.applyGiven_Settings()

        self.graph.centerOn(0, 0)

        self.chk_show_full.stateChanged.connect(self.refreshSceneDrawing)

    def checkScaleSliderBinding(self):
        # Connect or disconnect main UI Timeline's Scale slider from the Curve Editor
        if self.shareTimelineScale:
            self.sliderCon = get_app().window.sliderZoom.valueChanged.connect(self.sldrZoomTime.setSliderPosition)
            self.sldrZoomTime.setSliderPosition(get_app().window.sliderZoom.value())
        elif self.sliderCon:
            get_app().window.sliderZoom.valueChanged.disconnect(self.sliderCon)
            self.sliderCon = None

    def updateAreaScrollsPolicy(self):
        # Disable Scrolls and ignore Wheel events for invisible View scrolls
        if self.autoGrid:
            self.graph.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.graph.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.graph.verticalScrollBar().blockSignals(True)
            self.graph.horizontalScrollBar().blockSignals(True)
        else:
            self.graph.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.graph.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.graph.verticalScrollBar().blockSignals(False)
            self.graph.horizontalScrollBar().blockSignals(False)

    def resizeEvent(self, event):
        if self.isVisible() and self.autoGrid:
            geometry = self.getCurrentScene_Settings()
            w = self.graph.width()
            h = self.graph.height()
            x_num = int((w - self.scene.gridMarginL - self.scene.gridMarginR) / geometry[0])
            y_num = int((h - self.scene.gridMarginT - self.scene.gridMarginB) / geometry[1])

            # Set limits on Grid minimum size
            if x_num < 2:
                x_num = 2
            if y_num < 2:
                y_num = 2
            geometry[2] = x_num
            geometry[3] = y_num

            if self.settWindow:
                # Inform user of new values
                self.fillComboBoxes(geometry)

            self.applyGiven_Settings(geometry)
            self.saveGiven_Settings(geometry)

    def closeEvent(self, event):
        get_app().window.curve_editor_enable = False

    def loadEditorUI(self):
        """ Load editor's UI from the xml file """
        # Path to ui file
        ui_path = os.path.join(info.PATH, 'windows', 'ui', 'curve-editor.ui')

        # Load UI from designer
        ui_util.load_ui(self, ui_path)

        # Init UI (now 'self' is QDockWidget with object's name "dockCurveEditor" from .ui file)
        ui_util.init_ui(self)

    def newGraphScene(self):
        """ Init the Qt Graphics View Framework """
        self.graph = GraphView()
        self.graph.setObjectName('OPSHgraph')
        self.graphArea2grid.addWidget(self.graph, 1, 1)
        self.scene = GraphScene()
        self.graph.setScene(self.scene)

    def setInfoLabels(self, obj_txt, prop_txt):
        self.prop_name.setText(prop_txt)
        self.obj_name.setText(obj_txt)

    def actionZoom_Y_axis_1_trigger(self, event):
        # Reset Value axis zoom to x1.0
        self.sldrZoomVal.setSliderPosition(10)

    def actionCurveEditorSettings_trigger(self, event):
        # Get translation function
        _ = get_app()._tr

        # Grid Settings window
        self.settWindow = QDialog(self)

        # No help button window
        self.settWindow.setWindowFlags(self.settWindow.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.settWindow.setWindowTitle( _("Curve Editor Settings") )

        self.combo_cell_width = QSpinBox()
        self.combo_cell_width.setMinimum(20)
        self.combo_cell_width.setMaximum(400)
        self.combo_cell_height = QSpinBox()
        self.combo_cell_height.setMinimum(20)
        self.combo_cell_height.setMaximum(400)
        self.combo_cells_x_num = QSpinBox()
        self.combo_cells_x_num.setMinimum(2)
        self.combo_cells_x_num.setMaximum(200)
        self.combo_cells_y_num = QSpinBox()
        self.combo_cells_y_num.setMinimum(2)
        self.combo_cells_y_num.setMaximum(200)
        self.chk_fit_into_window = QCheckBox()
        self.chk_share_time_slider = QCheckBox()
        self.fillComboBoxes(self.getCurrentScene_Settings())
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel | QDialogButtonBox.Apply | QDialogButtonBox.Reset, self.settWindow)
        self.buttonBox.clicked.connect(self.setSettings)

        # Initial Settings UI appearance
        layout = QFormLayout()
        layout.addRow( _("Cell Width"), self.combo_cell_width)
        layout.addRow( _("Cell Height"), self.combo_cell_height)
        layout.addRow( _("Auto-Grid"), self.chk_fit_into_window)
        self.chk_fit_into_window.setChecked(self.autoGrid)
        layout.addRow( _("Grid Width (in cells)"), self.combo_cells_x_num)
        layout.addRow( _("Grid Height (in cells)"), self.combo_cells_y_num)
        layout.addRow( _("Use Timeline Scale Slider"), self.chk_share_time_slider)
        self.chk_share_time_slider.setChecked(self.shareTimelineScale)

        if self.chk_fit_into_window.isChecked():
            self.combo_cells_x_num.setEnabled(False)
            self.combo_cells_y_num.setEnabled(False)
            layout.labelForField(self.combo_cells_x_num).setEnabled(False)
            layout.labelForField(self.combo_cells_y_num).setEnabled(False)

        self.label_x_num = layout.labelForField(self.combo_cells_x_num)
        self.label_y_num = layout.labelForField(self.combo_cells_y_num)

        spacer_layout = QHBoxLayout()
        spacer_layout.setContentsMargins(0, 11, 0, 11) # Space at top and bottom
        layout.addRow(spacer_layout)
        layout.addRow(self.buttonBox)
        self.settWindow.setLayout(layout)

        # Use Grid Settings window signals to toggle visibility of UI elements
        self.chk_fit_into_window.stateChanged.connect(self.autoGridToggle)

        self.settWindow.show()

    def autoGridToggle(self, state):
        # Toggle UI elements of the Settings window
        if self.settWindow:
            if state == Qt.Unchecked:
                self.combo_cells_x_num.setEnabled(True)
                self.combo_cells_y_num.setEnabled(True)
                self.label_x_num.setEnabled(True)
                self.label_y_num.setEnabled(True)
            else:
                self.combo_cells_x_num.setEnabled(False)
                self.combo_cells_y_num.setEnabled(False)
                self.label_x_num.setEnabled(False)
                self.label_y_num.setEnabled(False)

    def setSettings(self, button):
        if button == self.buttonBox.button(QDialogButtonBox.Save):
            geometry = self.getCurrentCombo_Settings()
            self.applyGiven_Settings(geometry)
            self.saveGiven_Settings(geometry)
            self.settWindow.close()
        elif button == self.buttonBox.button(QDialogButtonBox.Cancel):
            self.settWindow.close()
        elif button == self.buttonBox.button(QDialogButtonBox.Reset):
            self.applyGiven_Settings()
            self.fillComboBoxes(self.getCurrentScene_Settings())
            self.chk_fit_into_window.setChecked(True)
            self.chk_share_time_slider.setChecked(False)
        elif button == self.buttonBox.button(QDialogButtonBox.Apply):
            self.applyGiven_Settings(self.getCurrentCombo_Settings())

    def fillComboBoxes(self, geometry):
        self.combo_cell_width.setValue(geometry[0])
        self.combo_cell_height.setValue(geometry[1])
        self.combo_cells_x_num.setValue(geometry[2])
        self.combo_cells_y_num.setValue(geometry[3])

    def getCurrentCombo_Settings(self):
        # Returns current settings from dialog window
        geometry = [100, 60, 8, 5, 1, 0]
        geometry[0] = self.combo_cell_width.value()
        geometry[1] = self.combo_cell_height.value()
        geometry[2] = self.combo_cells_x_num.value()
        geometry[3] = self.combo_cells_y_num.value()

        if self.chk_fit_into_window.isChecked():
            geometry[4] = 1
        else:
            geometry[4] = 0

        if self.chk_share_time_slider.isChecked():
            geometry[5] = 1
        else:
            geometry[5] = 0

        return geometry

    def getCurrentScene_Settings(self):
        # Returns current scene grid settings
        geometry = [100, 60, 8, 5, 1, 0]
        if self.scene is not None:
            geometry[0] = self.scene.cell_width
            geometry[1] = self.scene.cell_height
            geometry[2] = self.scene.cells_x_num
            geometry[3] = self.scene.cells_y_num
            geometry[4] = self.autoGrid
            geometry[5] = self.shareTimelineScale
        return geometry

    def applyGiven_Settings(self, geometry=[100, 60, 8, 5, 1, 0]):
        # Applies given settings to the scene
        if self.scene is None:
            return

        self.scene.cell_width = geometry[0]
        self.scene.cell_height = geometry[1]
        self.scene.cells_x_num = geometry[2]
        self.scene.cells_y_num = geometry[3]

        # Any new Options should be added inside the try/except statement
        try:
            idx = 4
            self.autoGrid = geometry[idx]
            idx = 5
            self.shareTimelineScale = geometry[idx]
        except IndexError:
            log.error("Grid settings not found. Defaults will apply. Missing index #{}".format(idx))
            pass

        # New bounds
        width = self.scene.cell_width * self.scene.cells_x_num
        height = self.scene.cell_height * self.scene.cells_y_num
        self.scene.exposed = QRectF(0.0, 0.0, width, height)
        self.scene.removeItem(self.scene.gridBoundsItem)
        self.scene.addBoundsGridItem()

        # New Scene scrolls position and size
        self.scene.updateScrollersGeometry()
        self.refreshSceneDrawing()

        # The View adjustments
        self.updateAreaScrollsPolicy()
        self.checkScaleSliderBinding()

    def refreshSceneDrawing(self, state=0):
        if self.scene is None:
            return

        if not self.scene.refreshDrawing():
            # Redraw the axis painting (new grid)
            self.scene.update()

    def getLoaded_Settings(self):
        # Returns settings loaded form the storage
        s = settings.get_settings()
        geometry = s.get('curve_editor_grid')
        return geometry

    def saveGiven_Settings(self, geometry):
        # Save given settings to the storage
        s = settings.get_settings()
        s.set('curve_editor_grid', geometry)

class GraphView(QGraphicsView):
    """ This class is the part of the Graphics View Framework to view and edit curves
    """

    def __init__(self):
        QGraphicsView.__init__(self)

class Seg(Enum):
    # Curve segment types
    BEZIER = 0
    LINEAR = 1
    CONST_STEP = 2
    UNKNOWN_LINEAR = 101
    CONST_SHELF = 202
    BOUNDS_RECTANGLE = 1000
    KEYPOINT_RECTANGLE = 1010
    ROUNDED_RECT = 1020
    HANDLE_CIRCLE = 1030
    LEVER_LINE = 1040

class GraphScene(QGraphicsScene):
    """ This class is the part of the Graphics View Framework to view and edit curves
    """
    # Time axis grid pitch (X), in pixels
    cell_width = 100

    # Value axis grid pitch (Y), in pixels
    cell_height = 60

    # Number of grid cells
    cells_x_num = 8
    cells_y_num = 5

    # In terms of the OpenShot's Timeline the first frame is 00:00:00:Frame=1, while ruler shows only 00:00:00 (hh:mm:ss).
    # Thus the best position for the cursor disply point is between
    # the time 00:00:00.000 (hh:mm:ss.ms) and 00:00:00.1/fps, or in the middle of the frame time.
    # Rendering graph uses integer coordinates only, and rounding enlarges values.
    # Thus it is better to keep the start point closer to 00:00:00.000 (hh:mm:ss.ms) rather than to 00:00:00.1/fps
    #
    # How much the half of the frame is, float 0..1
    # When rendered, less = closer to the frame's end
    halfFrameRatioF = 0.6

    # Empty zone around the grid, in pixels (for axis numbering, left-top-right-bottom)
    gridMarginL = 60
    gridMarginT = 20
    gridMarginR = 60
    gridMarginB = 40

    def __init__(self):
        QGraphicsScene.__init__(self)

        # Get dock widget to update UI later
        self.crvEdt = get_app().window.findChild(QDockWidget, 'dockCurveEditor', Qt.FindDirectChildrenOnly)

        # Define brushes and pens for grid and splines painitng
        self.GraphBrush      = QBrush(self.palette().color(QPalette.Text), Qt.SolidPattern)
        self.GraphBrushEmpty = QBrush()
        self.GraphBrushDis   = QBrush(self.palette().color(QPalette.Disabled, QPalette.Text), Qt.SolidPattern)
        self.GraphPenDis     = QPen(self.GraphBrushDis, 0, Qt.SolidLine)
        self.GraphPenHigh    = QPen(QBrush(self.palette().color(QPalette.Highlight), Qt.SolidPattern), 2, Qt.SolidLine)
        self.GraphPenRedThin = QPen(QBrush(Qt.red, Qt.SolidPattern), 0, Qt.SolidLine)
        self.GraphPenEmpty   = QPen(Qt.NoPen)
        self.GraphPenHelper  = QPen(self.GraphBrush, 1, Qt.DashLine)
        self.GraphPenHelperR = QPen(QBrush(QColor(Qt.darkRed), Qt.SolidPattern), 1, Qt.SolidLine)
        self.GraphPenHelperG = QPen(QBrush(QColor(Qt.darkGreen), Qt.SolidPattern), 1, Qt.SolidLine)
        self.GraphPenHelperB = QPen(QBrush(QColor(Qt.darkBlue), Qt.SolidPattern), 1, Qt.SolidLine)
        self.GraphPenRed     = QPen(QBrush(QColor(Qt.darkRed), Qt.SolidPattern), 3, Qt.SolidLine)
        self.GraphPenGreen   = QPen(QBrush(QColor(Qt.darkGreen), Qt.SolidPattern), 3, Qt.SolidLine)
        self.GraphPenBlue    = QPen(QBrush(QColor(Qt.darkBlue), Qt.SolidPattern), 3, Qt.SolidLine)
        self.GraphPenLightB  = QPen(QBrush(QColor('#4b92ad'), Qt.SolidPattern), 2, Qt.SolidLine)
        self.GraphPen        = QPen(self.GraphBrush, 3, Qt.SolidLine)

        # Defult brush and pen for drawing curves
        self.curvePen = self.GraphPen
        self.curveBrush = self.GraphBrushEmpty

        # Default brush and pen for drawing clip bounds
        self.clipBoundsPen = self.GraphPenLightB
        self.clipBoundsBrush = self.GraphBrushEmpty

        # Background coordinate grid
        self.grid = []
        width = self.cell_width * self.cells_x_num
        height = self.cell_height * self.cells_y_num
        self.exposed = QRectF(0.0, 0.0, width, height) # 8 x 5 cells

        # Refresh drawing is in progress
        self.refreshingDrawing = False

        # Do not skip next refresh of the drawing
        self.skipRefresh = False

        # Get translation function
        _ = get_app()._tr

        # Show default value of zoom
        self.crvEdt.label_zoomTime.setText( _("{} seconds").format(zoomToSeconds(1)) )
        self.crvEdt.label_zoomVal.setText("x{:3.1f}".format(1.0))

        # Init impossible current frame
        self.cur_frame = 0
        self.getCurFrameSafe()

        # X axis zoom factor
        self.timeAxisScale = self.crvEdt.sldrZoomTime.sliderPosition()
        # Y axis zoom factor
        self.valueAxisScaleF = 10 / self.crvEdt.sldrZoomVal.sliderPosition()

        # Stores the cell height, in units
        self.cellHeightUnitsCachedF = 1.0

        # Initial size of the Value axis (to draw empty grid), in units
        self.maxValF = 1.0
        self.minValF = 0.0
        self.minMaxChanged = True
        self.lastMaxValF = self.maxValF
        self.lastMinValF = self.minValF
        self.lastZoomedMaxValF = self.maxValF
        self.lastZoomedMinValF = self.minValF

        # Initial Time axis minimum, grid offset (in seconds) and last frame (in frames) that fits into the current grid, 
        # The Timeline always starts from 0 seconds
        # The maximum (end frame) depends on grid size and scale (offset is zero 0 seconds, thus omitted)
        self.minTimeF = 0.0
        self.gridOffsetTime = 0
        self.gridEndFrame = self.getCellWidthFramesF() * self.cells_x_num

        # Start offset of the current curve element, in seconds
        self.elementOffsetTimeF = 0.0

        # Visual frame offset to draw key points in the middle of the frame, in pixels
        self.halfFrameOffsetF = 0.0

        # Default segment type to add
        self.segment_type = Seg.BEZIER

        # Last selected clip item
        self.lastClipItem = None

        # Timeline's Start and End points (p1, p2) in frames, it's raw values and raw controls (c1, c2)
        self.frame_p1 = None
        self.frame_p2 = None
        self.value_p1 = None
        self.value_p2 = None
        self.ctrlX_c1 = None
        self.ctrlY_c1 = None
        self.ctrlX_c2 = None
        self.ctrlY_c2 = None

        # Backup data for Undo/Redo
        self.original_data = None

        # Property of type "color" (red, green or blue curve)
        self.colorRGB = None

        # Scroll widgets
        self.hScroller = None
        self.timeScroll = None
        self.timeScrollItem = None
        self.vScroller = None
        self.valueScroll = None
        self.valueScrollItem = None

        # Number of time cells to scroll behind the both ends of the clip
        self.overageTimeCells = 2

        # Number of time cells to scroll behind the min/max value of the clip
        self.overageValueCells = 2

        # Allow current grid time offset and value scroll to be applied
        self.autoScrollTime = True
        self.autoScrollValue = True

        # Invisible object larger than grid for a few pixels, for centering only
        self.gridBoundsItem = None

        self.addBoundsGridItem()
        self.addGridScrolls()
        self.updateValScrollerMinMax()

        # Use main UI signals
        get_app().window.previewFrameSignal.connect(self.setCurFrame)
        get_app().window.ItemSelected.connect(self.processAllAnimationPoints)
        get_app().window.refreshFrameSignal.connect(self.refreshDrawing)
        self.crvEdt.sldrZoomTime.valueChanged.connect(self.setTimeAxisScale)
        self.crvEdt.sldrZoomVal.valueChanged.connect(self.setValueAxisScale)

    def addGridScrolls(self):
        # Horizontal scroller (time axis)
        self.hScroller = QWidget()

        # Scroller fits into the full width of the grid, height minimum is 4 pixels
        self.hScroller.setGeometry(0, 0, (self.cell_width * self.cells_x_num) + 1, 4)
        self.timeScroll = QScrollBar(Qt.Horizontal)
        self.timeScroll.setMinimum(0)
        self.timeScroll.setMaximum(0) # Seconds
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 5, 0, 0) # default is 11 px from the style
        layout.addWidget(self.timeScroll)
        self.hScroller.setLayout(layout)
        self.timeScrollItem = self.addWidget(self.hScroller)

        # Vertical scroller (value axis)
        # To UP is subtracting the value and TOP is a minimum (most styles drawn this way)
        self.vScroller = QWidget()
        self.vScroller.setGeometry(0, 0, 4, (self.cell_height * self.cells_y_num) + 1)
        self.valueScroll = QScrollBar(Qt.Vertical)

        self.valueScroll.setMinimum(0)
        self.valueScroll.setMaximum(0) # Cells
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 0, 0, 0) # default is 11 px from the style
        layout.addWidget(self.valueScroll)
        self.vScroller.setLayout(layout)
        self.valueScrollItem = self.addWidget(self.vScroller)

        self.updateScrollersGeometry()

        # Use signals to update draw on handle move
        self.timeScroll.valueChanged.connect(self.refreshDrawing)
        self.valueScroll.valueChanged.connect(self.valueRefresh)

    def updateScrollersGeometry(self):
        # Adjust scrollers size
        self.hScroller.setGeometry(0, 0, (self.cell_width * self.cells_x_num) + 1, 5)
        self.vScroller.setGeometry(0, 0, 5, (self.cell_height * self.cells_y_num) + 1)

        # Place it 1 pixel behind the grid
        self.timeScrollItem.setPos(0, (self.cell_height * self.cells_y_num) + 1)
        self.valueScrollItem.setPos((self.cell_width * self.cells_x_num) + 1, 0)

    def updateValScrollerMinMax(self):
        # Number of cells needed to draw scaled curve
        halfCellsNumber = int(0.5 * self.cells_y_num / self.valueAxisScaleF)

        # Update Value axis scroll min/max, in cells number
        self.valueScroll.setMinimum(-halfCellsNumber - self.overageValueCells)
        self.valueScroll.setMaximum(halfCellsNumber + self.overageValueCells)

    def applyScrollToGrid(self):
        # Updating current min/max for the grid's Value axis.
        #
        # Number of cells needed to shift the current min/max to perform the "scroll"
        valShift = -self.valueScroll.sliderPosition()

        # Override current min/max values
        unit = (self.lastZoomedMaxValF - self.lastZoomedMinValF) / self.cells_y_num
        self.maxValF = self.lastZoomedMaxValF + valShift * unit
        self.minValF = self.maxValF - self.cells_y_num * unit
        self.minMaxChanged = True

    def valueRefresh(self):
        # Perform scroll and then refresh
        self.applyScrollToGrid()
        if not self.refreshDrawing():
            # Redraw the axis painting (new scale)
            self.update()

    def setValueAxisScale(self, zoom):
        # Setting new zoom factor, zoom is integer in range 1..99, 10 is x1.0 zoom factor
        self.valueAxisScaleF = 10 / zoom

        # New min/max of the Value axis, centered
        self.maxValF = 0.5 * (self.lastMaxValF - self.lastMinValF) * (1 + self.valueAxisScaleF) + self.lastMinValF
        self.minValF = 0.5 * (self.lastMaxValF - self.lastMinValF) * (1 - self.valueAxisScaleF) + self.lastMinValF
        self.minMaxChanged = True
        self.lastZoomedMaxValF = self.maxValF
        self.lastZoomedMinValF = self.minValF

        # Skip excessive refresh because setting new min/max for the scroller may update slider position
        ref = self.skipRefresh
        self.skipRefresh = True
        self.updateValScrollerMinMax()
        self.skipRefresh = ref

        self.crvEdt.label_zoomVal.setText("x{:3.1f}".format(zoom / 10))
        if not self.refreshDrawing():
            # Redraw the axis painting (new scale)
            self.update()

    def setupGrid(self):
        """ Builds array of the grid lines to draw them in one move later """
        # Start from the new grid
        self.grid.clear()

        # Vertical lines
        for num in range(0, self.cells_x_num + 1):
            x = num * self.cell_width
            self.grid.append(QLineF(x, self.exposed.top(), x, self.exposed.bottom()))

        # Horizontal lines
        for num in range(0, self.cells_y_num + 1):
            y = num * self.cell_height
            self.grid.append(QLineF(self.exposed.left(), y, self.exposed.right(), y))

    def drawBackground(self, painter, exposed):
        # Paint custom grid (is drawn first from all)
        painter.setBrush(self.GraphBrushEmpty)
        painter.setPen(self.GraphPenDis)
        self.setupGrid()
        painter.drawLines(self.grid)

        self.halfFrameOffsetF = self.halfFrameRatioF * self.getFramePixelPosF(1)

        # Draw frame ticks on timeline axis as rectangles of frame duration
        painter.setBrush(self.GraphBrushDis)
        painter.setPen(self.GraphPenEmpty)
        ticks_height = 3
        ticks_widthF = self.getFramePixelPosF(1)
        # Do not draw too thin ticks
        if ticks_widthF >= 2.0:
            # Draw each second only, first rectangle aligned to the left side of the cell
            ticks_count2 = int(self.cells_x_num * self.cell_width / (2 * ticks_widthF))
            for num in range (0, ticks_count2):
                # Draw each second only
                x = round(2 * ticks_widthF * num)
                painter.drawRect(x, -ticks_height, round(ticks_widthF), ticks_height)

        # Draw grid indexes as text with background
        painter.setBackgroundMode(Qt.OpaqueMode)
        painter.setBrush(self.GraphBrushEmpty)
        painter.setPen(self.GraphPenDis)
        timePos_bottom = -5
        valuePos_left = -70
        for num in range(0, self.cells_x_num + 1):
            x = num * self.cell_width
            painter.drawText(x, timePos_bottom, self.getTimeStr(num))
        for num in range(0, self.cells_y_num + 1):
            y = num * self.cell_height
            painter.drawText(valuePos_left, y, self.getValueStr(num))

        # Debug
        # painter.drawText(4, 14, "Frame: " + str(self.cur_frame))

        # Draw timeline cursor
        painter.setPen(self.GraphPenRedThin)
        x = round(self.cell_width * (self.frameToSecF(self.cur_frame) - self.gridOffsetTime) / zoomToSeconds(self.timeAxisScale) - self.halfFrameOffsetF)
        # Do not draw cursor outside the grid
        if x >= 0 and x <= (self.cell_width * self.cells_x_num):
            painter.drawLine(QLineF(x, self.exposed.top(), x, self.exposed.bottom()))

    def addBoundsGridItem(self):
        """ Invisible item. It only centers the grid on the screen when any item added
            withing the grid coordinates.
            Do not call it from drawForeground() etc. paint methods to avoid recursion
        """
        self.gridBoundsItem = GridBounds(self.exposed.adjusted(-self.gridMarginL, -self.gridMarginT, +self.gridMarginR, +self.gridMarginB))
        # If required, please, use the self.GraphPenHigh pen for UI debug here
        self.gridBoundsItem.setPen(self.GraphPenEmpty)
        self.addItem(self.gridBoundsItem)

    def setCurFrame(self, frame_number):
        # Main window signal carries the current frame_number
        self.cur_frame = frame_number

    def getCurFrameSafe(self):
        # The preview_thread may not running yet
        try:
            self.cur_frame = get_app().window.preview_thread.player.Position()
        except Exception:
               pass

    def setTimeAxisScale(self, scale):
        # Slider's internal signal carries the current value() within
        self.timeAxisScale = scale

        # Get translation function
        _ = get_app()._tr

        self.crvEdt.label_zoomTime.setText( _("{} seconds").format(zoomToSeconds(scale)) )
        if not self.refreshDrawing():
            # Redraw the axis painting (new scale)
            self.update()

    def frameToSecF(self, frame_number):
        # Returns duration in seconds for given number of full frames
        #
        # 30 frames for 30fps means that 1 sec was passed
        # 29 frames means that 0.9666(6) sec was passed

        # Get FPS from the project
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        return (frame_number) / fps_float

    def secToFrame(self, secondsF):
        # Returns frame number close to the right
        #
        # 1 sec for 30fps means that 31-th frame was started now
        # 0.99 sec means that 30-th frame was started now

        # Get FPS from the project
        fps = get_app().project.get("fps")
        fps_float = float(fps["num"]) / float(fps["den"])
        # Workaround possible inaccuracy by using rounding, thus int(1.6666666665 * 30.0) should result in 50
        return int(round(secondsF * fps_float, 6)) + 1

    def getCellHeightUnitsF(self, maxF=1.0, minF=0.0):
        """ Returns height of one grid cell in units, taking into account min/max in units """
        if not self.minMaxChanged:
            return self.cellHeightUnitsCachedF

        # Do not allow zero height
        if (maxF - minF) == 0:
            self.cellHeightUnitsCachedF = 0.000001
            return self.cellHeightUnitsCachedF

        # Values axis, cell height in units
        self.cellHeightUnitsCachedF = (maxF - minF) / self.cells_y_num

        # Calculate it only once
        self.minMaxChanged = False
        return self.cellHeightUnitsCachedF

    def getCellWidthFramesF(self):
        # Returns width of one grid cell in frames
        return zoomToSeconds(self.timeAxisScale) / self.frameToSecF(1)

    def getValuePixelPosF(self, valueF, valueOffsetF=0.0):
        """ Returns number of pixels by Value axis that corresponds to the given float value, taking into account the scale
            In other words it returns units length in pixels by Y axis.
        """
        # Number of cells that fits into the Value
        cellsPerValueF = valueF / self.getCellHeightUnitsF(self.maxValF, self.minValF)
        cellsPerOffsetF = valueOffsetF / self.getCellHeightUnitsF(self.maxValF, self.minValF)
        return (cellsPerValueF + cellsPerOffsetF) * self.cell_height

    def getFramePixelPosF(self, frame_number, frameOffset=0):
        """ Returns number of pixels by Time axis that corresponds to the given frame, taking into account the scale
            In other words it returns frames length in pixels by X axis.
        """
        # Seconds from the given point (frame)
        gpF = self.frameToSecF(frame_number) + self.frameToSecF(frameOffset)
        return gpF * self.cell_width / zoomToSeconds(self.timeAxisScale)

    def updateGridTimeShift(self, sec=None):
        """ Updates the time axis offset only for integer number of cells """
        # Number of whole cells
        num = int(self.minTimeF / zoomToSeconds(self.timeAxisScale))
        # Shift the time for integer number of cells
        if sec is None:
            self.gridOffsetTime = num * zoomToSeconds(self.timeAxisScale)
        else:
            self.gridOffsetTime = sec
        # Update the last frame that fits into the current grid
        self.gridEndFrame = self.getCellWidthFramesF() * self.cells_x_num + self.secToFrame(self.gridOffsetTime) - 1

    def getTimeStr(self, num):
        """ Returns time as string per cell number, left to right (num = 0, 1, 2,... self.cells_x_num)
            Formated "hh:mm:ss" with leading zeros, taking into account the scale and minimum value
            Considering that the minimum displayable value is 00:00:00
        """
        return "{:0>8}".format(str(timedelta(seconds = num * zoomToSeconds(self.timeAxisScale) + self.gridOffsetTime)))

    def getValueStr(self, num):
        """ Returns value as string per each cell number
            Top to bottom (num = 0, 1, 2,... self.cells_y_num)
            Fixed point format
        """
        # (1)First  cell = max - 0 * cell_height_units
        # (2)Second cell = max - 1 * cell_height_units
        # (3)Third  cell = max - 2 * cell_height_units
        # (N)-th    cell = max - (N - 1) * cell_height_units
        return "{:16.4f}".format(self.maxValF - num * self.getCellHeightUnitsF(self.maxValF, self.minValF))

    def addGraphCurveItem(self, path, c1_xF, c1_yF, c2_xF, c2_yF, xF, yF):
        """ Draw curve by adding the path item to the scene
            Uses raw keyframe Points values as input for the xF(X), yF(Y)
        """

        # Each keyframe point in libopenshot is abstract model and may hold:
        # 1) max (or min) value of the animated parameter ("Y")
        # 2) place where the max from p.1 should apply ("X")
        # 3) control point c2 of the Bezier curve, for the segment that lies left to the "X" from p.2 ("handle_left")
        # 4) control point c1 of the Bezier curve, for the segment that lies right to the "X" from p.2 ("handle_right")
        # 5) interpolation type enumerator (Bezier, Linear, Constant)
        # both p.3 and p.4 may point to the curve that doesn't exist (for example, last/first segment or interpolation change to linear or constant)
        # both p.3 and p.4 is in percent calculated from previous keyframe point
        # both p.3 and p.4 always lies within the previous-current keyframe point rectangle (time limited rectangle)
        # both p.3 and p.4 may not exist even for interpolation type Bezier specified by p.5

        # Save original Timeline's frame of the end point (p2), its value, and both controls (c1, c2)
        # Compensates 1 frame offset caused by fact that xF time includes length of the specified frame (frames always starts from 1.0)
        self.frame_p2 = self.secToFrame(self.frameToSecF(xF - 1) + self.elementOffsetTimeF + self.gridOffsetTime)
        self.value_p2 = yF
        self.ctrlX_c1 = c1_xF
        self.ctrlY_c1 = c1_yF
        self.ctrlX_c2 = c2_xF
        self.ctrlY_c2 = c2_yF

        self.halfFrameOffsetF = self.halfFrameRatioF * self.getFramePixelPosF(1)
        # Destination point of the curve, right-handed coordinate system, z toward viewer
        xF = round(self.getFramePixelPosF(self.secToFrame(self.frameToSecF(xF - 1) + self.elementOffsetTimeF)) - self.halfFrameOffsetF)
        yF = round(self.getValuePixelPosF(0.0, self.maxValF) - self.getValuePixelPosF(yF))

        X_diff = xF - self.DrawPointX
        Y_diff = yF - self.DrawPointY

        # Control point c1
        c1_xF = self.DrawPointX + (c1_xF * X_diff)
        c1_yF = self.DrawPointY + (c1_yF * Y_diff)

        # Control point c2
        c2_xF = self.DrawPointX + (c2_xF * X_diff)
        c2_yF = self.DrawPointY + (c2_yF * Y_diff)

        path.cubicTo(c1_xF, c1_yF, c2_xF, c2_yF, xF, yF)

        # Skip segments that fully lies outside the grid and cut loose ends
        clippingRect=self.exposed
        if path.intersects(clippingRect):
            if self.exposed.contains(xF, yF):
                # The path may begin before the current DrawPoint, thus use actual start point
                startPoint = QPointF(path.elementAt(0))
                if self.exposed.contains(startPoint):
                    # Whole curve fits into the exposed rectangle - don't cut it
                    clippingRect = None
            graphItem = CurveElement(path, self.segment_type, clippingRect, self.frame_p1, self.frame_p2, self.value_p1, self.value_p2, self.ctrlX_c1, self.ctrlY_c1, self.ctrlX_c2, self.ctrlY_c2)
            graphItem.setPen(self.curvePen)
            graphItem.setBrush(self.curveBrush)
            self.addItem(graphItem)

        # Update draw start point
        self.DrawPointX = xF
        self.DrawPointY = yF

    def addGraphTail(self, path, clip_endF, valueF):
        """ Places new curve element to the scene that lasts till the end of the grid,
            but no longer than the clip itself
            Uses raw keyframe Points values for the clip_endF(X), valueF(Y)
        """
        # Maximum grid time
        max_seconds = self.cells_x_num * zoomToSeconds(self.timeAxisScale) + self.gridOffsetTime
        if clip_endF > max_seconds:
            clip_endF = max_seconds
        xF = self.secToFrame(clip_endF)
        yF = valueF

        # The Seg.CONST_SHELF segment can't be edited
        self.segment_type = Seg.CONST_SHELF
        self.addGraphCurveItem(path, 1.0, 1.0, 1.0, 1.0, xF, yF)

    def moveDrawPointTo(self, path, frameF, valueF):
        """ Moves draw start point to the specified coordinates,
            Uses raw keyframe Points values for the frameF(X), valueF(Y)
        """
        # Graph coordinate system begins at (frame=1; valueF=0.0) coordinates
        # maxValF lies at Y=0 pixel, top left corner, thus length to 0 value is getValuePixelPosF(maxValF) pixels

        # Save original Timeline's frame of the start point (p1) and its value
        # Compensates 1 frame offset caused by fact that frame time includes length of the specified frame (frames always starts from 1.0)
        self.frame_p1 = self.secToFrame(self.frameToSecF(frameF - 1) + self.elementOffsetTimeF + self.gridOffsetTime)
        self.value_p1 = valueF

        self.halfFrameOffsetF = self.halfFrameRatioF * self.getFramePixelPosF(1)
        # Move draw start point according to the (1; 0.0) point, right-handed coordinate system, z toward viewer
        self.DrawPointX = round(self.getFramePixelPosF(self.secToFrame(self.frameToSecF(frameF - 1) + self.elementOffsetTimeF)) - self.halfFrameOffsetF)
        self.DrawPointY = round(self.getValuePixelPosF(0.0, self.maxValF) - self.getValuePixelPosF(valueF))
        path.moveTo(self.DrawPointX, self.DrawPointY)

    def addGraphClipBoundsItem(self, startF, endF):
        """ Places clip bounds drawing into the scene, the startF and endF in seconds """
        # Start position and width of the clip in pixels
        # It takes into account startTime shift of the element offset
        startX = round(self.getFramePixelPosF(self.secToFrame(self.elementOffsetTimeF + startF)) - self.halfFrameOffsetF)
        width = round(self.getFramePixelPosF(self.secToFrame(endF - startF)))

        # Vertically centered output
        y = round((self.exposed.height() - self.cell_height) / 2)
        height = self.cell_height
        bodyRect = QRectF(startX, y, width, height)

        # If clip bounds doesn't feet into the exoposed rectangle by the width then cut it
        if self.exposed.contains(bodyRect):
            clippingRect = None
        else:
            clippingRect=self.exposed
        path = RoundedRect(bodyRect)
        graphItem = ClipBounds(path, clippingRect)
        graphItem.setPen(self.clipBoundsPen)
        graphItem.setBrush(self.clipBoundsBrush)
        self.addItem(graphItem)

    def getClipByID(self, clip_id, item_type):
        # TODO: move it to the properties_model.py (there it used a lot)
        c = None

        # Get object of corresponding type
        if item_type == "clip":
            c = Clip.get(id=clip_id)
        elif item_type == "transition":
            c = Transition.get(id=clip_id)
        elif item_type == "effect":
            c = Effect.get(id=clip_id)

        return c

    def processAllAnimationPoints(self, item):
        """ Reads clips data to get keyframes values
            and calls for the curve element add if any found
        """

        self.lastClipItem = item

        # Remove all items from the scene before adding any new
        self.clearTheScene()

        if item is None:
            # Prepare to scroll to the clip's start and centered values
            self.autoScrollTime = True
            self.autoScrollValue = True

            # Nothing is selected
            self.crvEdt.setInfoLabels("-", "-")
            return

        # Here item.data() is list of clip_id and item_type
        clip_id, item_type = item.data()

        # Get data model and selection
        model = get_app().window.propertyTableView.clip_properties_model.model
        row = item.row()

        property = model.item(row, 0).data()
        property_type = property[1]["type"] # float, int, bool, color, string, reader
        property_name = property[1]["name"] # localized value
        property_key = property[0]

        c = self.getClipByID(clip_id, item_type)

        if c is None:
            return

        # Get data for Undo/Redo
        if not get_app().updates.ignore_history and (property_key in c.data):
            self.original_data = c.data

        startTime = 0.0
        endTime = 0.0
        # Find parent clip to get the effect's correct starting position
        if item_type == "effect":
            effect = Effect.get(id=clip_id)
            if not effect:
                return
            self.minTimeF = effect.parent["position"]
            startTime = effect.parent["start"]
            endTime = effect.parent["end"]
        else:
            self.minTimeF = c.data["position"]
            startTime = c.data["start"]
            endTime = c.data["end"]

        # Grid offset time from the scroller position, in seconds
        # Maximum possible time axis shift behind the clip's start/end, in seconds (+/- 2 cells)
        # Full grid length at current scale, in seconds
        timeScrollPos = self.timeScroll.sliderPosition()
        timeMaxOffset = self.overageTimeCells * zoomToSeconds(self.timeAxisScale)
        gridLengthSec = self.cells_x_num * zoomToSeconds(self.timeAxisScale)

        if self.autoScrollTime:
            # Update scroll min/max value and handle position
            self.updateGridTimeShift()
            self.timeScroll.setMaximum(self.minTimeF + (endTime - startTime) + timeMaxOffset)
            self.timeScroll.setMinimum(max(self.minTimeF - gridLengthSec - timeMaxOffset, 0))
            self.timeScroll.setSliderPosition(self.gridOffsetTime)
            self.autoScrollTime = False # Auto-scroll only once
        else:
            # Update scroll min/max value
            self.updateGridTimeShift(timeScrollPos)
            self.timeScroll.setMaximum(self.minTimeF + (endTime - startTime) + timeMaxOffset)
            self.timeScroll.setMinimum(max(self.minTimeF - gridLengthSec - timeMaxOffset, 0))

        # Start position of the curve has new offset now, recalculate
        self.elementOffsetTimeF = self.minTimeF - self.gridOffsetTime - startTime

        # Add clip current bounds into background
        self.addGraphClipBoundsItem(startTime, endTime)

        startClipFrame = self.secToFrame(startTime)
        endClipFrame = self.secToFrame(endTime)

        # Assuming that whole curve fits into the grid
        draw_tail = True

        # Get clip attribute
        if property_key in c.data:
            # Determine type of keyframe (standard or color)
            keyframe_list = []
            if property_type == "color":
                keyframe_list = [c.data[property_key]["red"], c.data[property_key]["green"], c.data[property_key]["blue"]]
                color_key = ["red", "green", "blue"]
                color_pen = [self.GraphPenRed, self.GraphPenGreen, self.GraphPenBlue]
                color_penH = [self.GraphPenHelperR, self.GraphPenHelperG, self.GraphPenHelperB]
            else:
                keyframe_list = [c.data[property_key]]
                color_key = None

            # Loop through each keyframe if any (red, blue, and green)
            for i, keyframe in enumerate(keyframe_list):
                # Not all properties has Points member (not animated yet),
                # exclude file readers too - for example Source property of the Mask effect
                if type(c.data[property_key]) != dict or property_type == "reader":
                    # The Effect object has no "title" property
                    if item_type == "effect":
                        obj_title = "name"
                    else:
                        obj_title = "title"

                    # Get translation function
                    _ = get_app()._tr

                    # Update info labels and abort graph building
                    self.crvEdt.setInfoLabels("{} ({})".format(c.data[obj_title], item_type), "{} ({})".format(property_name, _("No animation")))
                    return

                # Number of animated points (keys of animation)
                self.newCurvPointsNum = len(keyframe["Points"])

                # If Points list is empty - it means 0.0f value of the selected property
                # should apply while the whole object exist on the Timeline.
                # (For example, the "brightness" property of the Alpha Mask / Wipe Transition)
                # Any other value is set with at least one point at the first frame.
                if self.newCurvPointsNum < 1:
                    # Set start points in case the Points is empty list
                    prevPointX = 0.0
                    prevPointY = 0.0
                    if not self.refreshingDrawing:
                        self.maxValF = 0.6
                        self.minValF = -0.4
                        self.minMaxChanged = True
                        self.lastMaxValF = self.maxValF
                        self.lastMinValF = self.minValF
                else:
                    # Force sort of all keyframe points by frame number in ascending order
                    # OpenShot can create (and save) not ordered list of dictionaries
                    # but animation curve will be drawn continuously from left to right
                    keyframe["Points"].sort(key=lambda a: a["co"]["X"], reverse=False)

                    if not self.refreshingDrawing:
                        if color_key is None:
                            # Size of the Value axis
                            self.maxValF = float_info.min + 1
                            self.minValF = float_info.max - 1
                            for point in keyframe["Points"]:
                                cur = point["co"]["Y"]
                                if cur > self.maxValF:
                                    self.maxValF = cur
                                if cur < self.minValF:
                                    self.minValF = cur
                            if self.maxValF == self.minValF:
                                self.maxValF = self.minValF + 1
                            self.minMaxChanged = True
                            self.lastMaxValF = self.maxValF
                            self.lastMinValF = self.minValF
                        else:
                            # Override Value axis min/max to draw all three sub-colors in the same fixed scale
                            self.maxValF = 255.0
                            self.minValF = 0.0
                            self.minMaxChanged = True
                            self.lastMaxValF = self.maxValF
                            self.lastMinValF = self.minValF
                log.info("Value min/max: {} / {}".format(self.minValF, self.maxValF))

                if self.autoScrollValue:
                    # Update initial zoom and set scroll to center
                    self.skipRefresh = True
                    self.setValueAxisScale(self.crvEdt.sldrZoomVal.sliderPosition())
                    self.valueScroll.setSliderPosition(0)
                    self.skipRefresh = False
                    self.autoScrollValue = False # Auto-scroll only once
                else:
                    # Update Value axis zoom
                    self.skipRefresh = True
                    self.setValueAxisScale(self.crvEdt.sldrZoomVal.sliderPosition())
                    self.skipRefresh = False

                # Apply Value axis scrollers
                self.applyScrollToGrid()

                # Find leading curve segments that fully lies beyond the clip boundaries
                first_j = 0
                last_j = self.newCurvPointsNum - 1
                if not self.crvEdt.chk_show_full.isChecked():
                    draw_tail = False
                    for j, point in enumerate(keyframe["Points"]):
                        if point["co"]["X"] <= startClipFrame:
                            first_j = j
                        elif point["co"]["X"] >= endClipFrame:
                            last_j = j
                            break

                for j, point in enumerate(keyframe["Points"]):
                    # Skip the curve segments that fully lies beyond the clip boundaries
                    if j < first_j:
                        continue
                    if j > last_j:
                        break

                    path = QPainterPath()
                    # Start drawing curve from the frame 1, value 0.0 or any available
                    if j == first_j:
                        prevPointX = point["co"]["X"]
                        prevPointY = point["co"]["Y"]
                        prevHandle1X = 1.0
                        prevHandle1Y = 1.0

                    # Reset current segment pen and set color triad type
                    if color_key is None:
                        self.curvePen = self.GraphPen
                        self.colorRGB = None
                    else:
                        self.curvePen = color_pen[i]
                        self.colorRGB = color_key[i]

                    self.moveDrawPointTo(path, prevPointX, prevPointY)

                    # Get full bezier curve from available data
                    xF = point["co"]["X"]
                    yF = point["co"]["Y"]

                    c1_xF = prevHandle1X
                    c1_yF = prevHandle1Y
                    # Some control points may not exist!
                    try:
                        c2_xF = point["handle_left"]["X"]
                        c2_yF = point["handle_left"]["Y"]
                    except Exception:
                        # Assuming that handle point not exist
                        c2_xF = 1.0
                        c2_yF = 1.0
                    try:
                        prevHandle1X = point["handle_right"]["X"]
                        prevHandle1Y = point["handle_right"]["Y"]
                    except Exception:
                        # Assuming that handle point not exist
                        prevHandle1X = 1.0
                        prevHandle1Y = 1.0

                    if point["interpolation"] == 0:
                        # Bezier
                        self.segment_type = Seg.BEZIER
                    elif point["interpolation"] == 1:
                        # Linear
                        self.segment_type = Seg.LINEAR
                    elif point["interpolation"] == 2:
                        # Constant
                        self.segment_type = Seg.CONST_SHELF
                        if color_key is None:
                            # Reset current segment pen
                            self.curvePen = self.GraphPen

                            # Add intermediate line that lasts until the previous frame
                            self.addGraphCurveItem(path, c1_xF, c1_yF, c2_xF, c2_yF, xF - 1.0, prevPointY)

                            # Set current segment pen
                            self.curvePen = self.GraphPenHelper
                            self.segment_type = Seg.CONST_STEP
                        else:
                            # Reset current segment pen
                            self.curvePen = color_pen[i]

                            # Add intermediate line that lasts until the previous frame
                            self.addGraphCurveItem(path, c1_xF, c1_yF, c2_xF, c2_yF, xF - 1.0, prevPointY)

                            # Set current segment pen
                            self.curvePen = color_penH[i]
                            self.segment_type = Seg.CONST_STEP
                    else:
                        log.error("Unknown interpolation {}".format(point["interpolation"]))

                        # Substitute with the linear coefficients
                        self.segment_type = Seg.UNKNOWN_LINEAR
                        c1_xF = 1.0
                        c1_yF = 1.0
                        c2_xF = 1.0
                        c2_yF = 1.0

                        # Draw it blank
                        self.curvePen = self.GraphPenEmpty

                    self.addGraphCurveItem(path, c1_xF, c1_yF, c2_xF, c2_yF, xF, yF)

                    prevPointX = xF
                    prevPointY = yF

                    # Skip all points that lies behind the grid by the Time axis
                    if prevPointX > self.gridEndFrame:
                        draw_tail = False
                        break

                # Draw stait horizontal line till the end of the clip to show final value of the parameter if needed
                if draw_tail and (endTime > self.frameToSecF(prevPointX)):
                    # Make sure that tail (if any) will be drawn using right pen
                    if color_key is None:
                        self.curvePen = self.GraphPen
                    else:
                        self.curvePen = color_pen[i]
                    path = QPainterPath()
                    self.moveDrawPointTo(path, prevPointX, prevPointY)
                    self.addGraphTail(path, endTime, prevPointY)

            # The Effect object has no "title" property
            if item_type == "effect":
                obj_title = "name"
            else:
                obj_title = "title"
            self.crvEdt.setInfoLabels("{} ({})".format(c.data[obj_title], item_type), property_name)

            # Redraw the axis painting (new scale)
            self.update()

        else:
            # Update info labels to "No data available"
            #
            # The Effect object has no "title" property
            if item_type == "effect":
                obj_title = "name"
            else:
                obj_title = "title"

            # Get translation function
            _ = get_app()._tr

            self.crvEdt.setInfoLabels("{} ({})".format(c.data[obj_title], item_type), "{} ({})".format(property_name, _("No data available")))

    def clearTheScene(self):
        # Remove all non-helper curves from the scene
        for curve in self.items():
            if not curve.isWidget() and not curve.helper_obj:
                self.removeItem(curve)

    def refreshDrawing(self):
        # Skip refresh drawing if needed
        if self.skipRefresh:
            return False

        # Redraw all curves
        if self.lastClipItem is not None:
            # Read current item data again
            row = get_app().window.propertyTableView.currentIndex().row()
            model = get_app().window.propertyTableView.clip_properties_model.model
            selected_item = model.item(row, 1)

            # Update graphic's scene
            self.refreshingDrawing = True
            self.processAllAnimationPoints(selected_item)
            self.refreshingDrawing = False
            return True

        return False

class GridBounds(QGraphicsRectItem):
    # Initial properties
    helper_obj = True
    seg_type = Seg.BOUNDS_RECTANGLE

    def __init__(self, rect):
        QGraphicsRectItem.__init__(self, rect)

class CurveElement(QGraphicsPathItem):
    # Initial properties
    helper_obj = False
    seg_type = Seg.UNKNOWN_LINEAR

    def __init__(self, path, segment_type=Seg.BEZIER, clippingRect=None, p1_orig=None, p2_orig=None, p1_value=None, p2_value=None, c1_x=None, c1_y=None, c2_x=None, c2_y=None):
        self.frame_p1 = p1_orig
        self.frame_p2 = p2_orig
        self.value_p1 = p1_value
        self.value_p2 = p2_value
        self.origX_c1 = c1_x
        self.origY_c1 = c1_y
        self.origX_c2 = c2_x
        self.origY_c2 = c2_y

        # Get dock widget to update UI later
        self.crvEdt = get_app().window.findChild(QDockWidget, 'dockCurveEditor', Qt.FindDirectChildrenOnly)

        # Single frame length in pixels
        frameLength = int(self.crvEdt.scene.getFramePixelPosF(1))

        # Get all bezier control/main points from the first curve
        if (segment_type == Seg.BEZIER or segment_type == Seg.LINEAR) and path.elementCount() > 3:
            self.startPoint = QPointF(path.elementAt(0))
            self.c1 = QPointF(path.elementAt(1)) # Not used for Linear
            self.c2 = QPointF(path.elementAt(2)) # Not used for Linear
            self.endPoint = QPointF(path.elementAt(3))

            # Make new actual path that has straight bezier lines for Linear interpolation
            if segment_type == Seg.LINEAR:
                straightPath = QPainterPath()
                straightPath.moveTo(self.startPoint)
                straightPath.cubicTo(self.startPoint, self.endPoint, self.endPoint)

                # Redefine the path as staight
                path.swap(straightPath)
        elif segment_type == Seg.CONST_STEP and path.elementCount() > 6:
            # Constant interpolation curve segment consist of two CurveElement objects:
            # Seg.CONST_SHELF of p1-p2 and
            # Seg.CONST_STEP of p1-p2-p3 that lies above the Seg.CONST_SHELF
            #
            # Get bezier main points from the first-last curve segment
            self.startPoint = QPointF(path.elementAt(0))
            self.endPoint = QPointF(path.elementAt(6))

            # Make new actual path that has straight bezier lines for Constant interpolation
            straightPath = QPainterPath()
            straightPath.moveTo(self.startPoint)

            # Point previous to end frame but at start point value
            pp2 = QPointF(self.endPoint.x() - frameLength, self.startPoint.y())
            straightPath.cubicTo(self.startPoint, pp2, pp2)
            straightPath.cubicTo(pp2, self.endPoint, self.endPoint)

            # Redefine the path as staight
            path.swap(straightPath)
        if clippingRect is not None:
            # Add clipping rectangle and make intersection
            clipArea = QPainterPath()

            # Enlarge clipping rectangle a bit to ensure that the intersected square is always > 0
            clipArea.addRect(clippingRect.adjusted(-1, -1, +1, +1))

            # Make sure that the path is not straight line but some shape, to make accurate intersection
            path.lineTo(clippingRect.width(), clippingRect.height() + 1000)
            path.lineTo(clippingRect.width() - 1000, clippingRect.height() + 1000)
            path = path.intersected(clipArea)

            # Debug
            # log.info("curve segments count: {}".format(path.elementCount()))
            # for i in range(0, path.elementCount()):
            #    point = path.elementAt(i)
            #    log.info("clipped point ({}; {})".format(QPointF(point).x(), QPointF(point).y()))

            clipped_path = QPainterPath()

            # Get all bezier control/main points of the first curve segment inside clipping area
            if segment_type == Seg.CONST_STEP and path.elementCount() > 6:
                # Get bezier main points of the clipped first-last curve segment ("knee")
                self.startPoint = QPointF(path.elementAt(0))
                pp2 = QPointF(path.elementAt(3))
                self.endPoint = QPointF(path.elementAt(6))
                if not self.startPoint.y() == pp2.y():
                    # "Shelf" part lies out of the grid and was clipped
                    self.endPoint = pp2
                    pp2 = self.startPoint

                clipped_path.moveTo(self.startPoint)
                clipped_path.cubicTo(self.startPoint, pp2, pp2) # Here pp2 = cc2, straight line
                clipped_path.cubicTo(pp2, self.endPoint, self.endPoint)
            elif path.elementCount() > 3:
                self.startPoint = QPointF(path.elementAt(0))
                self.c1 = QPointF(path.elementAt(1))
                self.c2 = QPointF(path.elementAt(2))
                self.endPoint = QPointF(path.elementAt(3))

                clipped_path.moveTo(self.startPoint)
                clipped_path.cubicTo(self.c1, self.c2, self.endPoint)

            # Redefine path as not closed path
            path.swap(clipped_path)

        self.seg_type = segment_type

        QGraphicsPathItem.__init__(self, path)
        self.curvePen = self.crvEdt.scene.curvePen

        # Set property of type "color" (red, green or blue curve)
        self.colorRGB = self.crvEdt.scene.colorRGB

class ClipBounds(QGraphicsPathItem):
    # Initial properties
    helper_obj = False
    seg_type = Seg.ROUNDED_RECT

    def __init__(self, path, clippingRect=None):
        if clippingRect is not None:
            clipArea = QPainterPath()
            clipArea.addRect(clippingRect)
            path = path.intersected(clipArea)
        QGraphicsPathItem.__init__(self, path)

class RoundedRect(QPainterPath):
    """ Builds rounded rectangle path """
    def __init__(self, bodyRect, r=6):
        clipFullBounds = QPainterPath()
        clipFullBounds.addRoundedRect(bodyRect, r, r, Qt.AbsoluteSize)
        QPainterPath.__init__(self, clipFullBounds)
