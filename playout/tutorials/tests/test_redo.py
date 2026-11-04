from types import SimpleNamespace

from playout.tutorials import redo


def test_intro_text_names_title_sections_and_minutes():
    t = redo.intro_text("Multi-Agent Orchestration", 8, 30)
    assert t.startswith("Welcome to Multi-Agent Orchestration on ScriptHammer!")
    assert "8 sections over about 30 minutes" in t


def test_frames_add_the_fades_to_the_speech():
    assert redo.frames_for(10.0) == 300 + redo.FADES
    assert redo.frames_for(10.01) == 301 + redo.FADES


def test_render_script_skips_finished_files_and_names_each_composition():
    s = redo.render_script([("StreamIntro", "intro"), ("NarratedSegment", "s1")])
    assert s.startswith("set -e")
    assert "[ -s /work/intro.mp4 ] || npx remotion render src/index.ts StreamIntro /work/intro.mp4" in s
    assert "NarratedSegment /work/s1.mp4 --props=/work/props_s1.json" in s


def test_concat_filter_joins_all_and_normalises_after():
    f = redo.concat_filter(3)
    assert f.startswith("[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a_raw];")
    assert f.endswith("[a_raw]loudnorm=I=-16:TP=-1.5:LRA=11[a]")


def test_section_props_use_the_real_timings():
    parse = SimpleNamespace(parse_bullet_parts=lambda b: {"text": b})
    sec = SimpleNamespace(title="T", number=2, bullets=["a", "b"], code_block=None, code_language=None)
    p = redo.section_props(sec, 8, 12.0, [5, 90], parse)
    assert p["sectionNumber"] == 2 and p["totalSections"] == 8
    assert p["bulletTimings"] == [5, 90]
    assert p["durationInFrames"] == 360 + redo.FADES
    assert p["codeColumnWidth"] == 0
