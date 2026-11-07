"""Wrapper behaviour tests with HA interfaces stubbed; not HA integration tests."""
import asyncio
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).parents[1] / "custom_components/family_camera_control"


class HAError(Exception):
    pass


class BaseButton:
    pass


def load_module():
    modules = {
        "homeassistant": types.ModuleType("homeassistant"),
        "homeassistant.components": types.ModuleType("homeassistant.components"),
        "homeassistant.components.button": types.ModuleType("homeassistant.components.button"),
        "homeassistant.exceptions": types.ModuleType("homeassistant.exceptions"),
        "homeassistant.core": types.ModuleType("homeassistant.core"),
        "homeassistant.helpers": types.ModuleType("homeassistant.helpers"),
        "homeassistant.helpers.event": types.ModuleType("homeassistant.helpers.event"),
        "test_controls": types.ModuleType("test_controls"),
    }
    modules["test_controls"].__path__ = [str(ROOT)]
    modules["homeassistant.components.button"].ButtonEntity = BaseButton
    modules["homeassistant.exceptions"].HomeAssistantError = HAError
    modules["homeassistant.core"].callback = lambda function: function
    modules["homeassistant.helpers.event"].async_track_state_change_event = lambda *args: lambda: None
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location("test_controls.button", ROOT / "button.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


module = load_module()


def button(direction, lock=None, state="idle"):
    entry = types.SimpleNamespace(data={"camera_entity": "camera.test"}, entry_id="test", title="Test")
    entity = module.LensButton(entry, direction, lock or asyncio.Lock())
    entity.hass = types.SimpleNamespace(states=types.SimpleNamespace(
        get=lambda _: types.SimpleNamespace(state=state)))
    return entity


class ButtonTest(unittest.IsolatedAsyncioTestCase):
    async def test_success_has_extra_stop(self):
        entity = button("left")
        calls = []
        async def send(data):
            calls.append(data["move_mode"])
        entity._send = send
        await entity.async_press()
        self.assertEqual(calls, ["ContinuousMove", "Stop"])

    async def test_failure_still_stops(self):
        entity = button("right")
        calls = []
        async def send(data):
            calls.append(data["move_mode"])
            if data["move_mode"] != "Stop":
                raise HAError("Simulated device failure")
        entity._send = send
        with self.assertRaises(HAError):
            await entity.async_press()
        self.assertEqual(calls, ["ContinuousMove", "Stop"])

    async def test_overlapping_movement_rejected(self):
        lock = asyncio.Lock()
        await lock.acquire()
        entity = button("up", lock)
        with self.assertRaises(HAError):
            await entity.async_press()
        lock.release()

    async def test_stop_not_blocked_by_movement_lock(self):
        lock = asyncio.Lock()
        await lock.acquire()
        entity = button("stop", lock)
        calls = []
        async def send(data):
            calls.append(data)
        entity._send = send
        await entity.async_press()
        self.assertEqual(calls, [{"move_mode": "Stop"}])
        lock.release()

    async def test_unavailable_camera_rejected(self):
        entity = button("down", state="unavailable")
        with self.assertRaises(HAError):
            await entity.async_press()
