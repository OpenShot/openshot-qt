"""Confetti cannons that celebrate a successful export."""

import math
from random import Random

from qt_api import QColor, QElapsedTimer, QEvent, QPainter, QPointF, QRectF, Qt, QTimer, QWidget

from classes.logger import log

DURATION_MS = 4800
FADE_MS = 1200
GRAVITY = 450.0
COLORS = ("#ff5e5b", "#ffd23f", "#3bceac", "#5aa9e6", "#ee4266", "#9b5de5", "#f9a03f", "#00bbf9")


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "drag", "sway", "sway_phase", "angle", "spin", "flip", "flip_speed",
                 "width", "height", "color", "round")

    def __init__(self, rng, x, y, direction, reach):
        # Fire up and toward the center, high enough to reach most of the window.
        # Strong drag ends the burst quickly, then flakes flutter down at GRAVITY / drag.
        angle = math.radians(rng.uniform(50, 84))
        self.drag = rng.uniform(2.6, 3.6)
        speed = rng.uniform(0.7, 1.1) * reach * self.drag
        self.sway = rng.uniform(20, 60)
        self.sway_phase = rng.uniform(0, math.tau)
        self.x, self.y = x, y
        self.vx = math.cos(angle) * speed * direction
        self.vy = -math.sin(angle) * speed
        self.angle = rng.uniform(0, 360)
        self.spin = rng.uniform(-540, 540)
        self.flip = rng.uniform(0, math.tau)
        self.flip_speed = rng.uniform(6, 14)
        self.width = rng.uniform(6, 11)
        self.height = self.width * rng.uniform(0.4, 0.7)
        self.color = QColor(rng.choice(COLORS))
        self.round = rng.random() < 0.2

    def advance(self, seconds):
        damping = math.exp(-self.drag * seconds)
        self.vx *= damping
        self.vy = self.vy * damping + GRAVITY * seconds
        self.sway_phase += 3.0 * seconds
        self.x += (self.vx + math.sin(self.sway_phase) * self.sway) * seconds
        self.y += self.vy * seconds
        self.angle += self.spin * seconds
        self.flip += self.flip_speed * seconds


class ConfettiCannon(QWidget):
    """A click-through overlay that fires from both bottom corners, then deletes itself."""

    def __init__(self, parent, count=180, seed=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setGeometry(parent.rect())
        rng = Random(seed)
        # Launch speed follows window height, so any dialog size fills nicely.
        height = parent.height()
        reach = height * 1.05
        self.particles = [
            Particle(rng, 0 if index % 2 == 0 else parent.width(), height,
                     1 if index % 2 == 0 else -1, reach)
            for index in range(count)]
        self.clock = QElapsedTimer()
        self.last_ms = 0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        parent.installEventFilter(self)

    def fire(self):
        self.clock.start()
        self.last_ms = 0
        self.show()
        self.raise_()
        self.timer.start()
        return self

    def eventFilter(self, watched, event):
        if watched is self.parent() and event.type() == QEvent.Resize:
            self.setGeometry(watched.rect())
        return False

    def elapsed_ms(self):
        return self.clock.elapsed()

    def tick(self):
        now = self.elapsed_ms()
        # Cap each step so a stalled event loop doesn't teleport particles.
        seconds = min(0.05, max(0, now - self.last_ms) / 1000.0)
        self.last_ms = now
        for particle in self.particles:
            particle.advance(seconds)
        if now >= DURATION_MS:
            self.finish()
            return
        self.update()

    def finish(self):
        self.timer.stop()
        parent = self.parent()
        if parent is not None:
            parent.removeEventFilter(self)
        self.hide()
        self.deleteLater()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        remaining = DURATION_MS - self.last_ms
        painter.setOpacity(max(0.0, min(1.0, remaining / FADE_MS)))
        for particle in self.particles:
            if particle.y > self.height() + 20 and particle.vy > 0:
                continue
            painter.save()
            painter.translate(QPointF(particle.x, particle.y))
            painter.rotate(particle.angle)
            # Tumble by squashing one axis, which reads as a paper flake flipping.
            painter.scale(1.0, max(0.15, abs(math.cos(particle.flip))))
            painter.setBrush(particle.color)
            rect = QRectF(-particle.width / 2, -particle.height / 2, particle.width, particle.height)
            if particle.round:
                painter.drawEllipse(rect)
            else:
                painter.drawRect(rect)
            painter.restore()
        painter.end()


def should_celebrate(settings):
    """Return whether this export earns confetti, given the user's preference."""
    mode = settings.get("export-celebration")
    if mode == "all":
        return True
    if mode == "none":
        return False
    # "first" (the default) celebrates only the very first successful export.
    return not settings.get("export-celebrated")


def celebrate_export(settings, parent):
    """Fire confetti over parent when the preference allows; never break exporting."""
    try:
        if not should_celebrate(settings):
            return None
        if not settings.get("export-celebrated"):
            settings.set("export-celebrated", True)
            settings.save()
        return ConfettiCannon(parent).fire()
    except Exception:
        log.warning("Unable to celebrate export", exc_info=True)
        return None
