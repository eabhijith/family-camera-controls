import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).parents[1] / "custom_components/family_camera_control/policy.py"
spec = importlib.util.spec_from_file_location("policy", path)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTest(unittest.TestCase):
    def test_directions(self):
        for direction, (axis, value) in policy.DIRECTIONS.items():
            data = policy.movement_data(direction)
            self.assertEqual(data[axis], value)
            self.assertEqual(data["move_mode"], "ContinuousMove")
            self.assertGreater(data["continuous_duration"], 0)
            self.assertLessEqual(data["continuous_duration"], 0.5)

    def test_stop_has_no_motion(self):
        self.assertEqual(policy.movement_data("stop"), {"move_mode": "Stop"})

    def test_reject_unverified_lens(self):
        with self.assertRaises(ValueError):
            policy.movement_data("top")

    def test_invalid_duration(self):
        for duration in [0, -1, 1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                policy.movement_data("left", duration=duration)

    def test_invalid_coefficient(self):
        for coefficient in [0, -1, 2, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                policy.movement_data("left", coefficient=coefficient)
