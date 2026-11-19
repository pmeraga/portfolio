"""Async RPC handlers; camera I/O and encoding live in dedicated threads."""
import argparse
import asyncio
import logging
import signal
import time

import grpc
from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp
from camera_rpc.camera.v1 import camera_pb2 as pb, camera_pb2_grpc as rpc

from camera_app.worker import CameraWorker

MAX_MESSAGE = 16 * 1024 * 1024
OPTIONS = [("grpc.max_send_message_length", MAX_MESSAGE),
           ("grpc.max_receive_message_length", MAX_MESSAGE)]


def timestamp(ns):
    value = Timestamp()
    value.FromNanoseconds(ns)
    return value


def duration(ns):
    value = Duration()
    value.FromNanoseconds(ns)
    return value


class CameraService(rpc.CameraServiceServicer):
    def __init__(self, workers):
        self.workers = workers

    async def accept(self, request, context):
        if not request.camera_id or not request.context.request_id:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "camera_id and request_id required")
        try:
            if not request.context.HasField("client_request_sent_at"):
                raise ValueError("timestamp missing")
            request.context.client_request_sent_at.ToDatetime()
        except (ValueError, OverflowError):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Valid client timestamp required")
        worker = self.workers.get(request.camera_id)
        if worker is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "Unknown camera_id")
        with worker.lock:
            accepted = (time.monotonic_ns(), time.time_ns())
            boundary, session = worker.sequence, worker.session
        return worker, accepted, boundary, session

    def response_context(self, request, accepted):
        return pb.ResponseContext(
            request_id=request.context.request_id,
            client_request_sent_at=request.context.client_request_sent_at,
            server_accepted_at=timestamp(accepted[1]),
            server_response_ready_at=timestamp(time.time_ns()),
            server_elapsed=duration(time.monotonic_ns() - accepted[0]))

    async def latest(self, worker, boundary, session, context, fresh=True):
        while True:
            # Clear before inspecting state; publication notifications are queued
            # on this event loop, so a publication cannot be lost before await.
            worker.changed.clear()
            with worker.lock:
                frame, current_session = worker.frame, worker.session
                status, detail = worker.health_locked(time.monotonic_ns())
            if session != current_session:
                await context.abort(grpc.StatusCode.UNAVAILABLE, "Capture session restarted")
            if not fresh:
                if frame is None:
                    await context.abort(grpc.StatusCode.UNAVAILABLE, "Cache is empty")
                return frame
            if status == "UNAVAILABLE":
                await context.abort(grpc.StatusCode.UNAVAILABLE, detail)
            if frame is not None and frame.sequence > boundary:
                return frame
            # Periodically reevaluate health even if camera.read blocks forever.
            try:
                await asyncio.wait_for(worker.changed.wait(), timeout=0.05)
            except TimeoutError:
                pass

    def frame_response(self, request, accepted, worker, session, frame):
        return pb.FrameResponse(
            frame=pb.Frame(camera_id=worker.camera_id, capture_session_id=session,
                           sequence=frame.sequence, captured_at=timestamp(frame.captured_wall_ns),
                           jpeg=frame.jpeg, width=frame.width, height=frame.height),
            context=self.response_context(request, accepted))

    async def GetFrame(self, request, context):
        worker, accepted, boundary, session = await self.accept(request, context)
        fresh = request.fresh if request.HasField("fresh") else True
        frame = await self.latest(worker, boundary, session, context, fresh)
        return self.frame_response(request, accepted, worker, session, frame)

    async def GetStream(self, request, context):
        worker, accepted, boundary, session = await self.accept(request, context)
        while True:
            frame = await self.latest(worker, boundary, session, context)
            boundary = frame.sequence
            yield self.frame_response(request, accepted, worker, session, frame)

    async def CheckHealth(self, request, context):
        worker, accepted, _, session = await self.accept(request, context)
        with worker.lock:
            now = time.monotonic_ns()
            status, detail = worker.health_locked(now)
            frame = worker.frame
            response = pb.CheckHealthResponse(
                camera_id=worker.camera_id, capture_session_id=session,
                status=getattr(pb, "CAMERA_HEALTH_STATUS_" + status), detail=detail,
                worker_running=worker.running, stale_after=duration(worker.stale_ns))
            if frame is not None:
                response.latest_sequence = frame.sequence
                response.latest_captured_at.CopyFrom(timestamp(frame.captured_wall_ns))
                response.latest_frame_age.CopyFrom(duration(now - frame.captured_ns))
                response.last_cache_updated_at.CopyFrom(timestamp(frame.published_wall_ns))
                response.cache_update_age.CopyFrom(duration(now - frame.published_ns))
        response.context.CopyFrom(self.response_context(request, accepted))
        return response


async def serve(args):
    workers = {}
    for specification in args.camera or ["webcam=0"]:
        camera_id, device = specification.split("=", 1)
        if not camera_id or camera_id in workers:
            raise ValueError("Camera IDs must be nonempty and unique")
        workers[camera_id] = CameraWorker(camera_id, int(device), args.width, args.height,
                                          args.fps, args.quality, args.stale_after)
    if len({worker.device for worker in workers.values()}) != len(workers):
        raise ValueError("Each physical device must have exactly one worker")
    server = grpc.aio.server(options=OPTIONS)
    rpc.add_CameraServiceServicer_to_server(CameraService(workers), server)
    if server.add_insecure_port(args.bind) == 0:
        raise RuntimeError("Cannot bind server address")
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopped.set)
    try:
        for worker in workers.values():
            worker.start()
        await server.start()
        logging.info("Listening on %s; cameras: %s", args.bind, list(workers))
        await stopped.wait()
    finally:
        await server.stop(1)
        await asyncio.gather(*(worker.stop() for worker in workers.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1:50051")
    parser.add_argument("--camera", action="append", help="Repeat ID=DEVICE_INDEX; default webcam=0")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--quality", type=int, default=80)
    parser.add_argument("--stale-after", type=float, default=3.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(serve(args))


if __name__ == "__main__":
    main()
