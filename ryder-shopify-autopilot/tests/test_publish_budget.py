import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import publish_budget as pb

TODAY = dt.date(2026, 12, 10)


def day(n):
    return (TODAY - dt.timedelta(days=n)).isoformat()


class PublishBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.watch = Path(self.tmp.name, "watch.json")
        self.log = Path(self.tmp.name, "log.json")
        self._orig = (pb.WATCH_FILE, pb.PUBLISH_LOG, pb.DAILY_CAP)
        pb.WATCH_FILE, pb.PUBLISH_LOG, pb.DAILY_CAP = str(self.watch), str(self.log), 4

    def tearDown(self):
        pb.WATCH_FILE, pb.PUBLISH_LOG, pb.DAILY_CAP = self._orig
        self.tmp.cleanup()

    def write(self, watch, log):
        self.watch.write_text(json.dumps(watch))
        self.log.write_text(json.dumps(log))

    def posts(self, indexed, stuck, age=10):
        watch, log = [], []
        for i in range(indexed + stuck):
            slug = f"post-{i}"
            state = "Submitted and indexed" if i < indexed else "Crawled - currently not indexed"
            watch.append({"slug": slug, "added": day(age), "coverage_state": state})
            log.append({"slug": slug, "date": day(age)})
        return watch, log

    def test_normal_pace_counts_today(self):
        watch, log = self.posts(10, 0)
        log += [{"slug": "a", "date": TODAY.isoformat()},
                {"slug": "b", "date": TODAY.isoformat()}]
        self.write(watch, log)
        b = pb.budget(TODAY)
        self.assertEqual((b["cap"], b["published_today"], b["remaining_today"]), (4, 2, 2))

    def test_brake_slows_to_one(self):
        self.write(*self.posts(6, 2))
        self.assertEqual(pb.budget(TODAY)["cap"], 1)

    def test_pause_at_half_unindexed(self):
        self.write(*self.posts(3, 3))
        self.assertEqual(pb.budget(TODAY)["cap"], 0)

    def test_single_stuck_post_does_not_brake(self):
        self.write(*self.posts(1, 1))
        self.assertEqual(pb.budget(TODAY)["cap"], 4)

    def test_recent_posts_are_not_judged_yet(self):
        self.write(*self.posts(0, 5, age=3))
        self.assertEqual(pb.budget(TODAY)["cap"], 4)

    def test_unpublished_watch_entries_ignored(self):
        watch, _ = self.posts(0, 4)
        self.write(watch, [])
        self.assertEqual(pb.budget(TODAY)["cap"], 4)

    def test_record_publish_appends(self):
        self.write([], [])
        pb.record_publish("x", "X")
        self.assertEqual(json.loads(self.log.read_text())[-1]["slug"], "x")


if __name__ == "__main__":
    unittest.main()
