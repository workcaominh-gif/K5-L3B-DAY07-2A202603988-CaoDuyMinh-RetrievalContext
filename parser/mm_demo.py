"""Make test queries for every input mode and run them through mm_search.ask; saves results to <work>/queries/results.json.

    python parser/mm_demo.py <work_dir>

Generated inputs (in <work>/queries/, honest stand-ins for a real user's phone):
  voice_q1.wav   macOS `say` speaking a question (voice search -> STT -> hybrid text search)
  photo_p056.jpg page 56 dish photo, cropped 70 %, rotated 7°, darker, JPEG q=40 (image search)
  frame_crop.jpg a cropped, blurred video keyframe (image -> video timestamp)
  clip_*.wav     5 s cut from a video + white noise at 5 dB SNR (Shazam-style fingerprint)
  hum_*.wav      SYNTHETIC hum: the pitch contour of 8 s of video audio, re-sung as a sine tone transposed +3 semitones
                 and 10 % slower (tests key/tempo invariance; a real human hum is a harder, untested case)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audio_search as A  # noqa: E402
import mm_search as M  # noqa: E402

RAW = Path("/Volumes/T7 Dev/AI20K/day7/raw/video")


def wav(path: Path, y: np.ndarray, sr: int) -> None:
    import soundfile as sf
    sf.write(path, y, sr)


def make(work: Path) -> list[dict]:
    q = work / "queries"
    q.mkdir(exist_ok=True)
    cases = []
    subprocess.run(["say", "-o", str(q / "voice_q1.aiff"), "How much brown rice do I need for fifty servings of porcupine sliders?"], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(q / "voice_q1.aiff"), "-ar", "16000", str(q / "voice_q1.wav")], check=True)
    cases.append({"input": "voice_q1.wav", "expect": "cookbook p.12 brown rice 9 ½ oz / 1 ½ cups"})
    im = Image.open(work / "pages" / "p056.png").convert("RGB")
    w, h = im.size
    im = im.crop((int(w * .2), int(h * .1), int(w * .9), int(h * .8))).rotate(7, expand=True, fillcolor=(40, 30, 20))
    ImageEnhance.Brightness(im).enhance(0.8).save(q / "photo_p056.jpg", quality=40)
    cases.append({"input": "photo_p056.jpg", "expect": "cookbook p.56 (Central Valley Harvest Bake photo)"})
    fr = Image.open(work / "video" / "QhkDOr6kmi4" / "frames" / "f_013.jpg").convert("RGB")
    fw, fh = fr.size
    fr.crop((0, int(fh * .3), int(fw * .8), fh)).filter(ImageFilter.GaussianBlur(2)).save(q / "frame_crop.jpg", quality=50)
    cases.append({"input": "frame_crop.jpg", "expect": "yt:QhkDOr6kmi4 frame f_013 (~0:21, pre-heat oven to 400 °F)"})
    rng = np.random.default_rng(3)
    for vid, s in (("eSKtPtW0X2o", 192.0), ("QhkDOr6kmi4", 61.0)):
        y = A.load(RAW / f"{vid}.mp4", sr=16000, start=s, dur=5)
        y = y + rng.normal(0, np.sqrt(np.mean(y ** 2) / 10 ** 0.5), len(y)).astype(np.float32)
        wav(q / f"clip_{vid}.wav", y, 16000)
        cases.append({"input": f"clip_{vid}.wav", "expect": f"yt:{vid} @ {s:.0f}s"})
    import librosa
    for vid, s in (("eSKtPtW0X2o", 20.0), ("QhkDOr6kmi4", 30.0)):
        y = A.load(RAW / f"{vid}.mp4", sr=16000, start=s, dur=8)
        f0, v, _ = librosa.pyin(y, fmin=65, fmax=1000, sr=16000, frame_length=2048, hop_length=512)
        f0 = np.where(v, f0, np.nan) * 2 ** (3 / 12)                       # +3 semitones
        f0 = np.interp(np.linspace(0, len(f0) - 1, int(len(f0) * 1.1)), np.arange(len(f0)), f0)   # 10 % slower
        hz = np.repeat(np.nan_to_num(f0), 512)
        tone = 0.3 * np.sin(2 * np.pi * np.cumsum(hz) / 16000) * (hz > 0)
        wav(q / f"hum_{vid}.wav", tone.astype(np.float32), 16000)
        cases.append({"input": f"hum_{vid}.wav", "expect": f"yt:{vid} near {s + 8:.0f}s (end of hummed part)", "hum": True})
    return cases


def main(work: Path) -> None:
    cases = make(work)
    out = []
    for c in cases:
        r = M.ask(work, str(work / "queries" / c["input"]), hum=c.get("hum", False))
        out.append({**c, "result": r})
        top = (r.get("hits") or [r.get("match")])[0] if (r.get("hits") or r.get("match")) else None
        print(f"\n== {c['input']}  [{r['mode']}]  expect: {c['expect']}")
        if r.get("transcript"):
            print("   transcript:", r["transcript"])
        print("   top:", json.dumps(top, ensure_ascii=False, default=str)[:260])
    text_q = "photo of a wrap cut in half with purple cabbage"
    r = M.ask(work, text_q)
    out.append({"input": text_q, "expect": "Purple Power Bean Wrap photo page", "result": r})
    print(f"\n== text->image: {text_q}\n   image top:", json.dumps(r["image_hits"][0], ensure_ascii=False)[:200])
    (work / "queries" / "results.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
