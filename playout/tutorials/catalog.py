"""List the latest render of every tutorial episode, with its four segments (intro, card, content, outro).

Read-only on ~/clawd-twitch. The registry (episodes.json) holds one entry per render; the newest entry per script is the
latest. Three scripts were renamed after they were rendered, so their registry path is dead while the files live under
the new folder name (ALIASES). The newest file of each kind in the episode folder is the segment that airs.
"""
import json
import re
from pathlib import Path

CLAWD = Path.home() / "clawd-twitch"
KINDS = ("intro", "card", "content", "outro")

# registry folder -> the folder the files were renamed to (checked by hand against the dates of the files)
ALIASES = {
    "scripthammer-auth-payments": "scripthammer-auth-and-payments",
    "scripthammer-testing-deploy": "scripthammer-testing-and-deploy",
    "scripthammer-build-a-next-js-app-from-template": "scripthammer-walkthrough",
}


def _newest(folder, kind):
    best = None
    for p in folder.glob(f"{kind}-*.mp4"):
        m = re.fullmatch(rf"{kind}-(\d{{8}})(?:-\d+)?\.mp4", p.name)
        if m and (best is None or p.name > best.name):
            best = p
    return best


def episodes(root=CLAWD):
    reg = json.loads((root / "episodes.json").read_text())["episodes"]
    latest = {}
    for e in reg:
        k = e["templateFile"]
        if k not in latest or e["renderedAt"] > latest[k]["renderedAt"]:
            latest[k] = e
    out = []
    for script, e in sorted(latest.items()):
        folder = (root / e["videoFile"]).parent
        series, ep = folder.parent.name, folder.name
        if series == "renders":
            series = ep  # the episode sits straight under renders/
        aliased = None
        if not folder.exists() and ep in ALIASES:
            aliased = ep
            ep = ALIASES[ep]
            folder = root / "renders" / ep
            series = ep  # these live straight under renders/
        segs = {}
        for kind in KINDS:
            p = _newest(folder, kind) if folder.exists() else None
            segs[kind] = str(p) if p else None
        out.append({
            "script": script, "script_path": str(root / script), "series": series, "episode": ep,
            "registry_id": e["id"], "registered_seconds": e["durationSec"], "registered_sections": e["sections"],
            "rendered_at": e["renderedAt"], "aliased_from": aliased, "segments": segs,
        })
    return out


def script_title(script_path):
    """First heading of the episode script, or None."""
    try:
        for line in Path(script_path).read_text().splitlines():
            if line.startswith("#"):
                return line.lstrip("#").strip()
    except OSError:
        pass
    return None


if __name__ == "__main__":
    eps = episodes()
    miss = [(e["episode"], k) for e in eps for k, v in e["segments"].items() if not v]
    print(len(eps), "episodes;", len({e["series"] for e in eps}), "series; missing segments:", miss)
