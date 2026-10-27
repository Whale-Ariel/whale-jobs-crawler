# -*- coding: utf-8 -*-
"""tencent_source 单元测试：字段映射、增量/全量抓取只入本地队列（不推云库）。"""
import json
import os
import tempfile
import unittest
from unittest import mock

from crawler import paths
from crawler.core import state as state_store
from crawler.sources.tencent import client as tencent_source
from crawler.sources.tencent.client import PAGE_SIZE, parse_post
from crawler.sync.push import COLUMNS
from crawler.core.queue import PendingQueue


def sample_post(pid):
    return {
        "PostId": pid, "RecruitPostName": f"工程师-{pid}", "BGName": "IEG",
        "CategoryName": "研发", "ProductName": "QQ", "Responsibility": "负责",
        "RequireWorkYearsName": "3年以上", "LocationName": "深圳",
        "CountryName": "CN", "PostURL": f"https://careers.tencent.com/job.html?pid={pid}",
        "LastUpdateTime": "2026年10月22日", "IsValid": 1, "RecruitPostId": pid + 100000,
    }


class ParsePostTest(unittest.TestCase):
    def test_mapping(self):
        row = parse_post(sample_post(999), "society")
        self.assertEqual(set(row.keys()), set(COLUMNS))
        self.assertEqual(row["job_id"], "999")
        self.assertEqual(row["department_id"], "IEG")
        self.assertEqual(row["job_category_name"], "研发")
        self.assertEqual(row["city_name"], "深圳")
        self.assertEqual(row["city_code"], "CN")
        self.assertEqual(row["job_code"], "QQ")
        self.assertTrue(row["job_hot_flag"])
        self.assertTrue(row["publish_time"].startswith("2026-10-22"))
        self.assertEqual(row["source"], "tencent")

    def test_bad_date_returns_none(self):
        post = sample_post(1)
        post["LastUpdateTime"] = "不认识的格式"
        self.assertIsNone(parse_post(post, "campus")["publish_time"])


class RunTestBase(unittest.TestCase):
    def _setup_dirs(self, d):
        state_dir, out_dir = os.path.join(d, "state"), os.path.join(d, "output")
        os.makedirs(state_dir)
        os.makedirs(out_dir)
        return state_dir, out_dir


class RunIncrementalTest(RunTestBase, unittest.TestCase):
    def test_new_posts_enqueued_not_pushed(self):
        with tempfile.TemporaryDirectory() as d:
            state_dir, out_dir = self._setup_dirs(d)

            def fake_fetch(portal, page, retries=4, page_size=50):
                return {"Count": 3, "Posts": [sample_post(1), sample_post(2), sample_post(3)]}

            with mock.patch.object(paths, "STATE_DIR", state_dir), \
                 mock.patch.object(paths, "OUTPUT_DIR", out_dir):
                with mock.patch.object(tencent_source, "fetch_page",
                                       side_effect=fake_fetch), \
                     mock.patch.object(tencent_source.time, "sleep"):
                    q = PendingQueue(os.path.join(d, "q.db"))
                    summary = tencent_source.run("society", full=False,
                                                  max_pages_incremental=5, queue=q)
                # 首页 3 条 < PAGE_SIZE(50) → 停止；3 条入队
                self.assertEqual(summary["new_rows"], 3)
                self.assertEqual(summary["queued"], 3)
                self.assertEqual(summary["portal"], "tencent-society")
                self.assertEqual(q.pending_count("tencent"), 3)
                self.assertEqual(state_store.load_known_ids("tencent_society"),
                                 {"1", "2", "3"})
                with open(os.path.join(out_dir,
                                       "tencent_society_last_run_summary.json"),
                          encoding="utf-8") as f:
                    self.assertEqual(json.load(f)["queued"], 3)

    def test_no_new_posts_no_enqueue(self):
        with tempfile.TemporaryDirectory() as d:
            state_dir, out_dir = self._setup_dirs(d)
            with mock.patch.object(paths, "STATE_DIR", state_dir), \
                 mock.patch.object(paths, "OUTPUT_DIR", out_dir):
                state_store.save_known_ids("tencent_campus", {"7", "8"})

                def fake_fetch(portal, page, retries=4, page_size=50):
                    return {"Count": 2, "Posts": [sample_post(7), sample_post(8)]}

                with mock.patch.object(tencent_source, "fetch_page",
                                       side_effect=fake_fetch), \
                     mock.patch.object(tencent_source.time, "sleep"):
                    q = PendingQueue(os.path.join(d, "q.db"))
                    summary = tencent_source.run("campus", full=False, queue=q)
                self.assertEqual(summary["new_rows"], 0)
                self.assertEqual(q.pending_count(), 2)


class RunFullTest(RunTestBase, unittest.TestCase):
    def test_full_with_resume(self):
        total = 120
        with tempfile.TemporaryDirectory() as d:
            state_dir, out_dir = self._setup_dirs(d)
            with mock.patch.object(paths, "STATE_DIR", state_dir), \
                 mock.patch.object(paths, "OUTPUT_DIR", out_dir):
                # 模拟上次全量中断在第 2 页
                state_store.save_progress("tencent_society", 2)

                def fake_fetch(portal, page, retries=4, page_size=50):
                    if page == 2:
                        posts = [sample_post(i) for i in range(51, 101)]
                    else:
                        posts = [sample_post(i) for i in range(101, 121)]
                    return {"Count": total, "Posts": posts}

                with mock.patch.object(tencent_source, "fetch_page",
                                       side_effect=fake_fetch), \
                     mock.patch.object(tencent_source.time, "sleep"):
                    q = PendingQueue(os.path.join(d, "q.db"))
                    summary = tencent_source.run("society", full=True, queue=q)
                # 从第 2 页续传：50 + 20 = 70 条入队
                self.assertEqual(summary["queued"], 70)
                self.assertEqual(q.pending_count(), 70)
                self.assertFalse(os.path.exists(
                    os.path.join(state_dir, "progress_tencent_society.json")))


if __name__ == "__main__":
    unittest.main()
