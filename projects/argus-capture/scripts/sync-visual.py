"""Experimental visual alignment of overlapping UMI recordings."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np


FPS = 6
WIDTH, HEIGHT = 240, 136
DEFAULT_ROI = (0.17, 0.22, 0.66, 0.66)


def region(value):
    try:
        x, y, w, h = (float(field) for field in value.split(","))
        if (0 <= x and 0 <= y and 0.05 <= w and 0.05 <= h
                and x + w <= 1 and y + h <= 1):
            return x, y, w, h
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("ROI must be x,y,width,height within the image (0 to 1).")


def frame_range(image, roi):
    x, y, width, height = roi
    return image[round(y * HEIGHT):round((y + height) * HEIGHT),
                 round(x * WIDTH):round((x + width) * WIDTH)]


def motion_signal(frames, roi):
    previous = None
    features = []
    for frame in frames:
        if previous is not None:
            flow = cv2.calcOpticalFlowFarneback(
                previous, frame, None, 0.5, 3, 15, 2, 5, 1.1, 0
            )
            # Median flow removes bulk translation. Keep the raw motion as
            # a second cue because moving wrist cameras often move with the action.
            translation = np.median(flow[12:-12:4, 12:-12:4], axis=(0, 1))
            action = frame_range(flow, roi)[::2, ::2]
            features.append([
                np.percentile(np.linalg.norm(action, axis=2), 90),
                np.percentile(np.linalg.norm(action - translation, axis=2), 90),
            ])
        previous = frame
    if len(features) < FPS * 8:
        raise ValueError("Each clip needs at least eight seconds of decodable video.")
    return cv2.GaussianBlur(np.log1p(np.asarray(features)), (1, 5), 0)


def read_video(path, roi, seconds, ffmpeg):
    command = [
        ffmpeg, "-nostdin", "-loglevel", "error", "-threads", "2", "-i", path,
        "-t", str(seconds), "-map", "0:v:0", "-an",
        "-vf", f"fps={FPS},scale={WIDTH}:{HEIGHT}", "-pix_fmt", "gray",
        "-threads", "1", "-f", "rawvideo", "-",
    ]
    with subprocess.Popen(command, stdout=subprocess.PIPE) as decoder:
        def frames():
            while data := decoder.stdout.read(WIDTH * HEIGHT):
                if len(data) != WIDTH * HEIGHT:
                    raise ValueError(f"Truncated decoded frame in {path}")
                yield np.frombuffer(data, np.uint8).reshape(HEIGHT, WIDTH)

        try:
            signal = motion_signal(frames(), roi)
            if decoder.wait() != 0:
                raise ValueError(f"FFmpeg could not decode {path}")
            return signal
        finally:
            if decoder.poll() is None:
                decoder.kill()


def scores(ego, wrist, lags, start, end):
    values = []
    for lag in lags:
        a, b = ego[start:end], wrist[start + lag:end + lag]
        a = a - a.mean(axis=0)
        b = b - b.mean(axis=0)
        norm = np.linalg.norm(a, axis=0) * np.linalg.norm(b, axis=0)
        values.append(np.divide((a * b).sum(axis=0), norm,
                                out=np.zeros(a.shape[1]), where=norm > 1e-8).mean())
    return np.asarray(values)


def estimate(ego, wrist, max_lag):
    # Compare all candidate lags on the same time interval.
    limit = min(round(max_lag * FPS), (min(len(ego), len(wrist)) - 8 * FPS) // 2)
    start, end = limit, min(len(ego), len(wrist) - limit)
    lags = np.arange(-limit, limit + 1)
    full_scores = scores(ego, wrist, lags, start, end)
    best_index = int(np.argmax(full_scores))
    best = int(lags[best_index])
    peak = float(full_scores[best_index])
    alternatives = full_scores[np.abs(lags - best) > FPS]
    margin = peak - float(alternatives.max()) if alternatives.size else 0.0

    window_offsets = []
    split = np.linspace(start, end, 4, dtype=int)
    for lo, hi in zip(split[:-1], split[1:]):
        window = scores(ego, wrist, lags, lo, hi)
        winner = int(np.argmax(window))
        if window[winner] >= 0.25:
            window_offsets.append(int(lags[winner]))
    agrees = sum(abs(lag - best) <= 2 for lag in window_offsets)
    verified = (
        abs(best) < limit and peak >= 0.30 and margin >= 0.06
        and agrees >= 2 and agrees == len(window_offsets)
    )
    return {
        "status": "candidate" if verified else "needs-review",
        "candidateSeconds": best / FPS,
        "correlation": round(peak, 4),
        "peakMargin": round(margin, 4),
        "windowCandidatesSeconds": [lag / FPS for lag in window_offsets],
        "comparedEgoIntervalSeconds": [start / FPS, end / FPS],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ego", help="Reference video path")
    parser.add_argument("wrist", nargs="+", help="Overlapping wrist video paths")
    parser.add_argument("--ego-roi", type=region, default=DEFAULT_ROI)
    parser.add_argument("--wrist-roi", type=region, action="append",
                        help="Optional ROI per wrist, in input order (x,y,width,height)")
    parser.add_argument("--max-lag", type=float, default=15, help="Maximum start offset in seconds")
    parser.add_argument("--seconds", type=int, default=180, help="Seconds to decode per input")
    parser.add_argument("--ffmpeg", default=os.environ.get("FFMPEG", "ffmpeg"))
    args = parser.parse_args()
    if not math.isfinite(args.max_lag) or args.max_lag <= 0 or args.seconds < 9:
        parser.error("Use a positive finite max lag and at least nine seconds of video.")
    wrist_rois = args.wrist_roi or [DEFAULT_ROI] * len(args.wrist)
    if len(wrist_rois) != len(args.wrist):
        parser.error("Supply one --wrist-roi for each wrist clip.")
    cv2.setNumThreads(1)
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            pending = [
                pool.submit(read_video, path, roi, args.seconds, args.ffmpeg)
                for path, roi in zip([args.ego, *args.wrist], [args.ego_roi, *wrist_rois])
            ]
            ego, *wrists = (job.result() for job in pending)
        matches = [
            {"path": path, **estimate(ego, wrist, args.max_lag)}
            for path, wrist in zip(args.wrist, wrists)
        ]
    except (OSError, ValueError, cv2.error) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps({"reference": args.ego, "method": "visual-motion", "matches": matches},
                     indent=2))
    return int(any(match["status"] == "needs-review" for match in matches))


if __name__ == "__main__":
    sys.exit(main())
