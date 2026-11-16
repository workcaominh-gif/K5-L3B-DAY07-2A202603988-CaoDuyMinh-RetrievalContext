"""Processing for YouTube videos: speech (STT), captions, and on-screen text frames, all with timestamps.

    python parser/video_extract.py <video_dir> <work_dir> <id> [<id> ...]

Per video id writes <work>/video/<id>/:
  stt.json       faster-whisper 'small' segments [{t0, t1, text, avg_logprob}] (local, word timestamps off)
  captions.json  YouTube caption cues if the video has them (en, manual preferred over auto)
  frames/        scene-change keyframes f_###.jpg (ffmpeg select=gt(scene,0.12))
  ocr.json       Apple Vision OCR per frame [{t, frame, lines:[[text, conf]]}] for frames that contain text
  meta.json      title, channel, duration, url, upload date (from yt-dlp info.json)
OCR text is raw: fractions and stylised fonts are verified later by the VLM tier.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np


def vtt(path: Path) -> list[dict]:
    cues, t0, t1 = [], None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"(\d+):(\d+):([\d.]+) --> (\d+):(\d+):([\d.]+)", line)
        if m:
            h, mi, s, h2, mi2, s2 = m.groups()
            t0 = int(h) * 3600 + int(mi) * 60 + float(s)
            t1 = int(h2) * 3600 + int(mi2) * 60 + float(s2)
        elif line.strip() and t0 is not None and not line.startswith(("WEBVTT", "Kind:", "Language:")):
            text = re.sub(r"<[^>]+>", "", line).strip()
            if text and (not cues or cues[-1]["text"] != text):
                cues.append({"t0": round(t0, 2), "t1": round(t1, 2), "text": text})
    return cues


def main(vdir: Path, work: Path, ids: list[str]) -> None:
    from faster_whisper import WhisperModel
    from ocrmac import ocrmac
    model = WhisperModel("small", device="cpu", compute_type="int8")
    for vid in ids:
        out = work / "video" / vid
        (out / "frames").mkdir(parents=True, exist_ok=True)
        info = json.loads((vdir / f"{vid}.info.json").read_text(encoding="utf-8"))
        meta = {k: info.get(k) for k in ("id", "title", "channel", "duration", "upload_date", "webpage_url", "license")}
        (out / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
        mp4 = vdir / f"{vid}.mp4"
        # decode audio with ffmpeg (16 kHz mono float32) and pass samples: avoids PyAV version issues in faster-whisper
        pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                             capture_output=True, check=True).stdout
        segs, _ = model.transcribe(np.frombuffer(pcm, dtype=np.float32), language="en", vad_filter=True)
        stt = [{"t0": round(s.start, 2), "t1": round(s.end, 2), "text": s.text.strip(),
                "avg_logprob": round(s.avg_logprob, 3)} for s in segs]
        (out / "stt.json").write_text(json.dumps(stt, indent=1, ensure_ascii=False), encoding="utf-8")
        subs = sorted(vdir.glob(f"{vid}.en*.vtt"), key=lambda p: ("orig" in p.name, len(p.name)))
        (out / "captions.json").write_text(json.dumps(vtt(subs[0]) if subs else [], indent=1, ensure_ascii=False), encoding="utf-8")
        log = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", str(mp4), "-vf",
                              "select='gt(scene\\,0.12)',showinfo,scale=960:-1", "-fps_mode", "vfr",
                              str(out / "frames" / "f_%03d.jpg")], capture_output=True, text=True).stderr
        times = [float(t) for t in re.findall(r"pts_time:([\d.]+)", log)]
        ocr = []
        for k, t in enumerate(times, 1):
            f = out / "frames" / f"f_{k:03d}.jpg"
            lines = [[x[0], round(x[1], 2)] for x in ocrmac.OCR(str(f), recognition_level="accurate").recognize() if x[1] > 0.5]
            if lines:
                ocr.append({"t": round(t, 2), "frame": f.name, "lines": lines})
        (out / "ocr.json").write_text(json.dumps(ocr, indent=1, ensure_ascii=False), encoding="utf-8")
        print(vid, "stt", len(stt), "captions", len(json.loads((out / 'captions.json').read_text())), "frames", len(times), "text frames", len(ocr))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:])
