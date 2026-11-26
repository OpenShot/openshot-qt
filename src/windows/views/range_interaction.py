"""Shared grip hit testing for the timeline zoom and source-range controls."""
from qt_api import QPointF, QRectF


def range_hit_target(pos, selection, left_grip, right_grip, move_rect, top, height, midpoint=None):
    """Expand painted grips and split overlapping targets so both remain usable."""
    # Qt6 bindings reject QRectF.contains(QPoint), so compare as floats throughout
    point = QPointF(pos)
    left_hit = QRectF(left_grip.left() - 4, top, left_grip.width() + 8, height).contains(point)
    right_hit = QRectF(right_grip.left() - 4, top, right_grip.width() + 8, height).contains(point)
    if left_hit and right_hit:
        center = selection.center().x() if midpoint is None else midpoint
        return 'left' if pos.x() <= center else 'right'
    if left_hit:
        return 'left'
    if right_hit:
        return 'right'
    return 'move' if QRectF(move_rect).contains(point) else 'create'
