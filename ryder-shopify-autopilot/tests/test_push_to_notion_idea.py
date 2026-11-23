import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import common
import push_to_notion_idea as push
from test_notion_topic_intake import PAGE_ID, OTHER_ID, page_fixture


class PushIdeaTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "draft.md"
        self.path.write_text("# A first wallet\n\nCheck the recovery process before you buy a wallet.")
        self.meta = {"title": "A first wallet", "target_keyword": "first wallet",
                     "seo_title": "A first wallet", "meta_description": "Check the recovery process.",
                     "slug": "first-wallet", "hero_alt": "Wallet illustration"}
        self.write_meta()
        self.page = page_fixture()
        self.page["properties"]["Status"]["status"]["name"] = "Drafting"
        self.calls = []
        for target in (common, push):
            mock = patch.object(target, "notion", side_effect=self.notion)
            mock.start()
            self.addCleanup(mock.stop)
        no_network = patch.object(common, "http", side_effect=AssertionError("network forbidden"))
        no_network.start()
        self.addCleanup(no_network.stop)

    def write_meta(self):
        self.path.with_suffix(".meta.json").write_text(json.dumps(self.meta))

    def notion(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if method == "GET":
            return 200, copy.deepcopy(self.page)
        return 200, {"id": PAGE_ID, "url": self.page["url"]}

    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]

    def test_known_page_appends_body_and_seo_then_sets_same_page_idea(self):
        ok, page_id, _ = push.push_idea(self.path, PAGE_ID)
        self.assertTrue(ok)
        self.assertEqual(page_id, PAGE_ID)
        writes = self.writes()
        self.assertEqual([(c[0], c[1]) for c in writes],
                         [("PATCH", f"blocks/{PAGE_ID}/children"), ("PATCH", f"pages/{PAGE_ID}")])
        self.assertIn("SEO metadata", json.dumps(writes[0][2]))
        self.assertEqual(writes[1][2]["properties"]["Status"]["status"]["name"], "Idea")
        self.assertEqual(set(writes[1][2]["properties"]), {"Content name", "Status"})
        for _, _, payload in writes:
            self.assertNotIn("Owner", json.dumps(payload))
            self.assertNotIn("Approved for publishing", json.dumps(payload))
            self.assertNotIn("archived", payload)

    def test_metadata_page_id_is_used_without_explicit_arg(self):
        self.meta["notion_page_id"] = PAGE_ID
        self.write_meta()
        self.assertTrue(push.push_idea(self.path)[0])
        self.assertFalse(any(c[0] == "POST" for c in self.calls))

    def test_local_draft_keeps_create_path(self):
        self.assertTrue(push.push_idea(self.path)[0])
        self.assertEqual(len(self.writes()), 1)
        method, path, payload = self.writes()[0]
        self.assertEqual((method, path), ("POST", "pages"))
        self.assertEqual(payload["parent"], {"database_id": common.NOTION_DB_ID})
        self.assertEqual(payload["properties"]["Status"]["status"]["name"], "Idea")

    def test_missing_metadata_fails_before_any_write(self):
        with patch.object(push, "open", side_effect=[open(self.path), FileNotFoundError()]):
            with self.assertRaises(FileNotFoundError):
                push.push_idea(self.path, PAGE_ID)
        self.assertEqual(self.calls, [])

    def test_editorial_gate_blocks_body_and_metadata_before_writes(self):
        for field in ("body", "title", "meta_description"):
            with self.subTest(field=field):
                if field == "body":
                    self.path.write_text("A seamless wallet.")
                else:
                    self.path.write_text("Check the recovery process before you buy a wallet.")
                    self.meta[field] = "A seamless wallet"
                    self.write_meta()
                self.assertFalse(push.push_idea(self.path, PAGE_ID)[0])
        self.assertEqual(self.calls, [])

    def test_invalid_or_conflicting_id_never_creates_a_page(self):
        for value in ("../users", "", OTHER_ID):
            with self.subTest(value=value):
                self.meta["notion_page_id"] = value
                self.write_meta()
                with self.assertRaises(ValueError):
                    push.push_idea(self.path, PAGE_ID)
        self.assertEqual(self.calls, [])

    def test_human_owned_missing_owner_and_later_workflow_stages_are_blocked(self):
        for stage in ("human", "missing owner", "Approved for publishing", "Published", "In review", "Topic queued"):
            self.page = page_fixture()
            self.page["properties"]["Status"]["status"]["name"] = "Drafting"
            with self.subTest(stage=stage):
                if stage == "human":
                    self.page["properties"]["Owner"]["people"] = [{"id": "synthetic-human"}]
                elif stage == "missing owner":
                    del self.page["properties"]["Owner"]
                else:
                    self.page["properties"]["Status"]["status"]["name"] = stage
                with self.assertRaises(ValueError):
                    push.push_idea(self.path, PAGE_ID)
        self.assertEqual(self.writes(), [])

    def test_wrong_calendar_and_archived_pages_are_blocked(self):
        self.page["parent"]["database_id"] = OTHER_ID
        with self.assertRaises(ValueError):
            push.push_idea(self.path, PAGE_ID)
        self.page["parent"]["database_id"] = common.NOTION_DB_ID
        self.page["archived"] = True
        with self.assertRaises(ValueError):
            push.push_idea(self.path, PAGE_ID)
        self.assertEqual(self.writes(), [])

    def test_append_failure_does_not_set_idea_or_echo_response(self):
        with patch.object(push, "notion", return_value=(400, {"error": "sensitive response"})) as call:
            ok, _, info = push.push_idea(self.path, PAGE_ID)
        self.assertFalse(ok)
        self.assertNotIn("sensitive", info)
        self.assertEqual(call.call_count, 1)
        self.assertIn("blocks/", call.call_args.args[1])

    def test_owner_change_after_body_stops_status_update(self):
        def append_then_claim(method, path, payload=None):
            result = self.notion(method, path, payload)
            self.page["properties"]["Owner"]["people"] = [{"id": "synthetic-human"}]
            return result
        with patch.object(push, "notion", side_effect=append_then_claim), self.assertRaises(ValueError):
            push.push_idea(self.path, PAGE_ID)
        self.assertEqual(len(self.writes()), 1)
        self.assertEqual(self.writes()[0][1], f"blocks/{PAGE_ID}/children")

    def test_long_existing_page_upload_batches_before_idea(self):
        blocks = [{"type": "paragraph", "paragraph": {"rich_text": []}}] * 105
        with patch.object(push, "md_to_blocks", return_value=blocks):
            self.assertTrue(push.push_idea(self.path, PAGE_ID)[0])
        writes = self.writes()
        self.assertEqual([len(c[2]["children"]) for c in writes[:-1]], [100, 6])
        self.assertEqual(writes[-1][1], f"pages/{PAGE_ID}")


if __name__ == "__main__":
    unittest.main()
