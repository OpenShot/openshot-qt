"""Helpers for unit tests that need an OpenShot-like Qt application."""

import types

from qt_api import QApplication


def get_or_create_app(factory):
    """Return the process-wide Qt app and whether factory() created it.

    The creation flag does not confer ownership of the application's lifetime.
    Test classes must not call quit() in teardown: later classes reuse this
    instance, and quitting makes their local QEventLoops exit before timers run.
    The test process owns application shutdown.
    """
    app = QApplication.instance()
    if app is not None:
        return app, False
    return factory(), True


def ensure_app_state(
    app,
    settings_factory,
    project_factory=None,
    updates_factory=None,
    extra_attrs=None,
):
    """Attach OpenShot-style attributes/methods to any Qt application instance."""
    if not hasattr(app, "settings") or app.settings is None:
        app.settings = settings_factory()

    if not callable(getattr(app, "get_settings", None)):
        app.get_settings = types.MethodType(lambda self: self.settings, app)

    if not callable(getattr(app, "_tr", None)):
        app._tr = types.MethodType(lambda self, text: text, app)

    if project_factory is not None:
        project = getattr(app, "project", None)
        if (
            project is None
            or not hasattr(project, "get")
            or not hasattr(project, "generate_id")
        ):
            app.project = project_factory()

    if updates_factory is not None:
        app.updates = updates_factory()
        if hasattr(app.updates, "add_listener") and getattr(app, "project", None) is not None:
            app.updates.add_listener(app.project)
        if hasattr(app.updates, "reset"):
            app.updates.reset()

    for attr, value in (extra_attrs or {}).items():
        if not hasattr(app, attr):
            setattr(app, attr, value)

    return app
