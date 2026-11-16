"""Audio query modes for the KB: Shazam-style fingerprinting and humming (melody) search over the ingested videos.

    python parser/audio_search.py build <work_dir> <video_dir>          # index all videos
    python parser/audio_search.py query <work_dir> <clip.wav|mp3|m4a>   # which video + time?
    python parser/audio_search.py hum   <work_dir> <hum.wav>            # melody search
    python parser/audio_search.py eval  <work_dir> <video_dir>          # random clips, clean + noisy

Fingerprint (Wang 2003, the Shazam paper): 8 kHz mono -> STFT (1024/256) -> spectral peaks (local maxima in a
15x15 neighbourhood, above the frame's 80th percentile and within 60 dB of the loudest bin) -> landmark pairs (anchor peak + up to 5 later peaks within
1..64 frames) -> hash (f1, f2, dt). A query votes for (video, t_db - t_query); the tallest histogram bin wins.
Robust to noise and volume because only peak positions are hashed, not magnitudes.

Humming: librosa pYIN pitch (65-1000 Hz, 10 frames/s) -> MIDI semitones -> median filter -> intervals between frames (key-invariant)
-> subsequence DTW of the hum contour against every video's voiced-pitch contour; lowest normalised cost wins.
Speech/music videos have weak melodies, so this mode is reported with its measured accuracy, not assumed.
"""
from __future__ import annotations

import json
import pickle
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter
from scipy.signal import stft

SR, NFFT, HOP = 8000, 1024, 256
FRAME_S = HOP / SR


def load(path: Path, sr: int = SR, start: float | None = None, dur: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-loglevel", "error"] + (["-ss", str(start)] if start is not None else []) + ["-i", str(path)] + \
          (["-t", str(dur)] if dur else []) + ["-f", "f32le", "-ac", "1", "-ar", str(sr), "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32)


def peaks(y: np.ndarray) -> list[tuple[int, int]]:
    _, _, Z = stft(y, fs=SR, nperseg=NFFT, noverlap=NFFT - HOP)
    S = 20 * np.log10(np.abs(Z) + 1e-10)                      # dB: scale-free (volume changes shift all values equally)
    loc = (S == maximum_filter(S, size=15)) & (S > np.percentile(S, 80, axis=0, keepdims=True)) & (S > S.max() - 60)
    f, t = np.nonzero(loc)
    order = np.argsort(t)
    return list(zip(t[order].tolist(), f[order].tolist()))


