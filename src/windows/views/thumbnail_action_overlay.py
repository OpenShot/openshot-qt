"""
@file
@brief Reusable thumbnail action overlay delegate and interaction mixin for item list views.
"""

from qt_api import (
    QPoint, QPointF, QRect, QRectF, Qt,
    QColor, QPen, QBrush, QPainter,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle,
    QPersistentModelIndex, QModelIndex,
)
from classes.logger import log


def to_qmodelindex(index):
    """Safely convert QPersistentModelIndex or QModelIndex to QModelIndex."""
    if isinstance(index, QPersistentModelIndex):
        return QModelIndex(index)
    return index


def get_thumbnail_decoration_rect(option, widget=None):
    """Return the decoration (thumbnail) rect for a given style option."""
    if widget and hasattr(widget, "style"):
        style = widget.style()
        if style:
            deco_rect = style.subElementRect(QStyle.SE_ItemViewItemDecoration, option, widget)
            if deco_rect.isValid() and deco_rect.width() > 0 and deco_rect.height() > 0:
                return QRectF(deco_rect)

    r = option.rect
    target_w = 100.0
    target_h = 65.0
    if widget and hasattr(widget, "iconSize"):
        isz = widget.iconSize()
        if isz.isValid():
            target_w = float(isz.width())
            target_h = float(isz.height())

    icon_w = min(target_w, float(r.width()))
    icon_h = min(target_h, float(r.height()))
    icon_x = float(r.center().x()) - (icon_w / 2.0)
    icon_y = float(r.top())
    return QRectF(icon_x, icon_y, icon_w, icon_h)


def calculate_button_rect(deco_rect, button_size=28.0):
    """Return a centered square QRectF for the action button inside the decoration rect."""
    if not deco_rect or not deco_rect.isValid() or deco_rect.width() <= 0 or deco_rect.height() <= 0:
        return QRectF()
    cx = float(deco_rect.center().x())
    cy = float(deco_rect.center().y())
    return QRectF(cx - (button_size / 2.0), cy - (button_size / 2.0), button_size, button_size)


