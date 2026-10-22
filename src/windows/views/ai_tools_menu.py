"""
 @file
 @brief Shared AI Tools context-menu builder for project files and timeline.
"""

import os
from functools import partial

from qt_api import QIcon

from classes.app import get_app
from classes import info
from .menu import StyledContextMenu


def _trigger_generation(win, template_id, source_file=None, open_dialog=False):
    win.generation_service.action_generate_trigger(
        source_file=source_file,
        template_id=template_id,
        open_dialog=open_dialog,
    )


def _icon(name):
    icon_path = os.path.join(info.PATH, "themes", "cosmic", "images", name)
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    return QIcon()


def add_ai_tools_menu(win, parent_menu, source_file=None):
    _ = get_app()._tr
    if not win.is_comfy_available(force=False):
        return None

    grouped = win.generation_service.build_menu_templates(source_file=source_file)
    menu_defs = []
    if source_file:
        menu_defs = [("enhance", _("Enhance with AI")), ("unknown", _("Unknown AI"))]
    else:
        menu_defs = [("create", _("Create with AI")), ("unknown", _("Unknown AI"))]

    created_menus = []
    for key, title in menu_defs:
        templates = list(grouped.get(key, []) or [])
        if not templates:
            continue
        ai_menu = StyledContextMenu(title=title, parent=parent_menu)
        ai_menu.setIcon(_icon("tool-generate-sparkle.svg"))

        parent_labels = {
            "track_object": _("Track an Object"),
            "extract": _("Extract"),
            "noise": _("Noise"),
            "clarity": _("Clarity"),
        }
        parent_icons = {
            "track_object": "tool-generate-sparkle.svg",
            "extract": "ai-action-create-image.svg",
            "noise": "ai-action-create-audio.svg",
            "clarity": "ai-action-create-audio.svg",
        }
        parent_menus = {}

        inserted_style_separator = False
        for template in templates:
            template_key = str(template.get("template_id") or template.get("id") or "")
            if (
                key == "enhance"
                and not inserted_style_separator
                and template_key in ("img2img-basic", "video2video-basic")
            ):
                ai_menu.addSeparator()
                inserted_style_separator = True

            open_dialog = template.get("open_dialog")
            if not isinstance(open_dialog, bool):
                open_dialog = (
                    source_file is None
                    or bool(template.get("needs_prompt", False))
                    or bool(template.get("extra_inputs"))
                )

            template_parent = str(template.get("menu_parent") or "").strip().lower()
            target_menu = ai_menu
            if key == "enhance" and template_parent:
                if template_parent not in parent_menus:
                    submenu_title = parent_labels.get(template_parent, template_parent.replace("_", " ").title())
                    submenu = StyledContextMenu(title=submenu_title, parent=ai_menu)
                    submenu.setIcon(_icon(parent_icons.get(template_parent, "tool-generate-sparkle.svg")))
                    ai_menu.addMenu(submenu)
                    parent_menus[template_parent] = submenu
                target_menu = parent_menus[template_parent]

            action = target_menu.addAction(_(str(template.get("display_name", ""))))
            action.setIcon(_icon(win.generation_service.icon_for_template(template)))
            action.triggered.connect(
                partial(
                    _trigger_generation,
                    win,
                    template.get("id"),
                    source_file,
                    open_dialog,
                )
            )

        parent_menu.addMenu(ai_menu)
        created_menus.append(ai_menu)

    return created_menus[0] if created_menus else None
