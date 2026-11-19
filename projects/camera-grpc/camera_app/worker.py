"""One camera owner, one immutable JPEG cache, independent of RPC clients."""
import asyncio
from dataclasses import dataclass
import logging
import platform
import threading
import time
import uuid

import cv2


@dataclass(frozen=True)
class CachedFrame:
    sequence: int
    captured_ns: int
    captured_wall_ns: int
    published_ns: int
    published_wall_ns: int
    jpeg: bytes
    width: int
    height: int


class CameraWorker:
    def __init__(self, camera_id="webcam", device=0, width=640, height=480,
                 fps=30, quality=80, stale_after=3.0, capture_factory=None):
        if min(width, height, fps, stale_after) <= 0 or not 1 <= quality <= 100:
            raise ValueError("Positive dimensions, fps, timeout and quality 1..100 required")
        self.camera_id, self.device = camera_id, device
        self.width, self.height, self.fps, self.quality = width, height, fps, quality
        self.stale_ns = int(stale_after * 1e9)
        self.capture_factory = capture_factory
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.changed = asyncio.Event()
        self.loop = None
        self.thread = None
        self.session = ""
        self.sequence = 0
        self.frame = None
        self.running = False
        self.started_ns = 0
        self.error = ""

    def notify(self):
        if self.loop and not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self.changed.set)
            except RuntimeError:
                pass  # Event loop may close during shutdown.

    def start(self):
        self.loop = asyncio.get_running_loop()
        if self.thread and self.thread.is_alive():
            raise RuntimeError("Camera worker is already running")
        with self.lock:
            self.session = str(uuid.uuid4())
            self.sequence, self.frame, self.error = 0, None, ""
            self.running, self.started_ns = True, time.monotonic_ns()
        self.stop_event.clear()
        # AVFoundation must request macOS camera authorization on the main
        # thread. Release the probe, then create/read/release the actual capture
        # on its owning thread; do not transfer an AVFoundation capture session.
        if platform.system() == "Darwin" and self.capture_factory is None:
            probe = cv2.VideoCapture(self.device, cv2.CAP_AVFOUNDATION)
            probe.release()
        self.thread = threading.Thread(target=self._run, name=self.camera_id, daemon=True)
        self.thread.start()

    def _run(self):
        capture = None
        try:
            backend = cv2.CAP_AVFOUNDATION if platform.system() == "Darwin" else cv2.CAP_ANY
            capture = (self.capture_factory() if self.capture_factory else
                       cv2.VideoCapture(self.device, backend))
            if not capture.isOpened():
                raise RuntimeError("Cannot open camera; check device index and macOS camera permission")
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            capture.set(cv2.CAP_PROP_FPS, self.fps)
            while not self.stop_event.is_set():
                ok, image = capture.read()
                if not ok or image is None:
                    with self.lock:
                        self.error = "Camera read failed"
                    self.notify()
                    self.stop_event.wait(0.05)
                    continue
                # Acceptance snapshots this same sequence under this same lock.
                with self.lock:
                    self.sequence += 1
                    sequence = self.sequence
                    captured_ns, wall_ns = time.monotonic_ns(), time.time_ns()
                ok, jpeg = cv2.imencode(".jpg", image,
                                        [cv2.IMWRITE_JPEG_QUALITY, self.quality])
                if not ok:
                    with self.lock:
                        self.error = "JPEG encoding failed"
                    self.notify()
                    continue
                encoded = jpeg.tobytes()
                height, width = image.shape[:2]
                with self.lock:
                    self.frame = CachedFrame(sequence, captured_ns, wall_ns,
                                             time.monotonic_ns(), time.time_ns(),
                                             encoded, width, height)
                    self.error = ""
                self.notify()
        except Exception as exc:
            logging.exception("Camera worker failed")
            with self.lock:
                self.error = str(exc)
        finally:
            if capture is not None:
                capture.release()
            with self.lock:
                self.running = False
            self.notify()

    def health_locked(self, now):
        """Called under lock; status names match protobuf enum suffixes."""
        if not self.running:
            return "UNAVAILABLE", self.error or "Camera worker stopped"
        if self.frame is None:
            if now - self.started_ns >= self.stale_ns:
                return "UNAVAILABLE", "No frame published before startup timeout"
            return "STARTING", self.error or "Waiting for first JPEG"
        if (now - self.frame.published_ns >= self.stale_ns or
                now - self.frame.captured_ns >= self.stale_ns):
            return "UNAVAILABLE", "Capture-to-cache pipeline is stale"
        if self.error:
            return "DEGRADED", self.error
        return "SERVING", "Camera is capturing and updating the JPEG cache"

    async def stop(self):
        self.stop_event.set()
        self.notify()
        if self.thread:
            await asyncio.to_thread(self.thread.join, 2.0)
            if self.thread.is_alive():
                logging.warning("Camera read remains blocked; daemon worker will exit with process")
