"""HA entity-interface stubs, not a running Home Assistant instance."""
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).parents[1] / "custom_components/hikvision_dvr_status"


class CoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator

    @property
    def available(self):
        return self.coordinator.last_update_success


def load():
    names = ("homeassistant", "homeassistant.components", "homeassistant.components.sensor",
             "homeassistant.helpers", "homeassistant.helpers.entity",
             "homeassistant.helpers.update_coordinator", "fixture_dvr")
    modules = {name: types.ModuleType(name) for name in names}
    modules["homeassistant.components.sensor"].SensorEntity = type("SensorEntity", (), {})
    modules["homeassistant.helpers.entity"].EntityCategory = types.SimpleNamespace(DIAGNOSTIC="diagnostic")
    modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = CoordinatorEntity
    modules["fixture_dvr"].__path__ = [str(ROOT)]
    modules["fixture_dvr"].DOMAIN = "hikvision_dvr_status"
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location("fixture_dvr.sensor", ROOT / "sensor.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


sensor = load()


class SensorTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.entry = types.SimpleNamespace(entry_id="fixture", unique_id="fixture-serial", title="DVR")
        self.coordinator = types.SimpleNamespace(data={"camera_count": 4, "storage_status": "ok"},
                                                 last_update_success=True)

    async def test_setup_creates_both_entities(self):
        entities = []
        hass = types.SimpleNamespace(data={"hikvision_dvr_status": {"fixture": self.coordinator}})
        await sensor.async_setup_entry(hass, self.entry, entities.extend)
        self.assertEqual([entity.native_value for entity in entities], [4, "ok"])
        self.assertTrue(all(entity.available for entity in entities))
        self.assertEqual(len({entity._attr_unique_id for entity in entities}), 2)

    async def test_missing_endpoint_is_unavailable(self):
        self.coordinator.data["storage_status"] = None
        entity = sensor.DVRStatus(self.coordinator, self.entry, "storage_status", "disk", "mdi:harddisk")
        self.assertFalse(entity.available)
        self.assertIsNone(entity.native_value)

    async def test_failed_update_hides_stale_value(self):
        entity = sensor.DVRStatus(self.coordinator, self.entry, "camera_count", "cameras", "mdi:cctv")
        self.coordinator.last_update_success = False
        self.assertFalse(entity.available)
