"""
Timeline backend package helpers.

Ensures legacy ``classes`` imports work when OpenShot is installed under
the ``openshot_qt`` package.
"""

import os
import sys

try:
    import classes  # noqa: F401
except ImportError:
    # When running from a source checkout (for example via unittest discovery),
    # ensure the repository's ``src`` directory is on sys.path so ``classes``
    # can be imported without installing the package.
    checkout_src = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, os.pardir)
    )
    if (
        os.path.isdir(os.path.join(checkout_src, "classes"))
        and checkout_src not in sys.path
    ):
        sys.path.insert(0, checkout_src)

    try:
        import classes  # noqa: F401
    except ImportError:
        try:
            import openshot_qt

            # Prefer OPENSHOT_PATH if upstream defines it, else use package dir
            pkg_dir = getattr(openshot_qt, "OPENSHOT_PATH", None) or os.path.dirname(
                openshot_qt.__file__
            )
            if pkg_dir and pkg_dir not in sys.path:
                sys.path.insert(0, pkg_dir)

            import classes  # noqa: F401
        except Exception:
            # Let the original ImportError surface from downstream imports
            pass
