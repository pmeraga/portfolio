# Concurrent Camera Streaming Service

A standalone camera service built as an interview exercise. The portfolio snapshot uses the neutral camera_rpc namespace, with Protobuf bindings regenerated from the included schema. Tests inject camera data and never open a physical camera.

## Problem

Multiple clients need live camera frames without opening the same device repeatedly or building an ever-growing queue. A fresh read also needs a precise definition.

## Implementation

One worker owns each camera and publishes immutable JPEGs into a shared slot. A fresh request snapshots the capture sequence at server acceptance and waits for a later capture. Slow streaming clients skip frames. Request IDs, capture timestamps, and monotonic durations make latency and failures inspectable.

## Evidence

The included tests use injected cameras and real loopback gRPC to exercise concurrent requests, captures awaiting encoding, stale frames, recovery, cancellation, deadlines, and decoding. The protocol and runnable server/client are included.

## Limits

Capture time means completion of the software camera read. Sensor exposure and device buffering require hardware validation. The default service is local and uses an insecure loopback channel. Remote use requires authentication and TLS.

## Run

Requires Python 3.12 or newer.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python generate_proto.py
python -m pytest -q
python -m camera_app.server
```

In another terminal with the environment active, use `python -m camera_app.client health`, `python -m camera_app.client frame`, or `python -m camera_app.client stream`. Hardware runs need a webcam and OS camera permission. The default endpoint is `127.0.0.1:50051`. Press Ctrl+C to stop the server.

## Links

- [Protocol & source](https://github.com/pmeraga/portfolio/tree/main/projects/camera-grpc)