def paint_plus_overlay_button(painter, btn_rect, is_button_hovered=False, is_button_pressed=False):
    """Draw a modern, crisp circular '+' action button with hover and pressed states."""
    if not btn_rect or not btn_rect.isValid():
        return

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)

    if is_button_pressed:
        bg_color = QColor(24, 90, 160, 245)
        border_color = QColor(255, 255, 255, 180)
        border_width = 1.5
        plus_color = QColor(230, 230, 230, 255)
        plus_width = 2.0
    elif is_button_hovered:
        bg_color = QColor(42, 130, 218, 235)  # OpenShot vibrant blue
        border_color = QColor(255, 255, 255, 220)
        border_width = 1.5
        plus_color = QColor(255, 255, 255, 255)
        plus_width = 2.2
    else:
        bg_color = QColor(20, 26, 38, 190)  # Dark translucent
        border_color = QColor(255, 255, 255, 120)
        border_width = 1.2
        plus_color = QColor(255, 255, 255, 230)
        plus_width = 2.0

    painter.setPen(QPen(border_color, border_width))
    painter.setBrush(QBrush(bg_color))
    painter.drawEllipse(btn_rect)

    cx = float(btn_rect.center().x())
    cy = float(btn_rect.center().y())
    glyph_radius = max(4.0, min(btn_rect.width(), btn_rect.height()) * 0.22)

    plus_pen = QPen(plus_color, plus_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(plus_pen)
    painter.drawLine(QPointF(cx - glyph_radius, cy), QPointF(cx + glyph_radius, cy))
    painter.drawLine(QPointF(cx, cy - glyph_radius), QPointF(cx, cy + glyph_radius))

    painter.restore()


class ThumbnailActionDelegate(QStyledItemDelegate):
    """Item delegate that paints a '+' button overlay when an item is hovered."""

    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def get_item_button_rect(self, index):
        """Compute the button QRectF for an index using delegate styling."""
        if not index.isValid():
            return QRectF()
        model_idx = to_qmodelindex(index)
        opt = QStyleOptionViewItem()
        opt.rect = self.view.visualRect(model_idx)
        opt.widget = self.view
        self.initStyleOption(opt, model_idx)
        deco_rect = get_thumbnail_decoration_rect(opt, self.view)
        return calculate_button_rect(deco_rect)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        if not index.isValid():
            return

        hovered_idx = getattr(self.view, "_hovered_index", None)
        if not hovered_idx or not hovered_idx.isValid() or hovered_idx.row() != index.row():
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        deco_rect = get_thumbnail_decoration_rect(opt, opt.widget or self.view)
        if not deco_rect.isValid():
            return

        btn_rect = calculate_button_rect(deco_rect)
        is_btn_hovered = getattr(self.view, "_button_hovered", False)
        is_btn_pressed = getattr(self.view, "_button_pressed", False) and (
            getattr(self.view, "_pressed_index", None) == hovered_idx
        )

        paint_plus_overlay_button(
            painter,
            btn_rect,
            is_button_hovered=is_btn_hovered,
            is_button_pressed=is_btn_pressed,
        )


class ThumbnailActionViewMixin:
    """Mixin for QListView widgets to support hover '+' button overlay and click interaction."""

    def init_thumbnail_action_overlay(self):
        """Initialize overlay state and enable mouse tracking."""
        self._hovered_index = None
        self._button_hovered = False
        self._button_pressed = False
        self._pressed_index = None
        self.setMouseTracking(True)
        if self.viewport():
            self.viewport().setMouseTracking(True)
        self.setItemDelegate(ThumbnailActionDelegate(self))

    def _button_rect_for_index(self, index):
        """Compute the button QRectF for a given model index."""
        if not index.isValid():
            return QRectF()
        model_idx = to_qmodelindex(index)
        delegate = self.itemDelegate()
        if delegate and hasattr(delegate, "get_item_button_rect"):
            return delegate.get_item_button_rect(model_idx)
        opt = QStyleOptionViewItem()
        opt.rect = self.visualRect(model_idx)
        opt.widget = self
        deco_rect = get_thumbnail_decoration_rect(opt, self)
        return calculate_button_rect(deco_rect)

    def _trigger_repaint(self):
        """Request a repaint of the view/viewport."""
        if self.viewport():
            self.viewport().update()
        else:
            self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        index = self.indexAt(pos)

        if index.isValid():
            btn_rect = self._button_rect_for_index(index)
            btn_hovered = btn_rect.adjusted(-2, -2, 2, 2).contains(QPointF(pos.x(), pos.y()))

            if btn_hovered:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.unsetCursor()

            hover_changed = (
                not self._hovered_index
                or not self._hovered_index.isValid()
                or self._hovered_index.row() != index.row()
            )
            state_changed = hover_changed or (self._button_hovered != btn_hovered)

            if state_changed:
                self._hovered_index = QPersistentModelIndex(index) if isinstance(index, QModelIndex) else index
                self._button_hovered = btn_hovered
                self._trigger_repaint()
        else:
            if self._hovered_index and self._hovered_index.isValid():
                self._hovered_index = None
                self._button_hovered = False
                self.unsetCursor()
                self._trigger_repaint()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hovered_index and self._hovered_index.isValid():
            self._hovered_index = None
            self._button_hovered = False
            self._button_pressed = False
            self._pressed_index = None
            self.unsetCursor()
            self._trigger_repaint()
        else:
            self._button_hovered = False
            self._button_pressed = False
            self._pressed_index = None
            self.unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            index = self.indexAt(pos)
            if index.isValid():
                btn_rect = self._button_rect_for_index(index)
                if btn_rect.adjusted(-4, -4, 4, 4).contains(QPointF(pos.x(), pos.y())):
                    log.info("Thumbnail '+' button mouse pressed for row %s", index.row())
                    self._button_pressed = True
                    self._pressed_index = QPersistentModelIndex(index) if isinstance(index, QModelIndex) else index
                    self._trigger_repaint()
                    event.accept()
                    return

        self._button_pressed = False
        self._pressed_index = None
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._button_pressed:
            pos = event.pos()
            index = self.indexAt(pos)
            was_pressed_index = self._pressed_index
            self._button_pressed = False
            self._pressed_index = None

            self._trigger_repaint()

            if was_pressed_index and was_pressed_index.isValid():
                target_idx = to_qmodelindex(was_pressed_index)
                btn_rect = self._button_rect_for_index(target_idx)
                if btn_rect.adjusted(-8, -8, 8, 8).contains(QPointF(pos.x(), pos.y())) or (
                    index.isValid() and index.row() == was_pressed_index.row()
                ):
                    log.info("Thumbnail '+' button clicked for row %s -> adding to timeline", was_pressed_index.row())
                    self.add_item_to_timeline(target_idx)
                    event.accept()
                    return

        super().mouseReleaseEvent(event)

    def add_item_to_timeline(self, index):
        """Subclasses should implement this method to insert item into the timeline."""
        pass
