"""rotate_pid.py and the pid guard in air-rotation.sh: a stale rotate.pid (after a reboot its number can belong to any process)
must not stop the rotation from starting; a running rotate.py must."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from playout.tutorials import rotate_pid  # noqa: E402


def sleeper(*words):
    """A live child process with `words` among its arguments, so a rotate.py-like name can be faked without the real sender."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", *words])


def stop(*procs):
    for p in procs:
        p.kill()
        p.wait()


def test_only_a_running_rotate_py_keeps_the_pid_file(tmp_path):
    pf = tmp_path / "rotate.pid"
    other = sleeper("not-the-sender")
    rot = sleeper("/x/playout/tutorials/rotate.py", "list.json")
    try:
        pf.write_text(f"{rot.pid}\n")
        assert rotate_pid.check(str(pf)) == 0 and pf.exists()          # a real rotate.py: keep the file
        pf.write_text(f"{other.pid}\n")
        assert rotate_pid.check(str(pf)) == 1 and not pf.exists()      # alive but unrelated: stale, removed
    finally:
        stop(rot, other)


def test_dead_missing_and_garbage_pids_are_stale(tmp_path):
    dead = sleeper()
    stop(dead)
    pf = tmp_path / "rotate.pid"
    for text in (f"{dead.pid}\n", "", "abc\n", "0\n", "-5\n"):
        pf.write_text(text)
        assert rotate_pid.check(str(pf)) == 1 and not pf.exists()
    assert rotate_pid.check(str(tmp_path / "nothing.pid")) == 1        # no file: nothing to remove, not an error


def test_name_must_be_a_whole_word():
    p = sleeper("my-rotate.py.bak", "xrotate.py")
    try:
        assert rotate_pid.is_rotate(p.pid) is False
    finally:
        stop(p)


def run_air_rotation(tmp_path, pid):
    """Runs the real script as far as just past the pid guard: the key file is missing, so it ends at exit 5 before Docker."""
    air = tmp_path / "air"
    air.mkdir(parents=True)
    (air / "list.json").write_text('{"items": []}')
    (air / "rotate.pid").write_text(f"{pid}\n")
    env = {**os.environ, "AIR_DIR": str(air), "AIR_KEYFILE": str(tmp_path / "no-such.key")}
    r = subprocess.run(["bash", str(ROOT / "playout/tutorials/air-rotation.sh")], env=env, capture_output=True, text=True, timeout=60)
    return r, air / "rotate.pid"


def test_air_rotation_ignores_a_stale_pid_and_refuses_a_running_rotate(tmp_path):
    other = sleeper("not-the-sender")
    rot = sleeper("rotate.py")
    try:
        r, pf = run_air_rotation(tmp_path / "stale", other.pid)
        assert r.returncode == 5 and "already on air" not in r.stdout   # past the guard (ended at the missing key file)
        assert not pf.exists()                                            # and the stale file is gone
        r, pf = run_air_rotation(tmp_path / "live", rot.pid)
        assert r.returncode == 4 and "already on air" in r.stdout and pf.exists()
    finally:
        stop(rot, other)
