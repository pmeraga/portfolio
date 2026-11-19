import asyncio
from contextlib import asynccontextmanager
import queue
import time

import cv2
import grpc
import numpy as np
import pytest

from camera_app.client import CameraClient, LatestStream, request_context
from camera_app.server import CameraService, OPTIONS
from camera_app.worker import CachedFrame, CameraWorker
from camera_rpc.camera.v1 import camera_pb2 as pb, camera_pb2_grpc as rpc


@pytest.fixture(autouse=True)
def disable_physical_camera(monkeypatch):
    """Keep the test suite from opening the host computer's camera."""
    def forbidden_video_capture(*args, **kwargs):
        raise AssertionError("Tests must use an injected fake camera")

    monkeypatch.setattr(cv2, "VideoCapture", forbidden_video_capture)


class ObservedService(CameraService):
    def __init__(self, workers):
        super().__init__(workers)
        self.accepted = asyncio.Queue()

    async def accept(self, request, context):
        result = await super().accept(request, context)
        self.accepted.put_nowait(type(request).__name__)
        return result


@asynccontextmanager
async def endpoint():
    worker = CameraWorker(stale_after=1)
    worker.running, worker.session = True, "test-session"
    worker.started_ns = time.monotonic_ns()
    worker.loop = asyncio.get_running_loop()
    service = ObservedService({"webcam": worker})
    server = grpc.aio.server(options=OPTIONS)
    rpc.add_CameraServiceServicer_to_server(service, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    async with grpc.aio.insecure_channel(f"127.0.0.1:{port}", options=OPTIONS) as channel:
        try:
            yield worker, service, rpc.CameraServiceStub(channel), f"127.0.0.1:{port}"
        finally:
            await server.stop(0)


def publish(worker, sequence=None, capture_age=0):
    ok, jpeg = cv2.imencode(".jpg", np.zeros((24, 32, 3), dtype=np.uint8))
    assert ok
    with worker.lock:
        sequence = worker.sequence + 1 if sequence is None else sequence
        worker.sequence = max(worker.sequence, sequence)
        now, wall = time.monotonic_ns(), time.time_ns()
        worker.frame = CachedFrame(sequence, now - capture_age, wall - capture_age,
                                   now, wall, jpeg.tobytes(), 32, 24)
    worker.notify()


def request(kind, **kwargs):
    return kind(context=request_context(), camera_id="webcam", **kwargs)


def test_fresh_boundary_concurrent_clients_and_cached_jpeg():
    async def scenario():
        async with endpoint() as (worker, service, stub, target):
            publish(worker)
            cached = await stub.GetFrame(request(pb.GetFrameRequest, fresh=False))
            assert cached.frame.sequence == 1
            assert cv2.imdecode(np.frombuffer(cached.frame.jpeg, np.uint8), 1).shape == (24, 32, 3)
            await service.accepted.get()
            # Capture 2 completed before acceptance but has not finished encoding.
            with worker.lock:
                worker.sequence = 2
            first = stub.GetFrame(request(pb.GetFrameRequest), timeout=2)
            second = stub.GetFrame(request(pb.GetFrameRequest, fresh=True), timeout=2)
            await service.accepted.get()
            await service.accepted.get()
            publish(worker, 2)
            await asyncio.sleep(0.03)
            assert not first.done() and not second.done()
            publish(worker, 3)
            responses = await asyncio.gather(first, second)
            assert [r.frame.sequence for r in responses] == [3, 3]
            assert responses[0].context.server_elapsed.ToNanoseconds() > 0
            # Exercise the public synchronous client over real gRPC too.
            def cached_client():
                client = CameraClient(target)
                try:
                    assert client.getframe(False).frame.sequence == 3
                    assert client.last_round_trip_ms > 0
                finally:
                    client.close()
            await asyncio.to_thread(cached_client)
    asyncio.run(scenario())


def test_health_detects_stall_startup_and_delayed_encoding():
    async def scenario():
        async with endpoint() as (worker, _, stub, _):
            async def health():
                return await stub.CheckHealth(request(pb.CheckHealthRequest))
            starting = await health()
            assert starting.status == pb.CAMERA_HEALTH_STATUS_STARTING
            assert not starting.HasField("cache_update_age")
            with worker.lock:
                worker.started_ns -= worker.stale_ns
            assert (await health()).status == pb.CAMERA_HEALTH_STATUS_UNAVAILABLE
            publish(worker)
            healthy = await health()
            assert healthy.status == pb.CAMERA_HEALTH_STATUS_SERVING
            assert healthy.HasField("last_cache_updated_at")
            with worker.lock:
                worker.error = "Recoverable read error"
            assert (await health()).status == pb.CAMERA_HEALTH_STATUS_DEGRADED
            with worker.lock:
                worker.error = ""
                old = worker.frame
                worker.frame = CachedFrame(old.sequence, old.captured_ns, old.captured_wall_ns,
                                           old.published_ns - worker.stale_ns,
                                           old.published_wall_ns, old.jpeg, old.width, old.height)
            stalled = await health()
            assert stalled.worker_running
            assert stalled.status == pb.CAMERA_HEALTH_STATUS_UNAVAILABLE
            # Cached reads neither fail nor refresh the timer.
            await stub.GetFrame(request(pb.GetFrameRequest, fresh=False))
            assert (await health()).cache_update_age.ToNanoseconds() >= worker.stale_ns
            publish(worker, capture_age=worker.stale_ns)
            assert (await health()).status == pb.CAMERA_HEALTH_STATUS_UNAVAILABLE
            publish(worker)
            assert (await health()).status == pb.CAMERA_HEALTH_STATUS_SERVING
            with worker.lock:
                worker.running = False
            assert (await health()).status == pb.CAMERA_HEALTH_STATUS_UNAVAILABLE
    asyncio.run(scenario())


def test_stream_skips_frames_cancellation_deadline_and_validation():
    async def scenario():
        async with endpoint() as (worker, service, stub, _):
            publish(worker)
            stream = stub.GetStream(request(pb.GetStreamRequest))
            reading = asyncio.create_task(stream.read())
            await service.accepted.get()
            publish(worker, 2)
            assert (await reading).frame.sequence == 2
            publish(worker, 3)
            publish(worker, 4)
            assert (await stream.read()).frame.sequence == 4
            # An active stream must not block health or other RPCs.
            assert (await stub.CheckHealth(request(pb.CheckHealthRequest))).worker_running
            stream.cancel()
            assert await stream.code() == grpc.StatusCode.CANCELLED
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.GetFrame(request(pb.GetFrameRequest), timeout=0.05)
            assert error.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED
            bad = request(pb.CheckHealthRequest)
            bad.camera_id = "unknown"
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.CheckHealth(bad)
            assert error.value.code() == grpc.StatusCode.NOT_FOUND
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.CheckHealth(pb.CheckHealthRequest(camera_id="webcam"))
            assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    asyncio.run(scenario())


def test_capture_worker_encodes_and_releases_camera():
    class FakeCamera:
        def __init__(self):
            self.images = queue.Queue()
            self.released = False

        def isOpened(self):
            return True

        def set(self, *args):
            return True

        def read(self):
            try:
                return True, self.images.get(timeout=0.05)
            except queue.Empty:
                return False, None

        def release(self):
            self.released = True

    async def scenario():
        camera = FakeCamera()
        worker = CameraWorker(capture_factory=lambda: camera)
        worker.start()
        try:
            camera.images.put(np.zeros((48, 64, 3), dtype=np.uint8))
            async def wait_frame():
                while True:
                    worker.changed.clear()
                    with worker.lock:
                        frame = worker.frame
                    if frame:
                        return frame
                    await worker.changed.wait()
            frame = await asyncio.wait_for(wait_frame(), 2)
            assert frame.sequence == 1 and frame.width == 64 and frame.height == 48
            assert frame.published_ns >= frame.captured_ns
            assert cv2.imdecode(np.frombuffer(frame.jpeg, np.uint8), 1) is not None
        finally:
            await worker.stop()
        assert camera.released and not worker.running
    asyncio.run(scenario())


def test_viewer_receiver_skips_frames_while_gui_is_busy():
    async def scenario():
        async with endpoint() as (worker, service, _, target):
            client = CameraClient(target)
            reader = LatestStream(client.getstream())
            try:
                await service.accepted.get()
                publish(worker, 1)
                sample = await asyncio.wait_for(asyncio.to_thread(next, reader), 2)
                assert sample[0].frame.sequence == 1
                async def wait_received(sequence):
                    while True:
                        with reader.condition:
                            if reader.latest and reader.latest[0].frame.sequence == sequence:
                                return
                        await asyncio.sleep(0.001)
                publish(worker, 2)
                await asyncio.wait_for(wait_received(2), 2)
                # Do not consume sample 2: emulate a busy OpenCV GUI thread.
                publish(worker, 3)
                await asyncio.wait_for(wait_received(3), 2)
                assert next(reader)[0].frame.sequence == 3
            finally:
                await asyncio.to_thread(reader.close)
                client.close()
    asyncio.run(scenario())


def test_empty_cache_and_stream_stall():
    async def scenario():
        async with endpoint() as (worker, service, stub, _):
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await stub.GetFrame(request(pb.GetFrameRequest, fresh=False))
            assert error.value.code() == grpc.StatusCode.UNAVAILABLE
            await service.accepted.get()
            publish(worker)
            stream = stub.GetStream(request(pb.GetStreamRequest))
            reading = asyncio.create_task(stream.read())
            await service.accepted.get()
            # No more publications; worker thread still claims to be running.
            with worker.lock:
                worker.stale_ns = 1
            with pytest.raises(grpc.aio.AioRpcError) as error:
                await asyncio.wait_for(reading, 1)
            assert error.value.code() == grpc.StatusCode.UNAVAILABLE
    asyncio.run(scenario())
