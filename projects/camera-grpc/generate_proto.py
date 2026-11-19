"""Run after editing the protocol: python generate_proto.py."""
from pathlib import Path
import grpc_tools
from grpc_tools import protoc

root = Path(__file__).resolve().parent
includes = Path(grpc_tools.__file__).parent / "_proto"
raise SystemExit(protoc.main([
    "protoc", f"-I{root / 'proto'}", f"-I{includes}",
    f"--python_out={root}", f"--grpc_python_out={root}",
    str(root / "proto/camera_rpc/camera/v1/camera.proto"),
]))
