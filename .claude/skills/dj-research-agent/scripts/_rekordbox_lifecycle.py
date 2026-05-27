"""Helpers for safely closing and reopening rekordbox around a DB write.

Used by set_cue.py and bulk_cue_from_json.py. Not a CLI on its own.

Public API:
  - is_running() -> bool
  - graceful_quit(timeout_sec=20) -> tuple[bool, str]
      Returns (success, reason). On success, rekordbox is no longer running.
  - reopen() -> tuple[bool, str]
      Launches rekordbox in the background. Doesn't wait for it to finish loading.
"""

from __future__ import annotations

import subprocess
import time


def is_running() -> bool:
    try:
        r = subprocess.run(["pgrep", "-x", "rekordbox"],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def graceful_quit(timeout_sec: int = 20) -> tuple[bool, str]:
    """Ask rekordbox to quit gracefully, wait for the process to exit.

    Returns (True, "...") if rekordbox is no longer running after timeout_sec.
    Returns (False, reason) if it's still running — typically because a
    save-dialog (or unsaved-changes prompt) is blocking the quit.
    """
    if not is_running():
        return True, "already not running"

    try:
        subprocess.run(
            ["osascript", "-e", 'tell application "rekordbox" to quit'],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.SubprocessError as e:
        return False, f"osascript failed: {e}"

    # Poll for process exit
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not is_running():
            return True, "quit ok"
        time.sleep(0.5)

    return False, (
        f"rekordbox still running after {timeout_sec}s. "
        "It may be showing a save-changes dialog. "
        "Please save / discard manually and re-run."
    )


def reopen() -> tuple[bool, str]:
    """Launch rekordbox in the background. Does NOT wait for it to be ready."""
    try:
        subprocess.Popen(
            ["open", "-a", "rekordbox"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return True, "launched"
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        return False, f"open failed: {e}"
