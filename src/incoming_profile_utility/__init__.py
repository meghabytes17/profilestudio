"""Incoming Profile Utility.

Generate symmetric semiconductor cross-section profiles from CSV/parametric input
and render them to .bmp.
"""

# ---------------------------------------------------------------------------
# Single source of truth for the version. Bump __version__ on each release and
# set __build_date__ to that day. Everything else (title bar, header, About,
# .exe metadata) reads from here, so a screenshot always reveals the exact build.
# ---------------------------------------------------------------------------
__version__ = "1.2.0"
__build_date__ = "2026-08-06"          # ISO date of this build
APP_NAME = "Profile Studio"


def version_string() -> str:
    """e.g. 'Profile Studio 1.0.0 (2026-07-17)'."""
    return f"{APP_NAME} {__version__} ({__build_date__})"


def short_version() -> str:
    """e.g. 'v1.0.0' — for compact places like the title bar."""
    return f"v{__version__}"
