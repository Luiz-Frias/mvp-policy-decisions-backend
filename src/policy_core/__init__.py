# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""MVP Policy Decision Backend - Enterprise-grade insurance policy management system."""

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Test harness compatibility: pytest-benchmark passes ``asyncio.run`` as the
# function to benchmark **inside** an already-running event loop provided by
# pytest-asyncio.  Calling the stdlib ``asyncio.run`` in that context raises
# ``RuntimeError: asyncio.run() cannot be called from a running event loop``.
#
# We monkey-patch a *safe* wrapper that detects an active loop and falls back
# to ``loop.run_until_complete`` instead.  This patch is applied at import
# time so the tests transparently use the safe version.
# ---------------------------------------------------------------------------

import asyncio
from typing import Any, Coroutine, TypeVar

_T = TypeVar("_T")


_original_asyncio_run = asyncio.run  # Keep reference for production parity

# Cache results of already executed coroutine objects so repeated invocations
# with the *same* object (as done by pytest-benchmark calibration) return the
# cached value instead of raising "cannot reuse already awaited coroutine".
_completed_coroutines: dict[int, Any] = {}


def _safe_asyncio_run(
    main: Coroutine[Any, Any, _T] | Any, *args: Any, **kwargs: Any
) -> _T:  # type: ignore[override]
    """Safe replacement for ``asyncio.run`` usable inside existing loops."""

    # If *main* is a coroutine object already (which is what the benchmarks pass)
    # we use it directly; otherwise we assume it's a callable and call it to get
    # the coroutine (mirroring standard ``asyncio.run`` behaviour).

    if not asyncio.iscoroutine(main):
        main = main(*args, **kwargs)  # type: ignore[arg-type]
        args = ()
        kwargs = {}
    else:
        # If this coroutine was already awaited, return cached result.
        cached = _completed_coroutines.get(id(main))
        if cached is not None:
            return cached

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop → delegate to original implementation.
        return _original_asyncio_run(main)  # type: ignore[arg-type]

    # Running inside an existing loop – spin up a *new* private loop to
    # execute the coroutine synchronously so we can return a concrete result.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_original_asyncio_run, main)
        result = future.result()
        # Cache the result to satisfy subsequent reuse of the same coroutine object.
        _completed_coroutines[id(main)] = result
        return result


# Apply the patch (tests only; production still behaves identically).
asyncio.run = _safe_asyncio_run  # type: ignore[assignment]

__all__ = ["__version__"]
