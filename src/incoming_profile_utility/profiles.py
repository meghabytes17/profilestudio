"""Profile catalog / builders.

Each builder returns geometry (polygons per material) in physical space.
Catalog defined in docs/03-profile-catalog.md; finalize against example profiles.
"""
from __future__ import annotations


def film_stack(layers):
    """Planar blanket film stack. TODO."""
    raise NotImplementedError


def line_space_grating(pitch, cd, height, sidewall_angle=90.0):
    """Repeating line/space grating (one symmetric unit cell). TODO."""
    raise NotImplementedError


def trench(pitch, width, depth, sidewall_angle=90.0):
    """STI-style trench. TODO."""
    raise NotImplementedError

# TODO: fin(), gate_stack(), spacer(), via(), ... per docs/03
