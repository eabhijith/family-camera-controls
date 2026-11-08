import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).parents[1] / "custom_components/family_camera_control/netapi_ptz.py"
spec = importlib.util.spec_from_file_location("netapi", path)
netapi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(netapi)


class NetApiTest(unittest.TestCase):
    def test_observed_nested_shape(self):
        payload = netapi.build_multi_ptz_subtree(channel=2, command="StepLeft")
        self.assertEqual(payload, {"IPCam": {"NetAPI": {"R/MultiPTZ/Control": {
            "Chn": 2, "Cmd": "StepLeft", "Arg": 1, "Arg2": 0,
        }}}})

    def test_path_is_one_key_not_nested_url_parts(self):
        tree = netapi.build_multi_ptz_subtree(channel=0, command="Stop")["IPCam"]["NetAPI"]
        self.assertEqual(list(tree), ["R/MultiPTZ/Control"])

    def test_reject_invalid_channels(self):
        for channel in [-1, 32, True, 0.5, "0"]:
            with self.assertRaises(ValueError):
                netapi.build_multi_ptz_subtree(channel=channel, command="Stop")

    def test_reject_continuous_or_unknown_commands(self):
        for command in ["MoveUp", "MoveLeft", "Reset", "", None]:
            with self.assertRaises(ValueError):
                netapi.build_multi_ptz_subtree(channel=0, command=command)
