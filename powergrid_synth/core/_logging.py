"""
Package-wide logging.

All progress messages go through the ``powergrid_synth`` logger instead of
bare ``print`` calls, so they can be silenced or made more detailed in one
place::

    import powergrid_synth as pgs

    pgs.set_verbosity("silent")   # nothing at all
    pgs.set_verbosity("warning")  # problems only
    pgs.set_verbosity("info")     # one line per pipeline stage (default)
    pgs.set_verbosity("debug")    # per-level / per-iteration detail

The logger writes plain lines to ``sys.stdout`` so notebook output looks the
same as before.  To route messages somewhere else, attach your own handler to
``logging.getLogger("powergrid_synth")`` and call ``set_verbosity`` as usual.
"""

from __future__ import annotations

import contextlib
import logging
import sys
from typing import Iterator, Union

logger = logging.getLogger("powergrid_synth")

_LEVELS = {
    "silent": logging.CRITICAL + 10,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


class _StdoutHandler(logging.StreamHandler):
    """Stream handler that looks up ``sys.stdout`` at emit time.

    Resolving the stream late means output still lands in the right place when
    stdout is swapped out (Jupyter cells, ``contextlib.redirect_stdout``,
    pytest's ``capsys``).
    """

    def __init__(self) -> None:
        super().__init__(stream=sys.stdout)

    @property
    def stream(self):  # type: ignore[override]
        return sys.stdout

    @stream.setter
    def stream(self, value) -> None:
        # The base class assigns ``self.stream`` in __init__; ignore it.
        pass


def _resolve(level: Union[str, bool, int]) -> int:
    if isinstance(level, bool):
        return logging.INFO if level else logging.WARNING
    if isinstance(level, int):
        return level
    try:
        return _LEVELS[level.lower().strip()]
    except (KeyError, AttributeError):
        raise ValueError(
            f"Unknown verbosity {level!r}. Choose one of {sorted(_LEVELS)}, "
            f"True/False, or a logging level number."
        ) from None


def set_verbosity(level: Union[str, bool, int] = "info") -> None:
    """Set how much progress output the package prints.

    Parameters
    ----------
    level : {"silent", "warning", "info", "debug"} or bool or int
        ``"info"`` (default) prints one line per pipeline stage,
        ``"debug"`` adds per-level and per-iteration detail,
        ``"warning"`` prints problems only and ``"silent"`` prints nothing.
        ``True`` / ``False`` are shorthand for ``"info"`` / ``"warning"``.
        A :mod:`logging` level number is accepted as well.
    """
    logger.setLevel(_resolve(level))


@contextlib.contextmanager
def verbosity(level: Union[str, bool, int]) -> Iterator[None]:
    """Temporarily change the verbosity inside a ``with`` block."""
    previous = logger.level
    logger.setLevel(_resolve(level))
    try:
        yield
    finally:
        logger.setLevel(previous)


def _install_default_handler() -> None:
    if any(isinstance(h, _StdoutHandler) for h in logger.handlers):
        return
    handler = _StdoutHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Messages are already printed by the handler above; propagating them to
    # the root logger would print them a second time for users who have
    # configured logging themselves.
    logger.propagate = False


_install_default_handler()
