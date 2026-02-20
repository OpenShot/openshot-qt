"""Extend msilib Dialog."""

from __future__ import annotations

from msilib import Control, Dialog


class PyDialog(Dialog):
    """Dialog class with a fixed layout: controls at the top, then a ruler,
    then a list of buttons: back, next, cancel. Optionally a bitmap at the
    left.
    """

    def __init__(
        self,
        db,
        name,
        x,
        y,
        w,
        h,
        attr,
        title,
        first,
        default,
        cancel,
        bitmap=True,  # noqa: ARG002
    ) -> None:
        Dialog.__init__(
            self, db, name, x, y, w, h, attr, title, first, default, cancel
        )
        ruler = self.h - 36
        # bmwidth = 152 * ruler / 328
        # if kw.get("bitmap", True):
        #    self.bitmap("Bitmap", 0, 0, bmwidth, ruler, "PythonWin")
        self.line("BottomLine", 0, ruler, self.w, 0)

    def title(self, title) -> None:
        """Set the title text of the dialog at the top."""
        # flags=0x30003=Visible|Enabled|Transparent|NoPrefix
        # text, in VerdanaBold10
        font = r"{\VerdanaBold10}"
        self.text("Title", 15, 10, 320, 60, 0x30003, f"{font}{title}")

    def backbutton(self, title, tabnext, name="Back", active=1) -> Control:
        """Add a back button with a given title, the tab-next button,
        its name in the Control table, possibly initially disabled.

        Return the button, so that events can be associated
        """
        flags = 3 if active else 1  # Visible|Enabled or Visible
        return self.pushbutton(
            name, 180, self.h - 27, 56, 17, flags, title, tabnext
        )

    def cancelbutton(self, title, tabnext, name="Cancel", active=1) -> Control:
        """Add a cancel button with a given title, the tab-next button,
        its name in the Control table, possibly initially disabled.

        Return the button, so that events can be associated
        """
        flags = 3 if active else 1  # Visible|Enabled or Visible
        return self.pushbutton(
            name, 304, self.h - 27, 56, 17, flags, title, tabnext
        )

    def nextbutton(self, title, tabnext, name="Next", active=1) -> Control:
        """Add a Next button with a given title, the tab-next button,
        its name in the Control table, possibly initially disabled.

        Return the button, so that events can be associated
        """
        flags = 3 if active else 1  # Visible|Enabled or Visible
        return self.pushbutton(
            name, 236, self.h - 27, 56, 17, flags, title, tabnext
        )

    def xbutton(self, name, title, tabnext, xpos) -> Control:
        """Add a button with a given title, the tab-next button,
        its name in the Control table, giving its x position; the
        y-position is aligned with the other buttons.

        Return the button, so that events can be associated
        """
        return self.pushbutton(
            name,
            int(self.w * xpos - 28),
            self.h - 27,
            56,
            17,
            3,
            title,
            tabnext,
        )
