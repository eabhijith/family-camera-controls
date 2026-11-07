import importlib.util
import pathlib
import unittest

path=pathlib.Path(__file__).parents[1]/"custom_components/family_camera_control/electronic_ptz.py"
spec=importlib.util.spec_from_file_location("electronic",path)
electronic=importlib.util.module_from_spec(spec)
spec.loader.exec_module(electronic)


class ElectronicTest(unittest.TestCase):
    def test_observed_shape(self):
        p=electronic.build_payload("up",session="0x1",channel=0,pixels=10)
        self.assertEqual(electronic.COMMAND_ID,1402)
        self.assertEqual(p["Name"],"OPElecPTZControl")
        self.assertEqual(p[p["Name"]]["Parameter"]["POINT"],{"PixelsX":0,"PixelsY":10})

    def test_channel_is_explicit(self):
        with self.assertRaises(TypeError):
            electronic.build_payload("left",session="0x1")

    def test_invalid_parameters(self):
        for kwargs in [{"session":""},{"channel":-1},{"channel":True},{"pixels":0},{"pixels":101}]:
            data={"session":"0x1","channel":0,"pixels":10,**kwargs}
            with self.assertRaises(ValueError):electronic.build_payload("left",**data)
