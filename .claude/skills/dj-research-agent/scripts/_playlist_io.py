"""Shared playlist + library-snapshot IO for the dj-playlists scripts.

Not a CLI on its own — imported by playlist_list.py, playlist_show.py, etc.

Layout it assumes (anchored at repo root):
    playlists/
        _library.json         ← rekordbox snapshot, keyed by track_id
        <slug>/playlist.json  ← one folder per playable playlist
"""

from __future__ import annotations

import json
import os
import re
from typing import Any


def repo_root() -> str:
    """The dj-tools repo root, inferred from this file's location."""
    here = os.path.dirname(os.path.abspath(__file__))
    # scripts/ -> dj-playlists/ -> skills/ -> .claude/ -> repo root
    return os.path.abspath(os.path.join(here, "..", "..", "..", ".."))


def playlists_dir() -> str:
    return os.path.join(repo_root(), "playlists")


def playlist_path(slug: str) -> str:
    return os.path.join(playlists_dir(), slug, "playlist.json")


def library_path() -> str:
    return os.path.join(playlists_dir(), "_library.json")


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def validate_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"slug {slug!r} must be lowercase ASCII, kebab-case "
            "(letters/digits/hyphens, no leading/trailing hyphen)"
        )


def load_library() -> dict[str, Any] | None:
    """Return the parsed _library.json, or None if it doesn't exist."""
    p = library_path()
    if not os.path.isfile(p):
        return None
    with open(p) as f:
        return json.load(f)


def load_playlist(slug: str) -> dict[str, Any]:
    p = playlist_path(slug)
    if not os.path.isfile(p):
        raise FileNotFoundError(f"no playlist at {p}")
    with open(p) as f:
        return json.load(f)


def write_playlist(slug: str, data: dict[str, Any]) -> None:
    p = playlist_path(slug)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    # Re-pack sequences to 1..N before write (in case caller forgot).
    if "tracks" in data:
        data["tracks"].sort(key=lambda t: t.get("sequence", 0))
        for i, t in enumerate(data["tracks"], start=1):
            t["sequence"] = i
    with open(p, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def list_playlists() -> list[dict[str, Any]]:
    """Return playlist metadata for every playlists/<slug>/playlist.json."""
    out = []
    d = playlists_dir()
    if not os.path.isdir(d):
        return out
    for entry in sorted(os.listdir(d)):
        if entry.startswith("_") or entry.startswith("."):
            continue
        p = os.path.join(d, entry, "playlist.json")
        if not os.path.isfile(p):
            continue
        try:
            with open(p) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        meta = dict(data.get("playlist") or {})
        meta["slug"] = entry
        meta["track_count"] = len(data.get("tracks") or [])
        out.append(meta)
    # Most recent first by created date string (lexicographic on ISO dates is correct).
    out.sort(key=lambda m: m.get("created", ""), reverse=True)
    return out


def resolve_track(library: dict[str, Any] | None, track_id: str) -> dict[str, Any] | None:
    """Return the library entry for a track_id, or None if unknown."""
    if not library:
        return None
    return (library.get("tracks") or {}).get(str(track_id))


def assert_track_in_library(library: dict[str, Any] | None, track_id: str) -> None:
    """Raise ValueError if the track isn't in the library snapshot."""
    if library is None:
        raise ValueError(
            f"no playlists/_library.json snapshot found. "
            "Run snapshot_library.py first (see dj-research-agent skill)."
        )
    if resolve_track(library, track_id) is None:
        raise ValueError(
            f"track_id {track_id!r} not in library snapshot. "
            "Either the ID is wrong, or the snapshot is stale "
            "(re-run snapshot_library.py)."
        )
