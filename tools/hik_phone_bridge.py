#!/usr/bin/env python3
"""USB/ADB selected-view snapshot bridge. Requires Pillow on the Mac only.

Never unlocks, launches apps, or controls cameras. Guest publication is queued
through UTM; a zero exit code is not proof that HA received a frame.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import fcntl
import io
import json
import os
import re
import shlex
import signal
import stat
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

APP = "com.connect.enduser"
REMOTE = "/sdcard/Download/family-camera-analysis"
GUEST_COMMAND = "/mnt/data/supervisor/homeassistant/phone_camera_bridge/command.json"
MAX_JPEG = 65000


class UnsafeView(ValueError):
    pass


def bounds(node):
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.get("bounds", ""))
    if not match:
        raise UnsafeView("Missing view bounds")
    x1, y1, x2, y2 = map(int, match.groups())
    if x1 >= x2 or y1 >= y2:
        raise UnsafeView("Empty view bounds")
    return x1, y1, x2, y2


def intersects(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def parse_view(xml, today=None, require_video=True):
    root = ET.fromstring(xml)
    nodes = list(root.iter("node"))
    def find(resource):
        matches = matching(resource)
        if len(matches) != 1:
            raise UnsafeView("Required app view missing or ambiguous")
        return matches[0]
    def matching(resource):
        distinct = {}
        for node in nodes:
            if node.get("package") == APP and node.get("resource-id") == APP + ":id/" + resource:
                identity = tuple(node.get(k, "") for k in
                                 ("class", "bounds", "text", "content-desc", "enabled", "clickable"))
                distinct[identity] = node
        return list(distinct.values())
    play = find("play_view")
    if play.get("class") != "android.view.TextureView":
        raise UnsafeView("Not a video texture")
    crop = bounds(play)
    for node in nodes:
        package = node.get("package", "")
        if package == APP:
            continue
        # Only system status/navigation UI outside the video is permitted.
        if package != "com.android.systemui" or intersects(bounds(node), crop):
            raise UnsafeView("Foreign overlay")
    target = find("play_mode_tv").get("text", "").strip()
    modes = {"Playback": "Live", "Live View": "Playback"}
    if target not in modes:
        raise UnsafeView("Unknown app mode")
    value = {"source": APP, "mode": modes[target]}
    for resource, key in (("title_tv", "camera_label"), ("record_date_tv", "date"),
                          ("play_time_text", "time"), ("rate_text", "rate")):
        matches = matching(resource)
        if len(matches) == 1:
            value[key] = matches[0].get("text", "")[:128]
    if value.get("date") == "Today" and today:
        datetime.datetime.strptime(today, "%Y/%m/%d")
        value["date"] = today
    statuses = [n.get("text", "").strip() for n in nodes
                if n.get("resource-id") == APP + ":id/play_view_status_tv"]
    # Throughput overlays auto-hide and paused playback can have zero throughput.
    # This is a mirror of the validated app texture, not proof of a native stream.
    if require_video and any(re.search(r"loading|failed|offline|error|connecting|buffer", s, re.I) for s in statuses):
        raise UnsafeView("Video is not yet stable")
    if statuses:
        value["view_status"] = statuses[0][:128]
    return value, crop, find


def unlocked(policy):
    # Fail closed if Android doesn't expose an explicit keyguard state.
    locked = re.search(r"(?:mShowingLockscreen|mKeyguardShowing|showing|isKeyguardShowing)\s*=\s*true\b", policy)
    clear = re.search(r"(?:mShowingLockscreen|mKeyguardShowing|showing|isKeyguardShowing)\s*=\s*false\b", policy)
    return bool(clear and not locked)


def foreground_is_app(windows):
    focus = re.findall(r"mCurrentFocus\s*=\s*(.+)", windows)
    return len(focus) == 1 and bool(re.search(r"\bcom\.connect\.enduser/", focus[0]))


def action_target(action, view):
    mode = view["mode"]
    if action in ("live", "recordings"):
        expected = "Live" if action == "live" else "Playback"
        return (None if mode == expected else "playSwitchBtn"), expected, None
    if action not in ("previous_day", "next_day") or mode != "Playback":
        raise UnsafeView("Date action requires Playback")
    try:
        date = datetime.datetime.strptime(view.get("date", ""), "%Y/%m/%d").date()
    except ValueError:
        raise UnsafeView("Unrecognized recording date")
    delta = -1 if action == "previous_day" else 1
    return ("record_date_subtract_iv" if delta == -1 else "record_date_add_iv",
            "Playback", (date + datetime.timedelta(days=delta)).strftime("%Y/%m/%d"))


def load_serial(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "r") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("Serial JSON must be a private regular file (chmod 600)")
        value = json.loads(handle.read(8192))
    if not isinstance(value, dict):
        raise ValueError("Serial JSON must be an object")
    serial = value.get("serial", value.get("adb_serial"))
    if not isinstance(serial, str) or not re.fullmatch(r"[A-Za-z0-9._:-]+", serial):
        raise ValueError("Serial JSON needs a valid serial or adb_serial field")
    return serial


class Bridge:
    def __init__(self, args):
        self.args = args
        self.serial = load_serial(args.serial_file)
        self.seen = set()
        self.ack = {}
        self.state_path = args.serial_file + ".hik-bridge-state.json"
        try:
            fd = os.open(self.state_path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "r") as f:
                info = os.fstat(f.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                    raise ValueError("Command state must be a private regular file")
                saved = json.load(f)
            self.seen = {str(uuid.UUID(value)) for value in saved["seen"]}
        except FileNotFoundError:
            pass
        # Carry forward the last published acknowledgement across a graceful
        # helper handover; do not repeat a date tap from the previous process.
        try:
            raw = self.run([args.utmctl, "file", "pull", args.vm,
                           GUEST_COMMAND.replace("command.json", "metadata.json")])
            last = json.loads(raw)
            if last.get("status") in ("success", "error"):
                last_id = str(uuid.UUID(last["command_id"]))
                self.seen.add(last_id)
        except (subprocess.SubprocessError, ValueError, KeyError, TypeError):
            pass

    def claim(self, command_id):
        if command_id in self.seen:
            return False
        self.seen.add(command_id)
        if len(self.seen) > 1024:
            self.seen = {command_id}
        path = getattr(self, "state_path", None)
        if path:
            temporary = path + ".incoming-" + uuid.uuid4().hex
            if os.path.islink(path):
                raise ValueError("Unsafe command-state file")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump({"seen": sorted(self.seen)}, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return True

    def run(self, argv, timeout=20):
        return subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True, timeout=timeout).stdout

    def adb(self, *args):
        return self.run([self.args.adb, "-s", self.serial] + list(args))

    def guard(self):
        policy = self.adb("shell", "dumpsys", "window", "policy").decode("utf-8", "replace")
        windows = self.adb("shell", "dumpsys", "window").decode("utf-8", "replace")
        if not unlocked(policy) or not foreground_is_app(windows):
            raise UnsafeView("Phone locked or Hik-Connect not focused")

    def view(self, require_video=True):
        self.guard()
        path = REMOTE + "/view-" + uuid.uuid4().hex + ".xml"
        self.adb("shell", "mkdir", "-p", REMOTE)
        try:
            self.adb("shell", "uiautomator", "dump", path)
            xml = self.adb("exec-out", "cat", path)
        finally:
            self.adb("shell", "rm", "-f", path)
        self.guard()
        today = self.adb("shell", "date", "+%Y/%m/%d").decode("ascii").strip()
        return parse_view(xml, today=today, require_video=require_video)

    def publish(self, metadata, jpeg=None):
        metadata = dict(metadata, **self.ack)
        # Encode both payloads. Raw full-screen capture is never written anywhere.
        payload = {"metadata.json": base64.b64encode(json.dumps(metadata).encode()).decode()}
        if jpeg is not None:
            payload["frame.jpg"] = base64.b64encode(jpeg).decode()
        code = """import os,base64,pathlib,uuid
