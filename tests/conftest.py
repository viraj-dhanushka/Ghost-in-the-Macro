"""Shared fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def macro_samples(tmp_path_factory):
    """Build sample (d), the generated .xlsm pair, once per session.

    Returns (discount_vba.xlsm, haunted_vba.xlsm). Skips when LibreOffice is absent.
    """
    from ghost.referee.locate import RefereeUnavailable, locate_soffice

    try:
        soffice = locate_soffice()
    except RefereeUnavailable as exc:
        pytest.skip(f"soffice not available, cannot build the macro sample: {exc}")
    from samples import make_xlsm

    return make_xlsm.build_pair(tmp_path_factory.mktemp("macro_samples"), soffice)
