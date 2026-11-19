"""Reusable synchronous client and OpenCV viewer (GUI runs on main thread)."""
import argparse
import json
import threading
import time
import uuid

import cv2
import grpc
import numpy as np
from google.protobuf.json_format import MessageToDict
from google.protobuf.timestamp_pb2 import Timestamp
from camera_rpc.camera.v1 import camera_pb2 as pb, camera_pb2_grpc as rpc

from camera_app.server import OPTIONS


def request_context():
    now = Timestamp()
    now.GetCurrentTime()
    return pb.RequestContext(request_id=str(uuid.uuid4()), client_request_sent_at=now)


class CameraClient:
    def __init__(self, target="127.0.0.1:50051", camera_id="webcam", timeout=5.0):
        self.channel = grpc.insecure_channel(target, options=OPTIONS)
        self.stub = rpc.CameraServiceStub(self.channel)
        self.camera_id, self.timeout = camera_id, timeout
        self.last_round_trip_ms = None

    def getframe(self, fresh=True):
        request = pb.GetFrameRequest(context=request_context(), camera_id=self.camera_id, fresh=fresh)
        start = time.monotonic_ns()
        response = self.stub.GetFrame(request, timeout=self.timeout)
        self.last_round_trip_ms = (time.monotonic_ns() - start) / 1e6
        return response

    def checkhealth(self):
        request = pb.CheckHealthRequest(context=request_context(), camera_id=self.camera_id)
        start = time.monotonic_ns()
        response = self.stub.CheckHealth(request, timeout=self.timeout)
        self.last_round_trip_ms = (time.monotonic_ns() - start) / 1e6
        return response

    def getstream(self, timeout=None):
        return self.stub.GetStream(pb.GetStreamRequest(
            context=request_context(), camera_id=self.camera_id), timeout=timeout)

    def close(self):
        self.channel.close()


class LatestStream:
    """Drain gRPC independently of GUI speed, retaining one response only."""
    def __init__(self, call):
        self.call = call
        self.condition = threading.Condition()
        self.latest = None
        self.finished = False
        self.error = None
        self.thread = threading.Thread(target=self._receive, daemon=True)
        self.thread.start()

    def _receive(self):
        try:
            for response in self.call:
                sample = response, time.monotonic_ns(), time.time_ns()
                with self.condition:
                    self.latest = sample
                    self.condition.notify_all()
        except Exception as exc:
            with self.condition:
                self.error = exc
        finally:
            with self.condition:
                self.finished = True
                self.condition.notify_all()

    def __iter__(self):
        return self

    def __next__(self):
        with self.condition:
            while self.latest is None and not self.finished:
                self.condition.wait(0.1)
            if self.latest is not None:
                sample, self.latest = self.latest, None
                return sample
            if self.error:
                raise self.error
            raise StopIteration

    def close(self):
        self.call.cancel()
        self.thread.join(timeout=2)


def display(response, show):
    frame = response.frame
    image = cv2.imdecode(np.frombuffer(frame.jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Server returned an invalid JPEG")
    if show:
        title = "Camera viewer - q to quit"
        cv2.imshow(title, image)
        key = cv2.waitKey(1) & 0xff
        return key not in (ord("q"), 27) and cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) >= 1
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["health", "frame", "stream"])
    parser.add_argument("--target", default="127.0.0.1:50051")
    parser.add_argument("--camera-id", default="webcam")
    parser.add_argument("--cached", action="store_true", help="frame mode: fresh=false")
    parser.add_argument("--timeout", type=float, default=5.0, help="Unary deadline in seconds")
    parser.add_argument("--no-display", action="store_true", help="Decode and log without opening a window")
    parser.add_argument("--count", type=int, default=0, help="Stream frame limit; zero means unlimited")
    args = parser.parse_args()
    if args.timeout <= 0 or args.count < 0:
        parser.error("timeout must be positive and count nonnegative")
    client = CameraClient(args.target, args.camera_id, args.timeout)
    stream = None
    reader = None
    try:
        if args.mode == "health":
            response = client.checkhealth()
            print(json.dumps(MessageToDict(response), indent=2))
            print(f"round_trip_ms={client.last_round_trip_ms:.3f}")
        elif args.mode == "frame":
            response = client.getframe(fresh=not args.cached)
            print(f"sequence={response.frame.sequence} round_trip_ms={client.last_round_trip_ms:.3f}")
            if display(response, not args.no_display) and not args.no_display:
                while cv2.getWindowProperty("Camera viewer - q to quit", cv2.WND_PROP_VISIBLE) >= 1:
                    if cv2.waitKey(30) & 0xff in (ord("q"), 27):
                        break
        else:
            start = previous = time.monotonic_ns()
            stream = client.getstream()
            reader = LatestStream(stream)
            for count, (response, received, received_wall) in enumerate(reader, 1):
                label = "first_frame_ms" if count == 1 else "interarrival_ms"
                interval = received - (start if count == 1 else previous)
                previous = received
                age = (received_wall - response.frame.captured_at.ToNanoseconds()) / 1e6
                print(f"sequence={response.frame.sequence} {label}={interval / 1e6:.3f} "
                      f"frame_age_ms={age:.3f} (requires aligned wall clocks)", flush=True)
                if not display(response, not args.no_display) or (args.count and count >= args.count):
                    break
    except grpc.RpcError as exc:
        parser.exit(1, f"{exc.code().name}: {exc.details()}\n")
    except KeyboardInterrupt:
        pass
    finally:
        if reader is not None:
            reader.close()
        elif stream is not None:
            stream.cancel()
        client.close()
        if not args.no_display:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
