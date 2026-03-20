import unittest
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from hopaoems.ai_engine.tools import _handle_fabric_units

class TestFabricConversion(unittest.TestCase):
    def test_inch_to_mm(self):
        args = {"width_inch": 58}
        width_mm, weight_gyd = _handle_fabric_units(args)
        self.assertEqual(width_mm, 1473.2) # 58 * 25.4

    def test_gsm_to_gyd(self):
        # 340 GSM, 58 inch width
        # width_m = 58 * 0.0254 = 1.4732
        # g/yd = 340 * 1.4732 * 0.9144 = 458.016... -> 458.0
        args = {"width_inch": 58, "weight_gsm": 340}
        width_mm, weight_gyd = _handle_fabric_units(args)
        self.assertEqual(width_mm, 1473.2)
        self.assertEqual(weight_gyd, 458.0)

    def test_weight_only_no_conversion(self):
        # Without width, GSM cannot be converted to g/yd reliably
        args = {"weight_gsm": 340}
        width_mm, weight_gyd = _handle_fabric_units(args)
        self.assertIsNone(width_mm)
        self.assertIsNone(weight_gyd)

    def test_use_existing_width_for_conversion(self):
        # User only gives GSM, but we have existing width_mm
        args = {"weight_gsm": 340}
        existing = {"width_mm": 1473.2}
        width_mm, weight_gyd = _handle_fabric_units(args, existing)
        self.assertEqual(width_mm, 1473.2)
        self.assertEqual(weight_gyd, 458.0)

if __name__ == '__main__':
    unittest.main()
