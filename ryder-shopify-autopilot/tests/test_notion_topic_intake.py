import contextlib
import copy
import datetime as dt
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import common
import notion_topic_intake as intake

TODAY = dt.date(2026, 11, 24)
PAGE_ID = "11111111-1111-4111-8111-111111111111"
OTHER_ID = "22222222-2222-4222-8222-222222222222"


def page_fixture():
    return json.loads((ROOT / "tests/fixtures/notion_topic.synthetic.json").read_text())


def research_fixture(volume=0):
    return {"schema_version": 1, "country": "US", "language": "en",
            "collected_on": TODAY.isoformat(), "providers": ["DataForSEO"],
            "metric_sources": {"d4s": "Synthetic test metrics"},
            "rows": [{"keyword": "first hardware wallet", "d4s_volume": volume,
                      "ahrefs_volume": None, "d4s_difficulty": None, "ahrefs_difficulty": None}]}


def reviewed_fixture(page):
    topic = intake.map_page(page)
    topic["product_fit"] = {"verified": True, "verified_by": "Synthetic test reviewer",
                            "verified_on": TODAY.isoformat(), "rationale": "Synthetic buyer fit"}
    topic["serp"] = {"intent_match": True, "country": "US", "reviewed_on": TODAY.isoformat(),
                     "source_url": "https://example.com/test-serp", "notes": "Synthetic SERP review"}
    topic["existing_coverage"]["checked_on"] = TODAY.isoformat()
    return {"schema_version": 1, "topics": [topic]}