p=pathlib.Path('/config/phone_camera_bridge')
assert not p.is_symlink()
p.mkdir(mode=0o700,exist_ok=True)
assert p.resolve()==p and p.is_dir()
os.chmod(p,0o700)
payload=PAYLOAD
def write(name,data):
 target=p/name
 assert not target.is_symlink()
 temp=p/('.incoming-'+uuid.uuid4().hex)
 fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 try:
  with os.fdopen(fd,'wb') as f:
   f.write(base64.b64decode(data));f.flush();os.fsync(f.fileno())
  os.replace(temp,target)
 finally:
  temp.unlink(missing_ok=True)
if 'frame.jpg' in payload:
 write('metadata.json',base64.b64encode(b'{"available":false}').decode())
 write('frame.jpg',payload['frame.jpg'])
write('metadata.json',payload['metadata.json'])
""".replace("PAYLOAD", repr(payload))
        command = "docker exec homeassistant python3 -c " + shlex.quote(code)
        self.run([self.args.utmctl, "exec", self.args.vm, "--cmd", "/bin/sh", "-c", command])

    def capture(self):
        from PIL import Image
        view, crop, _ = self.view()
        started = time.monotonic()
        self.guard()
        raw = self.adb("exec-out", "screencap", "-p")
        self.guard()
        after, after_crop, _ = self.view()
        identity = ("source", "mode", "camera_label", "date")
        if any(view.get(k) != after.get(k) for k in identity) or crop != after_crop or time.monotonic() - started > 16:
            raise UnsafeView("View changed during capture")
        with Image.open(io.BytesIO(raw)) as full:
            if crop[2] > full.width or crop[3] > full.height:
                raise UnsafeView("Video bounds exceed capture")
            image = full.crop(crop).convert("RGB")
        del raw
        output = io.BytesIO()
        image.save(output, "JPEG", quality=60)
        while output.tell() > MAX_JPEG:
            if image.width < 240:
                raise UnsafeView("Snapshot exceeds transport limit")
            image = image.resize((int(image.width * .8), int(image.height * .8)))
            output = io.BytesIO()
            image.save(output, "JPEG", quality=60)
        # Timestamp describes capture, not delayed UI validation/publication.
        stamp = time.time() - (time.monotonic() - started)
        self.publish(dict(view, available=True, control_available=True, timestamp=stamp), output.getvalue())

    def commands(self):
        try:
            raw = self.run([self.args.utmctl, "file", "pull", self.args.vm, GUEST_COMMAND])
        except subprocess.CalledProcessError:
            return
        if len(raw) > 8192:
            return
        try:
            command = json.loads(raw)
            command_id = command["command_id"]
            if not isinstance(command_id, str):
                return
            uuid.UUID(command_id)
            stamp = command["timestamp"]
            if not self.claim(command_id):
                return
            if not isinstance(stamp, (float, int)) or not 0 <= time.time() - stamp <= 20:
                self.ack = {"command_id": command_id, "status": "error"}
                return
        except (ValueError, KeyError, TypeError):
            return
        self.ack = {"command_id": command_id, "status": "error"}
        try:
            before, _, find = self.view(require_video=False)
            resource, mode, date = action_target(command.get("action"), before)
            if resource:
                control = find(resource)
                if control.get("enabled") != "true" or control.get("clickable") != "true":
                    raise UnsafeView("App control is not actionable")
                x1, y1, x2, y2 = bounds(control)
                self.guard()
                self.adb("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))
            deadline = time.monotonic() + 18
            while time.monotonic() < deadline:
                try:
                    after, _, _ = self.view(require_video=False)
                    if after["mode"] == mode and (date is None or after.get("date") == date):
                        self.ack["status"] = "success"
                        return
                except UnsafeView:
                    pass
                time.sleep(.5)
        except (UnsafeView, subprocess.SubprocessError, ET.ParseError):
            pass

    def unavailable(self):
        self.publish({"available": False, "timestamp": time.time()})

    def publish_controls_only(self):
        try:
            view, _, _ = self.view(require_video=False)
        except (UnsafeView, subprocess.SubprocessError, ET.ParseError, OSError, ValueError):
            self.unavailable()
            return
        self.publish(dict(view, available=False, control_available=True, timestamp=time.time()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True, help="ADB executable")
    parser.add_argument("--serial-file", required=True, help="Private JSON containing serial")
    parser.add_argument("--utmctl", required=True, help="UTM CLI executable")
    parser.add_argument("--vm", required=True, help="Explicit UTM VM UUID or complete name")
    parser.add_argument("--once", action="store_true", help="Capture once without reading or executing UI commands")
    args = parser.parse_args()
    # One helper only: two processes must never execute the same date action.
    fd = os.open(args.serial_file + ".hik-bridge.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        print("Phone bridge already running; no second controller started.", flush=True)
        return 0
    bridge = Bridge(args)
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        while True:
            start = time.monotonic()
            try:
                if not args.once:
                    bridge.commands()
                bridge.capture()
                print("Selected-view publication submitted to UTM (guest confirmation required).", flush=True)
            except (UnsafeView, subprocess.SubprocessError, ET.ParseError, OSError, ValueError):
                bridge.publish_controls_only()
                print("Bridge unavailable; no screenshot published.", flush=True)
                if args.once:
                    return 1
            if args.once:
                return 0
            time.sleep(max(0, 4 - (time.monotonic() - start)))
    except KeyboardInterrupt:
        return 0
    finally:
        if not args.once:
            try:
                bridge.unavailable()
            except (OSError, subprocess.SubprocessError):
                print("Unavailable publication failed; HA freshness timeout remains active.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
