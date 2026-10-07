"""Generate small, self-contained projects for manually verifying issue #6177.

Run with the same Python/libopenshot environment used to launch OpenShot:
    python3 benchmarks/generate_issue_6177_projects.py /tmp/openshot-6177
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import openshot
from classes import info
from qt_api import QApplication, QColor, QFont, QImage, QPainter, Qt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    template = json.loads((Path(__file__).resolve().parents[1] / "src/settings/_default.project").read_text())
    for index, color in enumerate(("red", "green", "orange", "purple", "blue"), 1):
        image = QImage(1280, 720, QImage.Format_RGBA8888)
        image.fill(QColor(color))
        painter = QPainter(image)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Sans", 200))
        painter.drawText(image.rect(), Qt.AlignCenter, str(index))
        painter.end()
        if not image.save(str(output / ("%s.png" % index))):
            raise RuntimeError("Failed to write PNG")

    for fps in (25, 30):
        project = copy.deepcopy(template)
        project.update(profile="HD 720p %s fps" % fps, width=1280, height=720,
                       fps={"num": fps, "den": 1}, files=[], clips=[], effects=[],
                       version={"openshot-qt": info.VERSION, "libopenshot": openshot.OPENSHOT_VERSION_FULL},
                       scale=0.1, playhead_position=0.0)
        for index in range(1, 6):
            native = openshot.Clip(str(output / ("%s.png" % index)))
            native.Start(0)
            native.End(1 / fps)
            native.Position((index - 1) / fps)
            native.Layer(5000000)
            clip = json.loads(native.Json())
            file_id = "FILE%s" % index
            clip.update(id="CLIP%s" % index, file_id=file_id)
            clip["reader"].update(id=file_id, media_type="image")
            project["clips"].append(clip)
            project["files"].append(copy.deepcopy(clip["reader"]))
        (output / ("five-frames-%s.osp" % fps)).write_text(json.dumps(project, indent=2))
        if fps == 25:
            orphaned = copy.deepcopy(project)
            orphaned["files"] = orphaned["files"][:2]
            orphaned["clips"][1]["file_id"] = "OLD_FILE2"
            orphaned["clips"][1]["reader"]["id"] = "OLD_FILE2"
            (output / "orphaned-files-25.osp").write_text(json.dumps(orphaned, indent=2))
            for index, clip in enumerate(project["clips"]):
                clip["position"] = index * 10.0
            (output / "gapped-frames-25.osp").write_text(json.dumps(project, indent=2))
    print(output)


if __name__ == "__main__":
    main()
