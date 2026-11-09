"""Private-file and freshness policy (also usable without Home Assistant)."""
import json
import os
import stat
import time
from pathlib import Path

MAX_AGE = 20
MAX_FRAME = 65536
FIELDS = {"available", "control_available", "timestamp", "source", "mode", "camera_label", "date", "time", "rate", "view_status", "command_id", "status", "error"}


def private_directory(config_dir):
    root = Path(config_dir).resolve(strict=True)
    directory = root / "phone_camera_bridge"
    if directory.is_symlink():
        raise ValueError("Bridge directory may not be a symlink")
    directory.mkdir(mode=0o700, exist_ok=True)
    if not directory.is_dir() or directory.resolve() != directory:
        raise ValueError("Unsafe bridge directory")
    os.chmod(directory, 0o700)
    return directory


def read_private(directory, name, limit):
    if name not in {"frame.jpg", "metadata.json", "command.json"}:
        raise ValueError("Invalid bridge filename")
    if directory.is_symlink() or directory.resolve() != directory:
        raise ValueError("Unsafe bridge directory")
    fd = os.open(directory / name, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("Bridge file is not regular")
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Bridge file too large")
    return data


def valid_metadata(value, now=None):
    now = time.time() if now is None else now
    if not isinstance(value, dict):
        return False
    stamp = value.get("timestamp")
    return (isinstance(stamp, (int, float)) and not isinstance(stamp, bool)
            and 0 <= now - stamp <= MAX_AGE
            and value.get("available") is True
            and value.get("source") == "com.connect.enduser"
            and value.get("mode") in {"Live", "Playback"})


def load_metadata(directory):
    value = json.loads(read_private(directory, "metadata.json", 8192))
    if not isinstance(value, dict):
        raise ValueError("Invalid metadata")
    return {k: v for k, v in value.items() if k in FIELDS}


def valid_controls(value, now=None):
    if not isinstance(value, dict):
        return False
    return valid_metadata({**value, "available": value.get("available") is True
                           or value.get("control_available") is True}, now=now)


def snapshot(directory):
    before = load_metadata(directory)
    if not valid_metadata(before):
        return None
    image = read_private(directory, "frame.jpg", MAX_FRAME)
    after = load_metadata(directory)
    if before != after or not valid_metadata(after) or not image.startswith(b"\xff\xd8"):
        return None
    return image


def write_command(directory, command):
    if directory.is_symlink() or directory.resolve() != directory:
        raise ValueError("Unsafe bridge directory")
    target = directory / "command.json"
    if target.is_symlink():
        raise ValueError("Unsafe command file")
    temporary = directory / (".command-" + command["command_id"])
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(command, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
