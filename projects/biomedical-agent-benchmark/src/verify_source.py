"""Verify the public Dryad archive without downloading or extracting its data."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

EXPECTED_SHA256 = "a149ffb68f39a61566374af54bd35cea2c47e2b67c2e0c35307271f3b0542729"
EXPECTED_BYTES = 24_850_190
SIDES = ("P1R", "P2L", "P2R", "P3L", "P3R", "P4L", "P4R", "P5L", "P5R")


def verify(path):
    path = Path(path)
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if path.stat().st_size != EXPECTED_BYTES or digest != EXPECTED_SHA256:
        raise ValueError(
            "Archive does not match the verified Dryad release; check its version."
        )
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if archive.testzip() is not None:
            raise ValueError("ZIP integrity check failed")
        required = [f"{side}_ambulatory_features.h5" for side in SIDES]
        required.append("longitudinal_phase_metadata.csv")
        members = {}
        for filename in required:
            matches = [name for name in names if Path(name).name == filename]
            if len(matches) != 1:
                raise ValueError(f"Expected one original source member: {filename}")
            members[filename] = hashlib.sha256(archive.read(matches[0])).hexdigest()
    return {"archive_sha256": digest, "required_members": members, "verified": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.archive), indent=2))
