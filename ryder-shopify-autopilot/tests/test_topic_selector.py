import copy
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from topic_selector import select

TODAY = dt.date(2026, 10, 7)


def fixture(name):
    return json.loads((ROOT / "examples" / name).read_text())


class TopicSelectorTests(unittest.TestCase):
    def setUp(self):
        self.candidates = fixture("topics.synthetic.json")
        self.research = fixture("research.synthetic.json")

    def decisions(self):
        return {d["keyword"]: d for d in
                select(self.candidates, self.research, TODAY)["decisions"]}

    def test_buyer_brief_beats_high_volume_mismatch(self):
        decisions = self.decisions()
        buyer = decisions["move bitcoin from exchange to hardware wallet"]
        bot = decisions["crypto trading bot signals"]
        self.assertEqual(buyer["decision"], "draft_brief")
        self.assertEqual(bot["decision"], "reject")
        self.assertGreater(bot["metrics"]["d4s"]["volume"],
                           buyer["metrics"]["d4s"]["volume"])
        self.assertEqual(buyer["brief"]["buyer_question"],
                         self.candidates["topics"][0]["buyer_question"])

    def test_existing_coverage_routes_to_update_and_zero_is_observed(self):
        item = self.decisions()["how to set up a hardware wallet"]
        self.assertEqual(item["decision"], "update_existing")
        self.assertEqual(item["metrics"]["ahrefs"]["volume"], 0)
        self.assertEqual(item["existing_url"],
                         "https://ryder.id/blogs/post/example-existing-guide")

    def test_unknown_research_does_not_become_zero(self):
        item = self.decisions()["hardware wallet recovery checklist"]
        self.assertEqual(item["decision"], "research_needed")
        self.assertIsNone(item["metrics"]["d4s"]["volume"])
        self.assertIn("search volume missing from both providers", item["reasons"])

    def test_provenance_and_review_gates(self):
        self.research["country"] = "GB"
        result = select(self.candidates, self.research, TODAY)
        self.assertTrue(result["synthetic_example"])
        self.assertEqual(result["research_provenance"]["country"], "GB")
        item = {d["keyword"]: d for d in result["decisions"]}[
            "move bitcoin from exchange to hardware wallet"]
        self.assertNotEqual(item["decision"], "draft_brief")
        self.assertIn("research country must be US", item["reasons"])

    def test_stale_reviews_require_research(self):
        self.candidates["topics"][0]["product_fit"]["verified_on"] = "2026-01-01"
        item = self.decisions()["move bitcoin from exchange to hardware wallet"]
        self.assertEqual(item["decision"], "research_needed")
        self.assertTrue(any("product fit" in reason for reason in item["reasons"]))

    def test_wrong_language_and_missing_source_hold_briefs(self):
        self.research["language"] = "de"
        self.research["metric_sources"] = {}
        item = self.decisions()["move bitcoin from exchange to hardware wallet"]
        self.assertEqual(item["decision"], "research_needed")
        self.assertIn("research language must be en", item["reasons"])
        self.assertIn("research source missing for d4s", item["reasons"])

    def test_missing_evidence_blocks_brief(self):
        self.candidates["topics"][0]["evidence"] = []
        self.assertEqual(self.decisions()["move bitcoin from exchange to hardware wallet"]["decision"],
                         "research_needed")

    def test_non_url_evidence_blocks_brief(self):
        self.candidates["topics"][0]["evidence"][0]["source_url"] = "notes only"
        self.assertEqual(self.decisions()["move bitcoin from exchange to hardware wallet"]["decision"],
                         "research_needed")

    def test_invalid_nested_schema_is_readable_error(self):
        self.candidates["topics"][0]["serp"] = ["bad"]
        with self.assertRaisesRegex(ValueError, "must be objects"):
            select(self.candidates, self.research, TODAY)
        with self.assertRaisesRegex(ValueError, "research must be an object"):
            select(fixture("topics.synthetic.json"), [], TODAY)

    def test_invalid_metrics_and_duplicates_fail(self):
        research = copy.deepcopy(self.research)
        research["rows"][0]["d4s_volume"] = -1
        with self.assertRaisesRegex(ValueError, "invalid d4s volume"):
            select(self.candidates, research, TODAY)
        research = copy.deepcopy(self.research)
        research["rows"].append(copy.deepcopy(research["rows"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate research keyword"):
            select(self.candidates, research, TODAY)


if __name__ == "__main__":
    unittest.main()