class NotionIntakeTests(unittest.TestCase):
    def setUp(self):
        self.page = page_fixture()
        self.calls = []
        for target in (common, intake):
            mock = patch.object(target, "notion", side_effect=self.notion)
            mock.start()
            self.addCleanup(mock.stop)
        no_network = patch.object(common, "http", side_effect=AssertionError("network forbidden"))
        no_network.start()
        self.addCleanup(no_network.stop)
        paid = patch.object(intake.subprocess, "run", side_effect=AssertionError("paid research forbidden"))
        self.paid = paid.start()
        self.addCleanup(paid.stop)

    def notion(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if path.startswith("databases/"):
            return 200, {"results": [copy.deepcopy(self.page)], "has_more": False}
        if method == "GET":
            return 200, copy.deepcopy(self.page)
        if path == "pages/" + PAGE_ID:
            self.page["properties"].update(payload["properties"])
        return 200, {"id": PAGE_ID, "url": self.page["url"]}

    def run_intake(self, **kwargs):
        return intake.run_intake(today=TODAY, **kwargs)

    def writes(self):
        return [c for c in self.calls if c[0] == "PATCH"]

    def test_mapping_recovers_autolinked_evidence_without_invented_reviews(self):
        topic = intake.map_page(self.page)
        self.assertEqual(topic["keyword"], "first hardware wallet")
        self.assertEqual(topic["notion_page_id"], PAGE_ID)
        self.assertEqual(topic["evidence"][0]["source_url"], "https://example.com/wallet_guide")
        self.assertEqual(topic["evidence"][0]["checked_on"], TODAY.isoformat())
        self.assertEqual(topic["existing_coverage"]["source"], self.page["url"])
        for key in ("product_fit", "serp", "X likes", "Owner"):
            self.assertNotIn(key, topic)
        self.assertNotIn("checked_on", topic["existing_coverage"])

    def test_plain_json_autolinks_and_bad_evidence(self):
        self.assertEqual(intake.parse_evidence('[{"source_url":"[source](https://example.com/a_b)"}]'),
                         [{"source_url": "https://example.com/a_b"}])
        for value in ("not json", '["bad"]'):
            with self.assertRaises(ValueError):
                intake.parse_evidence(value)

    def test_queue_paginates_and_prefers_blog(self):
        other = copy.deepcopy(self.page)
        other["id"] = OTHER_ID
        other["properties"]["Content type"]["multi_select"] = []
        with patch.object(intake, "notion", side_effect=[
            (200, {"results": [other], "has_more": True, "next_cursor": "next"}),
            (200, {"results": [self.page], "has_more": False}),
        ]) as call:
            rows = intake.queued_pages()
        self.assertEqual([p["id"] for p in rows], [PAGE_ID, OTHER_ID])
        self.assertEqual(call.call_args_list[0].args[1], f"databases/{common.NOTION_DB_ID}/query")
        self.assertEqual(call.call_args_list[0].args[2]["filter"]["status"]["equals"], "Topic queued")
        self.assertEqual(call.call_args_list[1].args[2]["start_cursor"], "next")

    def test_dry_run_plans_without_paid_research_or_writes(self):
        result = self.run_intake(dry_run=True)
        self.assertEqual(result["candidates"]["schema_version"], 1)
        self.assertEqual(result["planned_keyword_research_calls"][0][-3:],
                         ["overview", "first hardware wallet", "--json"])
        self.assertEqual(result["planned_status_writes"][0]["status"], "Research needed")
        self.assertEqual(result["decisions"][0]["decision"], "research_needed")
        self.assertTrue(any("product fit" in r for r in result["decisions"][0]["reasons"]))
        self.assertIsNone(result["decisions"][0]["metrics"])
        self.assertEqual(self.writes(), [])
        self.paid.assert_not_called()

    def test_dry_run_explicit_research_still_never_writes(self):
        self.paid.side_effect = None
        self.paid.return_value = subprocess.CompletedProcess([], 0, json.dumps(research_fixture(None)))
        result = self.run_intake(dry_run=True, research_in_dry_run=True)
        self.paid.assert_called_once()
        self.assertIsNone(result["research"]["rows"][0]["d4s_volume"])
        self.assertEqual(self.writes(), [])

    def test_live_unknown_volume_runs_existing_json_command(self):
        self.paid.side_effect = None
        self.paid.return_value = subprocess.CompletedProcess([], 0, json.dumps(research_fixture()))
        result = self.run_intake()
        self.paid.assert_called_once()
        self.assertEqual(result["research"]["country"], "US")
        self.assertEqual(self.page["properties"]["Status"]["status"]["name"], "Research needed")

    def test_measured_zero_reused_and_only_status_written(self):
        result = self.run_intake(research=research_fixture())
        self.paid.assert_not_called()
        self.assertEqual(result["decisions"][0]["metrics"]["d4s"]["volume"], 0)
        for method, path, payload in self.writes():
            if path.startswith("pages/"):
                self.assertEqual(set(payload["properties"]), {"Status"})
            self.assertNotIn("Owner", json.dumps(payload))
            self.assertNotIn("Approved for publishing", json.dumps(payload))

    def test_human_owned_and_unknown_owner_skipped(self):
        for owner in ({"type": "people", "people": [{"id": "synthetic-human"}]},
                      {"type": "people"}, {"type": "rich_text", "rich_text": []}, None):
            with self.subTest(owner=owner):
                self.page["properties"]["Owner"] = owner
                result = self.run_intake(dry_run=True)
                self.assertEqual(result["candidates"]["topics"], [])
                self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(self.writes(), [])

    def test_failed_owner_lookup_is_closed(self):
        with patch.object(common, "notion", return_value=(403, {})):
            ok, _ = common.notion_page_owners(PAGE_ID)
            self.assertFalse(ok)
            result = self.run_intake(dry_run=True)
            self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(self.writes(), [])

    def test_reject_archives_status_without_deleting_page(self):
        self.page["properties"]["persona"]["select"]["name"] = "power_user"
        result = self.run_intake(research=research_fixture())
        self.assertEqual(result["decisions"][0]["decision"], "reject")
        self.assertEqual(self.page["properties"]["Status"]["status"]["name"], "Archived")
        self.assertTrue(all(c[0] in ("GET", "POST", "PATCH") for c in self.calls))
        self.assertFalse(any("archived" in (c[2] or {}) for c in self.calls))

    def test_existing_article_stays_research_with_refresh_note(self):
        self.page["properties"]["existing_coverage_status"]["select"]["name"] = "existing"
        self.page["properties"]["existing_coverage_url"]["url"] = "https://example.com/existing"
        result = self.run_intake(candidates=reviewed_fixture(self.page), research=research_fixture())
        self.assertEqual(result["decisions"][0]["decision"], "update_existing")
        self.assertEqual(result["planned_status_writes"][0]["status"], "Research needed")
        self.assertIn("do not draft a duplicate", result["planned_status_writes"][0]["note"])

    def test_brief_requires_explicit_claim_to_start_drafting(self):
        candidates = reviewed_fixture(self.page)
        result = self.run_intake(candidates=candidates, research=research_fixture())
        self.assertEqual(result["decisions"][0]["decision"], "draft_brief")
        self.assertIsNone(result["planned_status_writes"][0]["status"])
        self.assertEqual(self.page["properties"]["Status"]["status"]["name"], "Topic queued")
        self.run_intake(candidates=candidates, research=research_fixture(), claim=PAGE_ID)
        self.assertEqual(self.page["properties"]["Status"]["status"]["name"], "Drafting")

    def test_reviewer_can_discover_existing_coverage_without_new_notion_properties(self):
        candidates = reviewed_fixture(self.page)
        candidates["topics"][0]["existing_coverage"].update(
            status="existing", url="https://example.com/discovered-article")
        result = self.run_intake(candidates=candidates, research=research_fixture())
        self.assertEqual(result["decisions"][0]["decision"], "update_existing")
        self.assertIn("https://example.com/discovered-article", result["planned_status_writes"][0]["note"])
        self.assertEqual(result["planned_status_writes"][0]["status"], "Research needed")

    def test_review_cannot_erase_fresh_existing_coverage(self):
        candidates = reviewed_fixture(self.page)
        self.page["properties"]["existing_coverage_status"]["select"]["name"] = "existing"
        self.page["properties"]["existing_coverage_url"]["url"] = "https://example.com/existing"
        with self.assertRaises(ValueError):
            self.run_intake(candidates=candidates, research=research_fixture(), claim=PAGE_ID)
        self.assertEqual(self.writes(), [])

    def test_claim_rejects_missing_reviews_synthetic_and_changed_keyword(self):
        for change in ("no reviews", "synthetic candidates", "synthetic research", "changed keyword"):
            with self.subTest(change=change):
                self.page = page_fixture()
                candidates, research = reviewed_fixture(self.page), research_fixture()
                if change == "no reviews":
                    del candidates["topics"][0]["serp"]
                elif change == "synthetic candidates":
                    candidates["synthetic_example"] = True
                elif change == "synthetic research":
                    research["synthetic_example"] = True
                else:
                    candidates["topics"][0]["keyword"] = "different keyword"
                with self.assertRaises(ValueError):
                    self.run_intake(candidates=candidates, research=research, claim=PAGE_ID)
        self.assertEqual(self.writes(), [])

    def test_fresh_owner_or_status_change_stops_before_note(self):
        for change in ("owner", "status"):
            self.page = page_fixture()
            with self.subTest(change=change):
                original_select = intake.select
                def changed_select(*args, **kwargs):
                    result = original_select(*args, **kwargs)
                    if args[0].get("topics") and args[1:] and args[1] is not None:
                        if change == "owner":
                            self.page["properties"]["Owner"]["people"] = [{"id": "human"}]
                        else:
                            self.page["properties"]["Status"]["status"]["name"] = "In review"
                    return result
                with patch.object(intake, "select", side_effect=changed_select), self.assertRaises(ValueError):
                    self.run_intake(research=research_fixture())
        self.assertEqual(self.writes(), [])

    def test_malformed_evidence_needs_research_without_provider_call(self):
        self.page["properties"]["evidence"]["rich_text"] = [{"plain_text": "not json"}]
        result = self.run_intake()
        self.assertEqual(result["candidates"]["topics"], [])
        self.assertEqual(result["planned_status_writes"][0]["status"], "Research needed")
        self.paid.assert_not_called()

    def test_approval_status_is_not_an_intake_target(self):
        result = {"decision": "research_needed", "reasons": [], "score_kind": "test"}
        with self.assertRaises(ValueError):
            intake.write_decision(PAGE_ID, result, "Approved for publishing")
        self.assertEqual(self.writes(), [])

    def test_cli_output_is_candidates_json_and_dry_run_only_reads(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(intake, "load_env") as load:
            output = Path(tmp) / "topics.json"
            with patch.object(sys, "argv", ["intake", "--dry-run", "--output", str(output)]), \
                 contextlib.redirect_stdout(io.StringIO()):
                intake.main()
            self.assertEqual(json.loads(output.read_text())["topics"][0]["notion_page_id"], PAGE_ID)
            load.assert_called_once_with(required_keys=("NOTION_API_KEY",))
        self.assertEqual(self.writes(), [])


if __name__ == "__main__":
    unittest.main()
