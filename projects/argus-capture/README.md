# Multi-camera Capture & Synchronization

The full application lives at https://github.com/pmeraga/argus-capture. This folder is a standalone snapshot of the audio alignment core, overlap calculations, a headless audio CLI, the experimental visual CLI, and synchronization tests. The images on the portfolio are generated demonstration frames.

## Problem

Independently recorded camera views start at different times. Manual offsets become a bottleneck when the amount of demonstration footage grows.

## Implementation

The app stores episode metadata in D1 and originals in R2. A worker extracts audio-onset fingerprints across frequency bands and searches for a distinct correlation peak. The same estimator runs headlessly through FFmpeg. Weak or ambiguous matches are flagged for review.

## Evidence

The included synchronization tests recover positive and negative offsets from generated audio, reject silence and repeating signals, and verify that playback remains inside the shared interval. The public repository contains the complete application, upload API, and integration tests.

## Limits

Browser playback corrects drift above 120 ms and remains approximate. Audio alignment estimates a constant offset within a five-minute analysis window. The optional optical-flow script is experimental. Original recordings and access keys are excluded.

## Run

Requires Node 22.13 or newer. The audio core and tests have no package dependencies.

```sh
npm test
node --experimental-strip-types scripts/sync-episode.mjs ego.mp4 left.mp4 right.mp4
```

The CLI needs FFmpeg on PATH. Set `FFMPEG` to use a specific binary. The optional visual estimator needs Python, NumPy, OpenCV, and FFmpeg. Inspect its options with `python scripts/sync-visual.py --help`.

Offsets follow `camera_time = episode_time + camera_offset`. A failed audio match is review-required. Playback and alignment are approximate.

## Links

- [Full application source](https://github.com/pmeraga/argus-capture)
- [Synchronization core](https://github.com/pmeraga/portfolio/tree/main/projects/argus-capture)
