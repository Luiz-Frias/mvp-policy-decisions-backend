"""Central logging utilities for the MVP Policy Decision Backend.

This module enforces a consistent logging configuration across the entire
code-base and provides convenience helpers for retrieving module-scoped
loggers as well as monkey-patching the built-in ``print`` for legacy code
paths.

Key Features
------------
1. configure_logging(): idempotent initialization of the root logger.
2. get_logger(name): typed helper that always returns a configured logger.
3. patch_print(): optional helper that redirects ``print`` calls to the
   logging subsystem while preserving semantics.

Note: ``patch_print`` should only be used as a temporary bridge when a full
refactor is not yet feasible. Prefer explicit ``logger.<level>()`` calls in
new or updated code.
"""

from __future__ import annotations

import builtins
import logging
from typing import Final

from beartype import beartype

__all__: Final = [
    "configure_logging",
    "get_logger",
    "patch_print",
]

_DEFAULT_LOG_FORMAT: Final = (
    "% (asctime)s - %(name)s - %(levelname)s - %(message)s".replace(" % ", "%")
)
_is_configured: bool = False


@beartype
def configure_logging(
    *, level: int = logging.INFO, fmt: str = _DEFAULT_LOG_FORMAT
) -> None:
    """Configure the root logger exactly once.

    Calling this function multiple times is safe – configuration will only
    be applied on the first invocation.
    """
    global _is_configured
    if _is_configured:
        return

    logging.basicConfig(level=level, format=fmt)
    _is_configured = True


@beartype
def get_logger(name: str | None = None, *, level: int | None = None) -> logging.Logger:
    """Return a module-scoped logger that is guaranteed to be configured."""
    configure_logging()
    logger = logging.getLogger(name or "pd_prime_demo")
    if level is not None:
        logger.setLevel(level)
    return logger


@beartype
def patch_print(*, level: int = logging.INFO) -> None:
    """Redirect built-in ``print`` to the logging subsystem.

    This is intended as a *stop-gap* measure for legacy scripts that still
    rely on ``print``. It should **not** be considered a long-term solution.
    """

    configure_logging()
    logger = get_logger("print_patch")

    def _logger_print(*args: object, **kwargs: object) -> None:  # noqa: D401
        sep = str(kwargs.get("sep", " "))
        end = str(kwargs.get("end", "\n"))
        msg = sep.join(str(arg) for arg in args) + end.rstrip("\n")
        logger.log(level, msg)

    builtins.print = _logger_print
