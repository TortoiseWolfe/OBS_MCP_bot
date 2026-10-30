import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import prerecord as pr

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _img(path, size=(300, 400), colour=(90, 60, 30)):
    Image.new("RGB", size, colour).save(path)
    return path


def make_story(tmp_path):
    """Two songs: song 1 has a card, a lyric card and a comic page; song 2 is held (Corps rule) and has a card, a lyric card and portraits."""
    art = tmp_path / "art"
    art.mkdir()
    pages = tmp_path / "pages"
    pages.mkdir()
    port = tmp_path / "portraits"
    port.mkdir()
    for n in ("Nell", "Verse", "Form"):
        _img(port / f"portrait-{n}.png")
    _img(port / "ref-verse_ref.png")
    _img(art / "one-card.jpg")
    _img(art / "one-lyrics-1.jpg")
    _img(art / "two-card.jpg")
    _img(art / "two-lyrics-1.jpg")
    _img(pages / "page01.png", (400, 1200))
    (tmp_path / "pages.json").write_text(json.dumps({"pages": [{"page": 1, "track": 1}]}))
    (art / "track-cards.json").write_text(json.dumps({
        "one": ["one-card.jpg", "one-lyrics-1.jpg"],
        "two": ["two-card.jpg", "two-lyrics-1.jpg"],
    }))
    cfg = {"track_cards": str(art / "track-cards.json"), "font": FONT}
    story = {
        "join_seconds": 8, "picture_fade": 4.0,
        "portraits": str(port), "pages": str(tmp_path / "pages.json"), "pages_dir": str(pages),
        "opening": {"lines": ["THE BAND WAGON", "Replay", "A line"], "seconds": 10},
        "ending": {"lines": ["Thanks", "scripthammer.com"], "seconds": 20},
        "songs": [
            {"n": 1, "id": "one", "title": "One", "start": 0, "label": "Nell is 9 - 1848", "comic_track": 1, "singers": ["Nell", "Verse"],
             "chapter": {"at": 12, "head": "ACT ONE", "sub": "Nell is 9", "log": "Log, entry one."}},
            {"n": 2, "id": "two", "title": "Two", "start": 100, "held": True, "singers": ["Verse"]},
        ],
    }
    return story, cfg


def test_smooth_is_clamped_and_symmetric():
    assert pr.smooth(-1) == 0.0
    assert pr.smooth(2) == 1.0
    assert pr.smooth(0.5) == 0.5
    assert abs(pr.smooth(0.25) + pr.smooth(0.75) - 1.0) < 1e-9


def test_bounds_sum_to_song_length(tmp_path):
    story, cfg = make_story(tmp_path)
    plan = pr.build_plan(story, cfg, 200.0)
    one, two = plan["songs"]
    assert one["end"] == 108.0  # song 2 starts at 100 and the join reaches back 8 s into song 1
    assert abs(one["bounds"][-1] - 108.0) < 1e-6
    assert two["end"] == 200.0
    assert abs(two["bounds"][-1] - 100.0) < 1e-6
    assert all(a < b for a, b in zip(one["bounds"], one["bounds"][1:]))


def test_no_comic_page_appears_when_comic_is_off_or_the_page_is_excluded(tmp_path):
    story, cfg = make_story(tmp_path)
    assert any(x["kind"] == "page" for x in pr.build_plan(story, cfg, 200.0)["songs"][0]["items"])
    story["exclude_pages"] = [1]
    assert not any(x["kind"] == "page" for s in pr.build_plan(story, cfg, 200.0)["songs"] for x in s["items"])
    story["exclude_pages"], story["comic"] = [], False
    assert not any(x["kind"] == "page" for s in pr.build_plan(story, cfg, 200.0)["songs"] for x in s["items"])


def test_held_songs_show_no_card_or_page(tmp_path):
    story, cfg = make_story(tmp_path)
    plan = pr.build_plan(story, cfg, 200.0)
    one, two = plan["songs"]
    assert {"card", "page"} <= {x["kind"] for x in one["items"]}
    kinds = {x["kind"] for x in two["items"]}
    assert "lyrics" in kinds and not kinds & {"card", "page"}
    assert not any("two-card" in str(x["path"]) for x in two["items"])


def test_no_picture_stays_up_past_the_limit(tmp_path):
    story, cfg = make_story(tmp_path)
    plan = pr.build_plan(story, cfg, 400.0)  # song 2 is 300 s long: the pool is shown, then goes round again
    two = plan["songs"][1]
    lo = 0.0
    for x, hi in zip(two["items"], two["bounds"]):
        if x["kind"] != "slide":  # a slide is text, not a picture, and is held for its reading time
            assert (hi - lo) <= pr.UNIT_MAX * x["w"] + 1e-6
        lo = hi


def test_opening_chapter_and_end_are_screens_in_the_rotation(tmp_path):
    story, cfg = make_story(tmp_path)
    plan = pr.build_plan(story, cfg, 200.0)
    one, two = plan["songs"]
    keys = [x.get("key") for x in one["items"] if x["kind"] == "slide"]
    assert keys == ["open", "ch1"]
    assert [x["kind"] for x in one["items"]][:2] == ["slide", "slide"]  # the film opens on a screen of its own, then the chapter card
    assert [x.get("key") for x in two["items"] if x["kind"] == "slide"] == ["end"]
    assert two["items"][-1]["kind"] == "slide"
    sh = pr.shares_at(plan, 0.0)
    assert sh == {(0, 0): 1.0}  # first frame: one clean screen at full strength
    assert pr.shares_at(plan, 1.0) == {(0, 0): 1.0}


