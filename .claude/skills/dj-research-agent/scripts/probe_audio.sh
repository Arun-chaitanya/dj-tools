#!/usr/bin/env bash
# Probe an audio file for tags + bitrate. Output: JSON to stdout.
# Usage: probe_audio.sh <FILE>

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <FILE>" >&2
  exit 2
fi

FILE="$1"
[[ -f "$FILE" ]] || { echo "File not found: $FILE" >&2; exit 3; }

command -v ffprobe >/dev/null 2>&1 || { echo "ffprobe not installed (brew install ffmpeg)" >&2; exit 3; }

export PROBE_FILE="$FILE"
ffprobe -v error -print_format json -show_format -show_streams "$FILE" \
  | python3 -c '
import json, sys, os
d = json.load(sys.stdin)
streams = [s for s in d.get("streams", []) if s.get("codec_type") == "audio"]
audio = streams[0] if streams else {}
fmt = d.get("format", {})
tags = fmt.get("tags", {}) or {}
tags_lower = {k.lower(): v for k, v in tags.items()}
br = audio.get("bit_rate") or fmt.get("bit_rate") or ""
print(json.dumps({
  "file": os.path.abspath(os.environ["PROBE_FILE"]),
  "codec": audio.get("codec_name", ""),
  "bit_rate_kbps": int(br) // 1000 if br else 0,
  "sample_rate_hz": int(audio.get("sample_rate", 0)) if audio.get("sample_rate") else 0,
  "channels": audio.get("channels", 0),
  "duration_sec": float(fmt.get("duration", 0)),
  "tags": {
    "artist": tags_lower.get("artist", ""),
    "title": tags_lower.get("title", ""),
    "album": tags_lower.get("album", ""),
    "genre": tags_lower.get("genre", ""),
  },
}, indent=2))
'
