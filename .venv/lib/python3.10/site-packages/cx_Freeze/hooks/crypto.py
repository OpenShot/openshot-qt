"""A collection of functions which are triggered automatically by finder when
pycryptodome package is included.
"""

from cx_Freeze.hooks.cryptodome import Hook as CryptoHook


class Hook(CryptoHook):
    """The Module Hook class."""

    def __init__(self, module) -> None:
        super().__init__(module)
        self.name = "cryptodome"


__all__ = ["Hook"]