def hashes(pk: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out = []
    for i, (t1, f1) in enumerate(pk):
        n = 0
        for t2, f2 in pk[i + 1:]:
            dt = t2 - t1
            if dt < 1:
                continue
            if dt > 64 or n >= 5:
                break
            out.append(((f1 << 20) | (f2 << 8) | dt, t1))
            n += 1
    return out


def contour(y: np.ndarray, sr: int) -> np.ndarray:
    import librosa
    f0, voiced, _ = librosa.pyin(y, fmin=65, fmax=1000, sr=sr, frame_length=2048, hop_length=512)
    step = max(1, round(sr / 512 / 10))                       # ~10 contour points per second
    m = librosa.hz_to_midi(np.where(voiced, f0, np.nan))[::step]
    t = np.arange(len(m)) * step * 512 / sr                   # real seconds of each contour point
    keep = ~np.isnan(m)
    m, t = m[keep], t[keep]
    if len(m) < 3:
        return np.zeros((2, 0))
    from scipy.signal import medfilt
    m = medfilt(m, 5)                                         # remove octave jumps / pYIN glitches
    return np.vstack([np.clip(np.diff(m), -12, 12), t[1:]])  # row 0: intervals (key-invariant), row 1: seconds


def build(work: Path, vdir: Path) -> None:
    index, meta, mel = defaultdict(list), {}, {}
    for mp4 in sorted(vdir.glob("*.mp4")):
        vid = mp4.stem
        y = load(mp4)
        hs = hashes(peaks(y))
        for h, t in hs:
            index[h].append((vid, t))
        meta[vid] = {"seconds": round(len(y) / SR, 1), "hashes": len(hs)}
        mel[vid] = contour(load(mp4, sr=16000), 16000)
        print(vid, meta[vid], "melody points", mel[vid].shape[1])
    (work / "audio").mkdir(exist_ok=True)
    with open(work / "audio" / "fp_index.pkl", "wb") as f:
        pickle.dump({"index": dict(index), "meta": meta, "melody": mel}, f)


def _db(work: Path) -> dict:
    with open(work / "audio" / "fp_index.pkl", "rb") as f:
        return pickle.load(f)


def match(db: dict, y: np.ndarray) -> dict:
    votes = Counter()
    for h, tq in hashes(peaks(y)):
        for vid, tdb in db["index"].get(h, ()):
            votes[(vid, tdb - tq)] += 1
    if not votes:
        return {"match": None, "score": 0}
    (vid, off), score = votes.most_common(1)[0]
    second = next((c for (v, o), c in votes.most_common(5) if v != vid or abs(o - off) > 4), 0)
    t = max(0.0, off * FRAME_S)
    return {"match": vid, "t": round(t, 1), "link": f"https://youtu.be/{vid}?t={int(t)}", "score": score,
            "runner_up": second, "confident": score >= 15 and score >= 3 * max(second, 1)}


def hum(db: dict, y16: np.ndarray) -> list[dict]:
    import librosa
    q = contour(y16, 16000)[0]
    res = []
    for vid, c in db["melody"].items():
        if len(q) < 10 or c.shape[1] < len(q):
            continue
        D, wp = librosa.sequence.dtw(X=q[None, :], Y=c[0][None, :], subseq=True, metric="euclidean")
        j = int(np.argmin(D[-1]))
        start = int(wp[-1][1])                                    # warping path is end->start; last pair = query start
        res.append({"video": vid, "cost": round(float(D[-1, j]) / len(q), 3), "t_start": round(float(c[1][start]), 1),
                    "t_end": round(float(c[1][j]), 1), "link": f"https://youtu.be/{vid}?t={int(c[1][start])}"})
    return sorted(res, key=lambda r: r["cost"])


def evaluate(work: Path, vdir: Path, n: int = 20, seed: int = 7) -> None:
    db, rng, rows = _db(work), np.random.default_rng(seed), []
    for mp4 in sorted(vdir.glob("*.mp4")):
        dur = db["meta"][mp4.stem]["seconds"]
        for _ in range(n):
            for clip in (3.0, 5.0, 10.0):
                s = float(rng.uniform(0, dur - clip - 1))
                y = load(mp4, start=s, dur=clip)
                for snr in (None, 10, 0):
                    yq = y if snr is None else y + rng.normal(0, np.sqrt(np.mean(y ** 2) / 10 ** (snr / 10)), len(y)).astype(np.float32)
                    yq = yq * 0.5
                    r = match(db, yq)
                    ok = r["match"] == mp4.stem and abs(r.get("t", -99) - s) <= 1.0
                    rows.append({"video": mp4.stem, "start": round(s, 1), "clip_s": clip, "snr_db": snr, "ok": ok, **r})
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        agg[(r["clip_s"], r["snr_db"])][0] += r["ok"]
        agg[(r["clip_s"], r["snr_db"])][1] += 1
    summary = {f"{c}s / SNR {s if s is not None else 'clean'}": f"{a}/{b}" for (c, s), (a, b) in sorted(agg.items(), key=lambda x: (x[0][0], -1 if x[0][1] is None else -x[0][1]))}
    (work / "audio" / "fp_eval.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    cmd, work = sys.argv[1], Path(sys.argv[2])
    if cmd == "build":
        build(work, Path(sys.argv[3]))
    elif cmd == "query":
        print(json.dumps(match(_db(work), load(Path(sys.argv[3]))), indent=1))
    elif cmd == "hum":
        print(json.dumps(hum(_db(work), load(Path(sys.argv[3]), sr=16000))[:3], indent=1))
    elif cmd == "eval":
        evaluate(work, Path(sys.argv[3]))
