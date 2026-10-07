import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import keyword_research
import common


class ResearchJsonTests(unittest.TestCase):
    def test_optional_research_env_but_publisher_still_requires_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            common.load_env(path="/path/that/does/not/exist", required_keys=())
            with self.assertRaisesRegex(SystemExit, "SHOPIFY_SHOP"):
                common.load_env(path="/path/that/does/not/exist")
            rows, notes = keyword_research.research("matching", "test wallet")
        self.assertEqual(rows, [])
        self.assertTrue(any("no credentials" in note for note in notes))

    def test_json_keeps_zero_null_source_and_notes(self):
        rows = [{"keyword": "test wallet", "d4s_volume": 0,
                 "d4s_difficulty": 20}]
        output = io.StringIO()
        with patch.object(keyword_research, "load_env") as load, \
             patch.object(keyword_research, "research", return_value=(rows, ["ahrefs: no credentials, skipped"])), \
             patch.object(sys, "argv", ["keyword_research.py", "matching", "test wallet", "--json"]), \
             contextlib.redirect_stdout(output):
            keyword_research.main()
        load.assert_called_once_with(required_keys=())
        doc = json.loads(output.getvalue())
        self.assertEqual(doc["country"], "US")
        self.assertEqual(doc["providers"], ["DataForSEO"])
        self.assertEqual(doc["rows"][0]["d4s_volume"], 0)
        self.assertIsNone(doc["rows"][0]["ahrefs_volume"])
        self.assertIn("ahrefs: no credentials, skipped", doc["notes"])


if __name__ == "__main__":
    unittest.main()
