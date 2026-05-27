#!/usr/bin/env python3
"""Bulk-download tracks from a mix's tracklist.json into a DJ-Music subfolder.

Parallel: N workers shelling out to download_audio.sh. Resume-safe: skips files
already on disk (matched by sanitized filename).

Usage:
    python3 bulk_download.py --mix <MIX_ID> --out-dir <PATH> [--min-views N] [--workers N]

Examples:
    python3 bulk_download.py --mix dhh-research-v1 --out-dir ~/Desktop/DJ-Music/DHH --min-views 500000
    python3 bulk_download.py --mix telugu-9xm-feels-v1 --out-dir ~/Desktop/DJ-Music/Telugu

Manifest + log written to mixes/<mix-id>/bulk-download-manifest.json and bulk-download.log.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS_DIR.parents[3]
DOWNLOAD_SH = SCRIPTS_DIR / "download_audio.sh"


def safe(part: str) -> str:
    part = part.replace("/", "-")
    part = re.sub(r"[\x00-\x1f]", "", part)
    return part.strip()


def short_title(t: dict) -> str:
    yt = t.get("youtube_title") or t.get("title") or ""
    yt = re.sub(r"\s*\(Official.*?\)\s*", " ", yt, flags=re.IGNORECASE)
    yt = re.sub(r"\s*\[Official.*?\]\s*", " ", yt, flags=re.IGNORECASE)
    yt = re.sub(r"\s+", " ", yt).strip()
    return yt[:120]


class Runner:
    def __init__(self, mix_id: str, out_dir: Path, min_views: int, workers: int):
        self.mix_id = mix_id
        self.mix_dir = REPO_ROOT / "mixes" / mix_id
        self.tracklist_path = self.mix_dir / "tracklist.json"
        self.out_dir = out_dir
        self.min_views = min_views
        self.workers = workers
        self.manifest_path = self.mix_dir / "bulk-download-manifest.json"
        self.log_path = self.mix_dir / "bulk-download.log"
        self.lock = threading.Lock()
        self.log_lock = threading.Lock()
        self.results: list[dict] = []
        self.started: float = 0.0

    def log(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        with self.log_lock:
            print(line, flush=True)
            with self.log_path.open("a") as f:
                f.write(line + "\n")

    def write_manifest(self, total_work: int) -> None:
        snap = {
            "mix_id": self.mix_id,
            "out_dir": str(self.out_dir),
            "started": self.started,
            "elapsed_s": round(time.time() - self.started, 1),
            "min_views": self.min_views,
            "total_work": total_work,
            "downloaded": sum(1 for r in self.results if r["status"] == "downloaded"),
            "skipped_existing": sum(1 for r in self.results if r["status"] == "skipped_existing"),
            "failed": sum(1 for r in self.results if r["status"] in ("failed", "timeout")),
            "results": sorted(self.results, key=lambda r: r["rank"]),
        }
        with self.lock:
            self.manifest_path.write_text(json.dumps(snap, indent=2))

    def download_one(self, rank: int, total: int, t: dict) -> dict:
        name = safe(short_title(t))
        url = t["youtube_url"]
        out_file = self.out_dir / f"{name}.mp3"

        if out_file.exists() and out_file.stat().st_size > 500_000:
            self.log(f"[{rank:>4}/{total}] SKIP (on disk) {name[:70]}")
            return {
                "rank": rank, "video_id": t["video_id"], "title": name,
                "view_count": t.get("view_count"), "status": "skipped_existing",
                "output_path": str(out_file),
            }

        vc = t.get("view_count") or 0
        self.log(f"[{rank:>4}/{total}] START  {vc:>11,}  {t['video_id']}  {name[:60]}")
        t_start = time.time()
        try:
            proc = subprocess.run(
                ["bash", str(DOWNLOAD_SH), url, str(self.out_dir), name],
                capture_output=True, text=True, timeout=420,
            )
        except subprocess.TimeoutExpired:
            self.log(f"[{rank:>4}/{total}] TIMEOUT {name[:60]}")
            return {"rank": rank, "video_id": t["video_id"], "title": name,
                    "view_count": vc, "status": "timeout"}

        elapsed = time.time() - t_start
        if proc.returncode != 0:
            err_lines = (proc.stderr or "").strip().splitlines()
            tail = err_lines[-1] if err_lines else "unknown"
            self.log(f"[{rank:>4}/{total}] FAIL ({elapsed:.0f}s) {tail[:80]}  -- {name[:50]}")
            return {"rank": rank, "video_id": t["video_id"], "title": name,
                    "view_count": vc, "status": "failed",
                    "error": tail, "elapsed_s": round(elapsed, 1)}

        try:
            info = json.loads(proc.stdout)
        except json.JSONDecodeError:
            info = {"status": "downloaded"}

        self.log(f"[{rank:>4}/{total}] OK ({elapsed:.0f}s) src={info.get('source_codec')}@{info.get('source_bitrate_kbps')}kbps  {name[:50]}")
        return {
            "rank": rank, "video_id": t["video_id"], "title": name,
            "view_count": vc, "status": "downloaded",
            "output_path": info.get("output_path"),
            "source_bitrate_kbps": info.get("source_bitrate_kbps"),
            "source_codec": info.get("source_codec"),
            "elapsed_s": round(elapsed, 1),
        }

    def run(self) -> int:
        if not self.tracklist_path.exists():
            print(f"tracklist not found: {self.tracklist_path}", file=sys.stderr)
            return 2
        self.out_dir.mkdir(parents=True, exist_ok=True)

        data = json.loads(self.tracklist_path.read_text())
        all_tracks = data["tracks"]
        work = [
            t for t in all_tracks
            if t.get("video_id") and (self.min_views <= 0 or (t.get("view_count") or 0) >= self.min_views)
        ]
        # Stable order: most-viewed first when view_count is present, null treated as 0.
        work.sort(key=lambda t: t.get("view_count") or 0, reverse=True)

        self.started = time.time()
        self.log(f"=== bulk run: mix={self.mix_id}  min_views={self.min_views:,}  workers={self.workers}  total_work={len(work)}  out={self.out_dir} ===")

        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futures = {ex.submit(self.download_one, i, len(work), t): i for i, t in enumerate(work, 1)}
            for fut in as_completed(futures):
                try:
                    r = fut.result()
                except Exception as e:
                    r = {"rank": futures[fut], "status": "failed", "error": f"exception: {e}"}
                self.results.append(r)
                if len(self.results) % 5 == 0 or len(self.results) == len(work):
                    self.write_manifest(len(work))

        self.write_manifest(len(work))
        downloaded = sum(1 for r in self.results if r["status"] == "downloaded")
        skipped = sum(1 for r in self.results if r["status"] == "skipped_existing")
        failed = sum(1 for r in self.results if r["status"] in ("failed", "timeout"))
        elapsed = round(time.time() - self.started, 1)
        self.log(f"=== DONE: {downloaded} downloaded, {skipped} skipped, {failed} failed in {elapsed}s ===")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mix", required=True, help="mix id (folder under mixes/)")
    ap.add_argument("--out-dir", required=True, help="DJ-Music subfolder to download into")
    ap.add_argument("--min-views", type=int, default=0, help="filter tracks below this view count (0 = no filter)")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()

    out_dir = Path(os.path.expanduser(args.out_dir)).resolve()
    return Runner(args.mix, out_dir, args.min_views, args.workers).run()


if __name__ == "__main__":
    sys.exit(main())
