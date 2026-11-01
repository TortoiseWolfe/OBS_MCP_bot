"""Tests for the tutorial review: synthetic pictures for the layout checks, captured ffmpeg text for the sound parsers."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from playout.tutorials import catalog, layout, sound  # noqa: E402

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"


def canvas(bg=(30, 24, 18)):
    im = Image.new("RGB", (1920, 1080), bg)
    return im, ImageDraw.Draw(im)


def text(d, xy, s, size=34, fill=(235, 225, 205)):
    f = ImageFont.truetype(FONT, size) if Path(FONT).exists() else ImageFont.load_default()
    d.text(xy, s, font=f, fill=fill)
    b = d.textbbox(xy, s, font=f)
    return layout.Line(b[0], b[1], b[2], b[3], s)


def checks(found):
    return {(f["check"], f["severity"]) for f in found}


def test_line_boxes_from_ocr_sorted():
    res = [([[10, 50], [90, 50], [90, 70], [10, 70]], "b", 0.9), ([[10, 10], [90, 10], [90, 30], [10, 30]], "a", 0.9)]
    assert [ln.text for ln in layout.lines_from_ocr(res)] == ["a", "b"]


def test_chrome_lines_are_not_content():
    assert layout.is_chrome(layout.Line(60, 20, 280, 48, "Section 1 of 8"))
    assert layout.is_chrome(layout.Line(1650, 1030, 1860, 1060, "ScriptHammer.com"))
    assert not layout.is_chrome(layout.Line(60, 300, 900, 340, "Dialog role identifies an element"))


def test_empty_slide_is_white_space_blocker():
    im, d = canvas()
    ln = text(d, (80, 120), "Tiny title", 30)
    found, feats = layout.analyze(np.array(im), [ln], "content")
    assert ("white-space", "BLOCKER") in checks(found)
    assert feats["area"] < 0.12


def test_title_screens_never_block_on_white_space():
    im, d = canvas()
    ln = text(d, (80, 120), "Tiny title", 30)
    found, _ = layout.analyze(np.array(im), [ln], "intro")
    assert ("white-space", "UPDATE") in checks(found) and ("white-space", "BLOCKER") not in checks(found)


def test_text_on_the_frame_edge_is_clipping():
    im, d = canvas()
    ln = text(d, (1700, 400), "A heading that runs off the right edge", 40)
    ln.x1 = 1920
    found, _ = layout.analyze(np.array(im), [ln], "content")
    assert any(c == "clip-frame" for c, _ in checks(found))


def test_ellipsis_means_truncated():
    im, d = canvas()
    ln = text(d, (100, 400), "This sentence was cut by its box…", 36)
    found, _ = layout.analyze(np.array(im), [ln], "content")
    assert any(c == "clip-ellipsis" for c, _ in checks(found))


def test_low_contrast_body_text_blocks_but_chrome_only_updates():
    im, d = canvas(bg=(40, 40, 40))
    body = text(d, (100, 300), "Body text nobody can read here", 36, fill=(70, 70, 70))
    chrome = text(d, (100, 20), "Section 1 of 8", 30, fill=(70, 70, 70))
    found, _ = layout.analyze(np.array(im), [body, chrome], "content")
    got = {(f["check"], f["severity"], f["detail"][:20]) for f in found if f["check"] == "contrast"}
    assert any(sev == "BLOCKER" for _, sev, _ in got) and any(sev == "UPDATE" for _, sev, _ in got)


def test_large_text_needs_only_three_to_one():
    im, d = canvas(bg=(30, 30, 30))
    big = text(d, (100, 300), "Large headline text here", 60, fill=(125, 125, 125))
    found, _ = layout.analyze(np.array(im), [big], "content")
    assert not [f for f in found if f["check"] == "contrast"]


def test_old_versions_listed():
    ln = layout.Line(100, 400, 700, 440, "Built with Next.js 14 and React 18")
    hits = layout.check_versions([ln])
    assert hits and hits[0]["severity"] == "UPDATE"
    assert not layout.check_versions([layout.Line(0, 0, 10, 10, "Next.js 16 on Node 24")])


def test_old_version_regex_ignores_longer_numbers():
    assert not layout.OLD_VERSION.search("Node 180 workers")


def test_single_word_last_line_is_blocker():
    im, d = canvas()
    l1 = text(d, (80, 400), "The quick brown fox jumps over the lazy dog and keeps running far", 36)
    l2 = text(d, (80, 442), "away", 36)
    gray = np.array(im.convert("L"))
    out = layout.check_single_word(gray, [l1, l2])
    assert out and out[0]["check"] == "single-word-line"


def test_two_word_last_line_is_fine():
    im, d = canvas()
    l1 = text(d, (80, 400), "The quick brown fox jumps over the lazy dog and keeps running far", 36)
    l2 = text(d, (80, 442), "far away", 36)
    gray = np.array(im.convert("L"))
    assert not layout.check_single_word(gray, [l1, l2])


def test_card_repeating_its_title_is_flagged():
    im, d = canvas()
    a = text(d, (80, 500), "Accessible Components and Testing", 60)
    b = text(d, (80, 600), "Accessible Components and Testing", 40)
    found, _ = layout.analyze(np.array(im), [a, b], "card")
    assert ("card-duplicate-text", "UPDATE") in checks(found)


# sound parsers on captured ffmpeg text
SIL = """[silencedetect @ 0x1] silence_start: 1.5
[silencedetect @ 0x1] silence_end: 4.0 | silence_duration: 2.5
[silencedetect @ 0x1] silence_start: 20.25"""


def test_silence_parser_closes_open_gap_at_the_end():
    got = sound.parse_silences(SIL, 30.0)
    assert got[0] == (1.5, 4.0) and got[1][0] == 20.25 and got[1][1] == pytest.approx(30.0)


def test_black_and_freeze_parsers():
    assert sound.parse_black("black_start:3.2 black_end:5.0 black_duration:1.8") == [(3.2, 5.0)]
    assert sound.parse_freezes("freeze_start: 10.0\nfreeze_end: 45.5", 100) == [(10.0, 45.5)]
    assert sound.parse_freezes("freeze_start: 90.0", 100) == [(90.0, 100)]


def test_loudness_parser_reads_the_summary_block():
    txt = "Summary:\n\n  Integrated loudness:\n    I:         -16.2 LUFS\n  True peak:\n    Peak:       -1.4 dBFS\n"
    assert sound.parse_loudness(txt) == (-16.2, -1.4)


def facts(**kw):
    base = dict(width=1920, height=1080, fps=30.0, v_dur=60.0, a_dur=60.0, has_audio=True, duration=60.0)
    base.update(kw)
    return base


def test_clean_content_has_no_findings():
    assert sound.evaluate("content", facts(), [(3.0, 3.4)], [], [], -16.0, -1.4) == []


def test_dead_air_clipping_length_and_black_are_blockers():
    f = sound.evaluate("content", facts(a_dur=61.0), [(10.0, 13.0)], [(20.0, 22.0)], [], -16.0, 0.0)
    assert {x["check"] for x in f} == {"av-length", "clipping", "dead-air", "black"}
    assert all(x["severity"] == "BLOCKER" for x in f)


def test_wrong_size_and_rate_block():
    f = sound.evaluate("content", facts(width=1280, height=720, fps=24.0), [], [], [], -16.0, -2.0)
    assert {x["check"] for x in f} == {"resolution", "frame-rate"}


def test_frozen_picture_with_text_is_a_deliberate_still():
    assert sound.evaluate("content", facts(), [], [], [(10, 50)], -16.0, -2.0, slide_text=lambda t: True) == []
    assert sound.evaluate("content", facts(), [], [], [(10, 50)], -16.0, -2.0, slide_text=lambda t: False)[0]["check"] == "frozen"


def test_silent_bumper_is_only_an_update():
    f = sound.evaluate("intro", facts(), [(0.0, 60.0)], [], [], -70.0, None)
    assert [(x["check"], x["severity"]) for x in f] == [("silent-bumper", "UPDATE")]


def test_loudness_jump_over_three_lu_blocks_and_silent_tracks_are_ignored():
    assert sound.loudness_jumps({"intro": -70.0, "card": -70.0, "content": -16.0, "outro": -70.0}) == []
    assert sound.loudness_jumps({"intro": -20.0, "content": -16.0})[0]["severity"] == "BLOCKER"
    assert sound.loudness_jumps({"intro": -17.0, "content": -16.0}) == []


def test_catalog_aliases_find_the_renamed_folders(tmp_path):
    renders = tmp_path / "renders" / "scripthammer-auth-and-payments"
    renders.mkdir(parents=True)
    for k in catalog.KINDS:
        (renders / f"{k}-20260301.mp4").write_bytes(b"x")
    reg = {"episodes": [{"id": "a", "templateFile": "episodes/auth.md", "renderedAt": "2026-03-01",
                         "videoFile": "renders/scripthammer-auth-payments/content-20260301.mp4", "durationSec": 600, "sections": 5}]}
    (tmp_path / "episodes.json").write_text(json.dumps(reg))
    eps = catalog.episodes(tmp_path)
    assert eps[0]["episode"] == "scripthammer-auth-and-payments" and all(eps[0]["segments"].values())


def test_catalog_takes_the_newest_render_of_a_script(tmp_path):
    f = tmp_path / "renders" / "s" / "e"
    f.mkdir(parents=True)
    for d in ("20260101", "20260301"):
        for k in catalog.KINDS:
            (f / f"{k}-{d}.mp4").write_bytes(b"x")
    reg = {"episodes": [
        {"id": "old", "templateFile": "episodes/e.md", "renderedAt": "2026-01-01", "videoFile": "renders/s/e/content-20260101.mp4", "durationSec": 1, "sections": 1},
        {"id": "new", "templateFile": "episodes/e.md", "renderedAt": "2026-03-01", "videoFile": "renders/s/e/content-20260301.mp4", "durationSec": 2, "sections": 1}]}
    (tmp_path / "episodes.json").write_text(json.dumps(reg))
    eps = catalog.episodes(tmp_path)
    assert len(eps) == 1 and eps[0]["registry_id"] == "new" and eps[0]["segments"]["content"].endswith("content-20260301.mp4")
