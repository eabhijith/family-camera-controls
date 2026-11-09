"""Camera interface regression checks; actual HA integration is tested separately."""
import enum
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch


class Features(enum.IntFlag):
    STREAM = 2


class Camera:
    async def async_added_to_hass(self):
        pass

    def async_on_remove(self, callback):
        self.remove_callback = callback

    def async_write_ha_state(self):
        pass


def load():
    root = pathlib.Path(__file__).parents[1] / "custom_components/hikconnect_phone_bridge"
    names = ("homeassistant", "homeassistant.components", "homeassistant.components.camera",
             "homeassistant.helpers", "homeassistant.helpers.dispatcher", "phone_fixture")
    modules = {name: types.ModuleType(name) for name in names}
    modules["homeassistant.components.camera"].Camera = Camera
    modules["homeassistant.components.camera"].CameraEntityFeature = Features
    modules["homeassistant.helpers.dispatcher"].async_dispatcher_connect = lambda *args: lambda: None
    modules["phone_fixture"].DOMAIN = "hikconnect_phone_bridge"
    modules["phone_fixture"].__path__ = [str(root)]
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location("phone_fixture.camera", root / "camera.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


module = load()


class CameraTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bridge = types.SimpleNamespace(available=True, metadata={"mode": "Playback", "date": "2026/11/07"},
                                            refresh=AsyncMock(), image=AsyncMock(return_value=b"jpeg"))
        self.entity = module.PhoneCamera(self.bridge)
        self.entity.hass = object()

    async def test_typed_feature_flag_not_plain_integer(self):
        self.assertIsInstance(self.entity._attr_supported_features, Features)
        self.assertEqual(int(self.entity._attr_supported_features), 0)

    async def test_private_snapshot_and_metadata(self):
        self.assertEqual(await self.entity.async_camera_image(), b"jpeg")
        self.assertEqual(self.entity.extra_state_attributes["mode"], "Playback")

    async def test_lifecycle_and_unavailable_state(self):
        await self.entity.async_added_to_hass()
        self.assertTrue(callable(self.entity.remove_callback))
        self.bridge.available = False
        self.assertFalse(self.entity.available)
