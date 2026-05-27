#!/usr/bin/env bash
# Download best available audio from a URL, transcode to 320 kbps MP3.
# Usage: download_audio.sh <URL> <OUTPUT_DIR> <ARTIST - TITLE>
#
# Prints JSON to stdout: { status, output_path, source_bitrate_kbps, source_codec }
# Non-zero exit on failure; error message on stderr.

set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <URL> <OUTPUT_DIR> <ARTIST - TITLE>" >&2
  exit 2
fi

URL="$1"
OUT_DIR="$2"
NAME="$3"

command -v yt-dlp >/dev/null 2>&1 || { echo "yt-dlp not installed (brew install yt-dlp)" >&2; exit 3; }
command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg not installed (brew install ffmpeg)" >&2; exit 3; }
command -v ffprobe >/dev/null 2>&1 || { echo "ffprobe not installed" >&2; exit 3; }

mkdir -p "$OUT_DIR"

# Sanitize filename
SAFE_NAME="$(echo "$NAME" | tr '/' '-' | tr -d '\000-\037')"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Download best audio to a temp file
RAW_FILE="$TMP_DIR/raw"
yt-dlp \
  --no-playlist \
  --quiet --no-warnings \
  -f 'bestaudio/best' \
  -o "$RAW_FILE.%(ext)s" \
  "$URL" >&2

# Find the actual file yt-dlp wrote
ACTUAL_RAW="$(ls "$TMP_DIR"/raw.* | head -n1)"
if [[ -z "$ACTUAL_RAW" || ! -f "$ACTUAL_RAW" ]]; then
  echo "yt-dlp did not produce a file" >&2
  exit 4
fi

# Probe source
PROBE_JSON="$(ffprobe -v error -print_format json -show_streams -show_format "$ACTUAL_RAW")"
SRC_BITRATE_BPS="$(echo "$PROBE_JSON" | python3 -c 'import sys,json;d=json.load(sys.stdin);s=[x for x in d.get("streams",[]) if x.get("codec_type")=="audio"];print(s[0].get("bit_rate") or d.get("format",{}).get("bit_rate") or "")' 2>/dev/null || echo "")"
SRC_CODEC="$(echo "$PROBE_JSON" | python3 -c 'import sys,json;d=json.load(sys.stdin);s=[x for x in d.get("streams",[]) if x.get("codec_type")=="audio"];print(s[0].get("codec_name",""))' 2>/dev/null || echo "")"

if [[ -n "$SRC_BITRATE_BPS" ]]; then
  SRC_BITRATE_KBPS=$(( SRC_BITRATE_BPS / 1000 ))
else
  SRC_BITRATE_KBPS=0
fi

# Transcode to 320 MP3 with metadata
OUT_FILE="$OUT_DIR/$SAFE_NAME.mp3"
ARTIST="${NAME% - *}"
TITLE="${NAME#* - }"

ffmpeg -y -hide_banner -loglevel error \
  -i "$ACTUAL_RAW" \
  -codec:a libmp3lame -b:a 320k \
  -metadata "artist=$ARTIST" \
  -metadata "title=$TITLE" \
  "$OUT_FILE" >&2

# Output result. Pass strings via argv (env-safe: handles apostrophes, quotes, etc.)
python3 - "$OUT_FILE" "$SRC_CODEC" "$SRC_BITRATE_KBPS" <<'PY'
import json, sys
out_file, codec, bitrate = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({
  "status": "downloaded",
  "output_path": out_file,
  "source_bitrate_kbps": int(bitrate or 0),
  "source_codec": codec,
  "transcoded_to_kbps": 320,
}, indent=2))
PY