def test_clear_need_and_hold_needs(tmp_path):
    assert pr.clear_need(0) == pr.MIN_CLEAR
    assert pr.clear_need(40) == pr.ORIENT + 40 / pr.READ_WPS
    items = [{"kind": "card", "words": 8}, {"kind": "lyrics", "words": 40}]
    needs = pr.hold_needs(items, False, False, 8.0, 4.0)
    assert needs[1] > needs[0]
    assert needs[1] >= pr.clear_need(40) + (pr.U - 0.5) * 4.0


def test_a_short_song_drops_members_before_lyrics_and_keeps_the_first_page_and_slides(tmp_path):
    mk = lambda kind, words=0, **kw: {"kind": kind, "words": words, "w": 1.0, **kw}
    slide = mk("slide", 12, slide={"head": "A", "sub": "b", "log": "c", "seconds": 0})
    items = [slide, mk("card", 8), mk("lyrics", 30), mk("lyrics", 30), mk("page", 15), mk("member")]
    kept, needs, dropped = pr.fit_items(list(items), 40.0, False, False, 8.0, 4.0)
    assert sum(needs) <= 40.0 or len(kept) <= 2
    assert items[0] in kept and items[2] in kept
    assert [x["kind"] for x in dropped][0] == "member"
    assert "lyrics" not in [x["kind"] for x in dropped][:3]


def test_measure_flags_a_fade_that_is_too_short(tmp_path):
    story, cfg = make_story(tmp_path)
    ok = pr.build_plan(story, cfg, 200.0)
    short, fades = pr.readability(pr.measure(ok), ok["total"])
    assert fades == []
    story["picture_fade"] = 1.0
    bad = pr.build_plan(story, cfg, 200.0)
    short, fades = pr.readability(pr.measure(bad), bad["total"])
    assert fades  # a 1 s dissolve into a screen with words is reported


def test_frames_are_720p_and_the_band_dips_at_a_join(tmp_path):
    story, cfg = make_story(tmp_path)
    plan = pr.build_plan(story, cfg, 200.0)
    r = pr.Renderer(plan, FONT)
    for t in (3.0, 50.0, 100.0, 104.0, 108.5, 150.0, 199.5):
        assert r.frame_at(t).size == (pr.W, pr.H)
    # halfway through the join both band texts have faded out: the band is black
    mid = r.frame_at(104.0).crop((0, pr.PH, pr.W, pr.H))
    assert mid.getextrema() == ((0, 0), (0, 0), (0, 0))
    assert r.frame_at(150.0).crop((0, pr.PH, pr.W, pr.H)).getextrema()[0][1] > 200  # the new band text is white
    assert r.frame_at(199.9).getextrema()[0][1] < 30  # the film ends on black


def test_band_text_keeps_the_graphics_safe_margins(tmp_path):
    story, cfg = make_story(tmp_path)
    plan = pr.build_plan(story, cfg, 200.0)
    r = pr.Renderer(plan, FONT)
    for t in (50.0, 150.0):
        band = r.frame_at(t).crop((0, pr.PH, pr.W, pr.H)).convert("L").point(lambda v: 255 if v > 200 else 0)
        x0, y0, x1, y1 = band.getbbox()  # the white band text (right and bottom edges are one past the last pixel)
        assert pr.H - (pr.PH + y1) >= 36  # lowest text pixel at least 36 px above the frame's bottom (5% of 720)
        assert x0 >= 64 and pr.W - x1 >= 64


def test_clips_join_the_rotation_and_play_through_their_slot(tmp_path):
    story, cfg = make_story(tmp_path)
    vis = tmp_path / "vis"
    vis.mkdir()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=160x90:r=10:d=3", "-pix_fmt", "yuv420p",
                    str(vis / "vz-turntable-x.mp4")], check=True)
    story["visuals"] = str(vis)
    story["songs"][0]["clips"] = ["turntable-x", "turntable-missing"]  # a file that is not there is skipped
    plan = pr.build_plan(story, cfg, 200.0)
    clips = [x for x in plan["songs"][0]["items"] if x["kind"] == "clip"]
    assert len(clips) == 1 and clips[0]["loop"] and abs(clips[0]["dur"] - 3.0) < 0.2
    assert all("span" in x for s in plan["songs"] for x in s["items"])
    pr.extract_clips(plan, tmp_path / "out")
    assert clips[0]["count"] >= 55  # 3 s at 20 frames a second
    r = pr.Renderer(plan, FONT)
    lo = plan["songs"][0]["bounds"][[x["kind"] for x in plan["songs"][0]["items"]].index("clip") - 1]
    assert r.frame_at(lo + 5.0).size == (pr.W, pr.H)


def test_video_cards_replace_square_cards_in_order(tmp_path):
    sq = [tmp_path / n for n in ("a-card.jpg", "a-lyrics.jpg", "a-lyrics-2.jpg")]
    vd = tmp_path / "video"
    vd.mkdir()
    for n in ("a-card-video.jpg", "a-lyrics-video.jpg", "a-lyrics-video-2.jpg", "a-lyrics-video-10.jpg"):
        (vd / n).write_bytes(b"x")
    out, used = pr.video_cards(sq, str(vd))
    assert used
    assert [p.name for p in out] == ["a-card-video.jpg", "a-lyrics-video.jpg", "a-lyrics-video-2.jpg", "a-lyrics-video-10.jpg"]


def test_video_cards_fall_back_to_square_cards(tmp_path):
    sq = [tmp_path / "a-card.jpg"]
    assert pr.video_cards(sq, None) == (sq, False)
    assert pr.video_cards(sq, str(tmp_path / "missing")) == (sq, False)
    empty = tmp_path / "video"
    empty.mkdir()
    assert pr.video_cards(sq, str(empty)) == (sq, False)
