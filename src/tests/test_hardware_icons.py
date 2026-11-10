# SPDX-FileCopyrightText: 2026 OpenShot Studios, LLC
# SPDX-License-Identifier: GPL-3.0-or-later
"""Hardware dropdown glyphs remain scalable and independent of installed fonts."""
import unittest
# Parse only SVG fixtures from this repository.
import xml.etree.ElementTree as ET  # nosec B405

from qt_api import QApplication, QIcon, QSize, QSvgRenderer
from classes import hardware_rc  # pylint: disable=unused-import  # Registers vector badges.
from tests.source_tree import source_path


class HardwareIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_both_badges_use_outlines_without_font_or_bitmap_dependencies(self):
        for name in ('cpu', 'gpu'):
            with self.subTest(name=name):
                svg = source_path('images') / ('hardware-' + name + '.svg')
                root = ET.fromstring(svg.read_bytes())  # nosec B314
                self.assertEqual(root.get('viewBox'), '0 0 64 22')
                self.assertFalse(any(n.tag.rsplit('}', 1)[-1] in ('text', 'image') for n in root.iter()))
                renderer = QSvgRenderer(str(svg))
                self.assertTrue(renderer.isValid())
                icon = QIcon(':/hardware/%s.svg' % name)
                self.assertFalse(icon.isNull())
                for scale in (1, 2, 3):
                    pixmap = icon.pixmap(QSize(64 * scale, 22 * scale))
                    self.assertFalse(pixmap.isNull())
                    self.assertEqual(pixmap.size(), QSize(64 * scale, 22 * scale))
