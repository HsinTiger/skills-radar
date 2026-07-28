import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))

from launchd_schedule import build_contract, validate_contract  # noqa: E402


class LaunchdScheduleTests(unittest.TestCase):
    def test_contract_is_daily_taipei_dispatcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = build_contract(root, "/opt/homebrew/bin:/usr/bin:/bin")
            self.assertEqual(contract["StartCalendarInterval"], {"Hour": 8, "Minute": 30})
            self.assertEqual(contract["EnvironmentVariables"]["TZ"], "Asia/Taipei")
            self.assertEqual(contract["EnvironmentVariables"]["SKILLS_RADAR_RUN_CONTEXT"], "launchd")
            self.assertEqual(validate_contract(contract, root), [])

    def test_contract_rejects_wrong_cadence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract = build_contract(root, "/usr/bin:/bin")
            contract["StartCalendarInterval"] = {"Hour": 9, "Minute": 30}
            self.assertIn("StartCalendarInterval must be daily 08:30", validate_contract(contract, root))


if __name__ == "__main__":
    unittest.main()
