"""R-23: border contrast (WCAG 1.4.11) and a constant theme-toggle label."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
CSS = (WEB / "static" / "style.css").read_text(encoding="utf-8")
JS = (WEB / "static" / "theme.js").read_text(encoding="utf-8")
HTML = (WEB / "templates" / "index.html").read_text(encoding="utf-8")


def _lum(hex_colour):
    ch = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _vars(block):
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})", block))


def _block(start_pattern):
    m = re.search(start_pattern + r"\s*\{(.*?)\}", CSS, re.S | re.M)
    assert m, start_pattern
    return _vars(m.group(1))


def test_dark_border_contrast_at_least_3_to_1():
    v = _block(r"^:root")
    assert contrast(v["border"], v["bg"]) >= 3.0
    assert contrast(v["border"], v["surface"]) >= 3.0


def test_light_border_contrast_at_least_3_to_1():
    v = _block(r':root\[data-theme="light"\]')
    assert contrast(v["border"], v["bg"]) >= 3.0
    assert contrast(v["border"], v["surface"]) >= 3.0


def test_toggle_markup_has_constant_label_and_aria_pressed():
    m = re.search(r'<button[^>]*id="theme-toggle"[^>]*>(.*?)</button>', HTML, re.S)
    assert m
    assert "aria-pressed=" in m.group(0)
    assert m.group(1).strip() == "Light mode"


def test_toggle_js_sets_aria_pressed_and_never_changes_label():
    assert "aria-pressed" in JS
    assert "textContent" not in JS and "innerText" not in JS and "innerHTML" not in JS
