"""Front door: landing page structure, Stepper and Sample_Cards (test-first).

Task 2 of the front-door spec.
Validates: Requirements 1.1-1.6, 1.9, 1.10, 2.2-2.10, 3.1-3.9.

These tests are written before the templates exist. They are expected to fail
until `_stepper.html`, `_sample_card.html` and the new `index.html` land.
Event data (durations) comes from a fixture file built inside the test; the
committed `web/measured_runs.json` is never read here.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from web.app import PRIVACY_NOTE, SAMPLES, create_app

STEPS = [
    ("exhume", "Exhume", "Upload"),
    ("autopsy", "Autopsy", "Findings"),
    ("verdict", "Verdict of the living", "Decisions"),
    ("trial", "Trial", "Verification"),
    ("resurrection", "Resurrection", "Proof"),
]
SAMPLE_IDS = ["discount", "haunted", "scenarios", "macros"]


@pytest.fixture()
def client(tmp_path):
    return TestClient(create_app(session_root=tmp_path / "s"))


@pytest.fixture()
def templates(client):
    return client.app.state.templates


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _landing(client) -> str:
    r = client.get("/")
    assert r.status_code == 200
    return r.text


# ---------- Landing_Page structure (Req 1) ----------

def test_landing_order_tagline_explanation_form_cards_privacy(client):
    html = _landing(client)
    after_header = html.split("</header>", 1)[1]
    tagline = re.search(r"<(h2|p)\b[^>]*>(.*?)</\1>", after_header, re.S)
    assert tagline, "tagline <h2>/<p> directly below the header is missing"
    tag_text = _text(tagline.group(2))
    assert tag_text and tag_text != "Try a sample"
    explanation = re.search(r"<p\b[^>]*>(.*?)</p>", after_header[tagline.end():], re.S)
    assert explanation, "two-sentence explanation paragraph is missing"
    form_at = after_header.index("<form")
    # tagline and explanation both come before the upload form
    assert tagline.start() < after_header[tagline.end():].index(explanation.group(0)) + tagline.end() < form_at
    first_card = min(after_header.index(f"/sample/{i}/workbook") for i in SAMPLE_IDS)
    last_card = max(after_header.index(f"/sample/{i}/workbook") for i in SAMPLE_IDS)
    privacy_at = after_header.index('id="privacy-note"')
    assert form_at < first_card <= last_card < privacy_at


def test_landing_explanation_is_exactly_two_sentences(client):
    html = _landing(client)
    after_header = html.split("</header>", 1)[1]
    tagline = re.search(r"<(h2|p)\b[^>]*>.*?</\1>", after_header, re.S)
    assert tagline
    explanation = re.search(r"<p\b[^>]*>(.*?)</p>", after_header[tagline.end():], re.S)
    assert explanation
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", _text(explanation.group(1))) if s]
    assert len(sentences) == 2, sentences


def test_landing_has_privacy_note_once_after_cards(client):
    html = _landing(client)
    assert PRIVACY_NOTE in html
    assert html.count('id="privacy-note"') == 1


def test_landing_links_to_repository(client):
    assert re.search(r'<a\b[^>]*href="https://github\.com/[^"]+"', _landing(client))


def test_landing_has_no_kiro_or_video_link_or_placeholder(client):
    html = _landing(client)
    hrefs = re.findall(r'<a\b[^>]*href="([^"]*)"', html)
    for href in hrefs:
        low = href.lower()
        assert "kiro" not in low and "youtu" not in low and "video" not in low, href
    lowered = _text(html).lower()
    assert "coming soon" not in lowered
    assert "kiro" not in lowered
    assert "video" not in lowered


def test_landing_head_has_favicon_description_and_open_graph(client):
    head = _landing(client).split("</head>", 1)[0]
    assert re.search(r'<link\b[^>]*rel="[^"]*icon[^"]*"', head)
    assert re.search(r'<meta\b[^>]*name="description"[^>]*content="[^"]+"', head)
    for prop in ("og:title", "og:description", "og:type", "og:url"):
        assert re.search(rf'<meta\b[^>]*property="{prop}"[^>]*content="[^"]+"', head), prop


# ---------- Stepper (Req 2) ----------

class _Steps(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items: list[dict] = []
        self._depth_li = False

    def handle_starttag(self, tag, attrs):
        if tag == "li":
            self.items.append({"attrs": dict(attrs), "text": ""})
            self._depth_li = True

    def handle_endtag(self, tag):
        if tag == "li":
            self._depth_li = False

    def handle_data(self, data):
        if self._depth_li and self.items:
            self.items[-1]["text"] += data


def _render_stepper(templates, current_step: str):
    html = templates.get_template("_stepper.html").render(current_step=current_step)
    p = _Steps()
    p.feed(html)
    return html, p.items


def test_stepper_lists_five_steps_in_order_with_both_names(templates):
    _, items = _render_stepper(templates, "exhume")
    assert len(items) == 5
    for item, (_, themed, plain) in zip(items, STEPS):
        text = " ".join(item["text"].split())
        assert themed in text and plain in text, text
        assert text.index(themed) < text.index(plain)


@pytest.mark.parametrize("index", range(5))
def test_stepper_marks_exactly_one_current_step(templates, index):
    key = STEPS[index][0]
    html, items = _render_stepper(templates, key)
    assert html.count('aria-current="step"') == 1
    current = [i for i, it in enumerate(items) if it["attrs"].get("aria-current") == "step"]
    assert current == [index]


@pytest.mark.parametrize("index", range(5))
def test_stepper_current_step_has_non_colour_cue(templates, index):
    _, items = _render_stepper(templates, STEPS[index][0])
    cur = " ".join(items[index]["text"].split()).lower()
    others = [" ".join(it["text"].split()).lower() for i, it in enumerate(items) if i != index]
    # a visible text cue only the current step carries (e.g. "current step")
    assert "current" in cur
    assert all("current" not in o for o in others)


def test_landing_stepper_current_is_exhume(client):
    html = _landing(client)
    assert html.count('aria-current="step"') == 1
    m = re.search(r'<li\b[^>]*aria-current="step"[^>]*>(.*?)</li>', html, re.S)
    assert m and "Exhume" in m.group(1)


# ---------- Sample_Cards (Req 3) ----------

def _measured_file(tmp_path):
    path = tmp_path / "measured_runs.json"
    path.write_text(json.dumps({"discount": {"seconds": 5.3, "date": "2026-11-24", "cases": 500, "measured_on": "local development machine (macOS), not the deployed host"}}))
    return json.loads(path.read_text())


def _card(templates, sample_id: str, measured):
    label = SAMPLES[sample_id][2]
    blurb = "Holds a discount formula. No difference found on N cases is the expected result."
    return templates.get_template("_sample_card.html").render(
        id=sample_id, label=label, blurb=blurb, measured=measured
    ), blurb


def test_landing_has_every_card_in_order_with_download_links(client):
    html = _landing(client)
    ats = [html.index(f'href="/sample/{i}/workbook"') for i in SAMPLE_IDS]
    assert ats == sorted(ats)
    for i in SAMPLE_IDS:
        assert html.count(f'href="/sample/{i}/workbook"') == 1
    assert html.count("Download the workbook") == len(SAMPLE_IDS) == len(SAMPLES)


def test_landing_cards_keep_run_button_target_and_generated_label(client):
    html = _landing(client)
    for i in SAMPLE_IDS:
        label = SAMPLES[i][2]
        assert label.endswith("(generated)")
        m = re.search(rf'<button\b[^>]*hx-post="/sample/{i}"[^>]*>(.*?)</button>', html, re.S)
        assert m, i
        assert 'hx-target="#result"' in m.group(0)
        assert label in html


def test_landing_card_blurbs_are_one_sentence_and_avoid_correct_or_proven(client):
    html = _landing(client)
    for i in SAMPLE_IDS:
        card = re.search(
            rf'<(li|article|div)\b[^>]*>(?:(?!</\1>).)*?/sample/{i}/workbook.*?</\1>', html, re.S
        )
        assert card, i
        text = _text(card.group(0)).lower()
        assert "download the workbook" in text
        assert "correct" not in text and "proven" not in text


def test_card_partial_renders_blurb_run_button_and_download_link(templates, tmp_path):
    data = _measured_file(tmp_path)
    html, blurb = _card(templates, "discount", data["discount"])
    assert blurb in _text(html)
    assert 'hx-post="/sample/discount"' in html
    assert 'hx-target="#result"' in html
    assert re.search(r'<a\b[^>]*href="/sample/discount/workbook"[^>]*>\s*Download the workbook\s*</a>', html)
    assert SAMPLES["discount"][2] in _text(html)


def test_card_shows_measured_duration_with_date_and_cases(templates, tmp_path):
    data = _measured_file(tmp_path)
    html, _ = _card(templates, "discount", data["discount"])
    text = _text(html)
    assert "measured" in text.lower()
    assert "5.3" in text and "2026-11-24" in text and "500" in text
    # Owner decision (task 17 follow-up): the card says it is one run, not a typical value.
    assert "One measured run: 5.3 s on 2026-11-24, 500 cases" in text


def test_card_shows_measured_on_label_from_file(templates, tmp_path):
    data = _measured_file(tmp_path)
    html, _ = _card(templates, "discount", data["discount"])
    assert data["discount"]["measured_on"] in _text(html)


def test_card_entry_without_measured_on_shows_no_duration(templates):
    entry = {"seconds": 5.3, "date": "2026-11-24", "cases": 500}
    html, _ = _card(templates, "discount", entry)
    text = _text(html).lower()
    assert "measured" not in text
    assert "5.3" not in text


def test_scenarios_blurb_is_the_single_sentence_the_owner_chose(client):
    # Owner decision 2026-11-25: no engine change for E3; the blurb says what a visitor sees.
    assert (
        "A model with ten tax scenarios that picks the lowest net cost with INDEX and MATCH; "
        "three inputs are checked by default and the other constants stay fixed; "
        "expect a Faithful run with no difference found on the cases tested."
    ) in _text(_landing(client))
def test_measured_runs_say_local_run_and_that_the_live_site_is_slower():
    from web import app as webapp
    runs = webapp.load_measured_runs()
    assert set(runs) == {"discount", "haunted", "scenarios"}
    for sid, r in runs.items():
        assert "local" in r["measured_on"].lower() and "live site is slower" in r["measured_on"], sid
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]), sid
def test_load_measured_runs_reads_web_package_file():
    from web import app as webapp
    assert webapp.MEASURED_RUNS_FILE.parent.name == "web"
    runs = webapp.load_measured_runs()
    assert set(runs) == {"discount", "haunted", "scenarios"}
    assert all(r.get("measured_on") for r in runs.values())


def test_card_without_measured_duration_shows_no_duration(templates):
    html, _ = _card(templates, "haunted", None)
    text = _text(html).lower()
    assert "measured" not in text
    assert not re.search(r"\d+(\.\d+)?\s*(s|sec|seconds)\b", text)


def test_landing_does_not_compute_durations_at_request_time(client):
    # Durations come from a committed file; with none present for a sample,
    # no duration text may appear for it. No timing is invented.
    html = _landing(client)
    for m in re.finditer(r"measured", html, re.I):
        window = _text(html[m.start(): m.start() + 200])
        assert re.search(r"\d{4}-\d{2}-\d{2}", window), window
