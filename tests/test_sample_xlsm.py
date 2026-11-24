"""Sample (d): the generated macro workbook pair (review-fixes task 5.7, R-13)."""
from __future__ import annotations

import zipfile

from ghost.ingest.vba import extract_vba


def test_pair_contains_vba_project_and_both_modules(macro_samples):
    base, haunted = macro_samples
    for path in (base, haunted):
        with zipfile.ZipFile(path) as z:
            assert "xl/vbaProject.bin" in z.namelist()
        modules = extract_vba(path)
        source = "\n".join(m.source for m in modules)
        assert "Function DeliveryFee" in source
        assert "Sub AwardPoints" in source


def test_haunted_twin_rounds_total_over_ten(macro_samples):
    base, haunted = macro_samples
    base_src = "\n".join(m.source for m in extract_vba(base))
    haunted_src = "\n".join(m.source for m in extract_vba(haunted))
    assert "Int(total / 10)" in base_src and "Round" not in base_src.split("Sub AwardPoints")[1]
    assert "Round(total / 10, 0)" in haunted_src


def test_delivery_fee_formula_is_kept(macro_samples):
    from openpyxl import load_workbook

    ws = load_workbook(macro_samples[0], keep_vba=True)["Calculator"]
    # LibreOffice lower-cases a function name it does not know when it loads the
    # base workbook; VBA names are case-insensitive, so the call is unchanged.
    assert ws["B13"].value.lower() == "=deliveryfee(b2,b4)"
