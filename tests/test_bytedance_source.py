# -*- coding: utf-8 -*-
"""bytedance_source 单元测试：字段解析、增量/全量抓取只入本地队列（不推云库）。"""
import json
import os
import tempfile
import unittest
from unittest import mock

from crawler import paths
from crawler.core import state as state_store
from crawler.sources.bytedance import client as bytedance_source
from crawler.sources.bytedance.client import parse_job
from crawler.sync.push import COLUMNS
from crawler.core.queue import PendingQueue


def sample_job(jid, title="后端工程师"):
    return {
        "id": jid, "title": title, "sub_title": "字节", "code": f"BY{jid}",
        "description": "desc", "requirement": "req",
        "job_category": {"id": 7, "name": "技术", "en_name": "Tech"},
        "recruit_type": {"id": 1, "name": "正式", "en_name": "Full"},
        "city_info": {"code": "110000", "name": "北京", "en_name": "Beijing"},
        "city_list": ["北京"],
        "job_post_info": {
            "address": "望京", "address_list": ["望京"],
            "min_salary": 20, "max_salary": 40, "currency": "K",
            "head_count": 1, "required_degree": "本科",
            "min_level": "2", "max_level": "5", "expiry_time": 1767225600000,
        },
        "job_hot_flag": 2,  # 接口可能返回整数，必须归一为 bool
        "job_subject": ["a"], "job_function": ["b"],
        "department_id": 55, "job_process_id": 66,
        "storefront_mode": 1, "process_type": 2,
        "publish_time": 1761148800000,
    }


class ParseJobTest(unittest.TestCase):
    def test_all_schema_keys_present(self):
        row = parse_job(sample_job(1), "society")
        self.assertEqual(set(row.keys()), set(COLUMNS))
        self.assertEqual(row["job_id"], "1")
        self.assertEqual(row["source"], "bytedance")

    def test_bool_normalization_and_ms_to_ts(self):
        row = parse_job(sample_job(2), "society")
        self.assertTrue(row["job_hot_flag"])          # 2 -> True
        self.assertIsNotNone(row["publish_time"])
        self.assertTrue(row["publish_time"].startswith("2025-"))
        row2 = parse_job({"id": 3}, "campus")
        self.assertIsNone(row2["job_hot_flag"])
        self.assertIsNone(row2["publish_time"])


class RunTestBase(unittest.TestCase):
    """抓取 run() 的行为测试：网络与云库均不真实访问。"""

    def _setup_dirs(self, d):
        state_dir, out_dir = os.path.join(d, "state"), os.path.join(d, "output")
        os.makedirs(state_dir)
        os.makedirs(out_dir)
        return state_dir, out_dir


class RunIncrementalTest(RunTestBase, unittest.TestCase):
    def test_new_jobs_enqueued_not_pushed(self):
        with tempfile.TemporaryDirectory() as d:
            state_dir, out_dir = self._setup_dirs(d)
            jobs = [sample_job(12345), sample_job(12346)]

            def fake_fetch(pt, offset, headers, retries=4, page_size=50):
                if offset == 0:
                    return {"count": 2, "job_post_list": jobs}
                return {"count": 10, "job_post_list": []}

            with mock.patch.object(paths, "STATE_DIR", state_dir), \
                 mock.patch.object(paths, "OUTPUT_DIR", out_dir):
                with mock.patch.object(bytedance_source, "fetch_page",
                                       side_effect=fake_fetch), \
                     mock.patch.object(bytedance_source.time, "sleep"):
                    q = PendingQueue(os.path.join(d, "q.db"))
                    summary = bytedance_source.run("society", 2, full=False,
                                                    max_pages_incremental=5, queue=q)
                # 断言在 STATE_DIR patch 生效期内执行
                self.assertEqual(summary["new_rows"], 2)
                self.assertEqual(summary["queued"], 2)
                self.assertEqual(q.pending_count(), 2)
                self.assertEqual(q.dequeue(10), [parse_job(jobs[0], "society"),
                                                  parse_job(jobs[1], "society")])
                # 已知 ID 已持久化（增量判重用）
                self.assertEqual(state_store.load_known_ids("society"),
                                 {"12345", "12346"})
                # 运行汇总已写出
                with open(os.path.join(out_dir, "society_last_run_summary.json"),
                          encoding="utf-8") as f:
                    self.assertEqual(json.load(f)["queued"], 2)

    def test_no_new_jobs_no_enqueue(self):
        with tempfile.TemporaryDirectory() as d:
            state_dir, out_dir = self._setup_dirs(d)
            with mock.patch.object(paths, "STATE_DIR", state_dir), \
                 mock.patch.object(paths, "OUTPUT_DIR", out_dir):
                state_store.save_known_ids("society", {"12345", "12346"})

                def fake_fetch(pt, offset, headers, retries=4, page_size=50):
                    return {"count": 2,
                            "job_post_list": [sample_job(12345), sample_job(12346)]}

                with mock.patch.object(bytedance_source, "fetch_page",
                                       side_effect=fake_fetch), \
                     mock.patch.object(bytedance_source.time, "sleep"):
                    q = PendingQueue(os.path.join(d, "q.db"))
                    summary = bytedance_source.run("society", 2, full=False,
                                                    max_pages_incremental=5, queue=q)
                self.assertEqual(summary["new_rows"], 0)
                self.assertEqual(q.pending_count(), 2)


class RunFullTest(RunTestBase, unittest.TestCase):
    def test_full_resume_from_progress(self):
        with tempfile.TemporaryDirectory() as d:
            state_dir, out_dir = self._setup_dirs(d)
            with mock.patch.object(paths, "STATE_DIR", state_dir), \
                 mock.patch.object(paths, "OUTPUT_DIR", out_dir):
                # 模拟上次全量中断在 offset=30
                state_store.save_progress("society", 30)

                def fake_fetch(pt, offset, headers, retries=4, page_size=50):
                    if offset == 30:
                        return {"count": 31, "job_post_list": [sample_job(12347)]}
                    return {"count": 31, "job_post_list": []}

                with mock.patch.object(bytedance_source, "fetch_page",
                                       side_effect=fake_fetch), \
                     mock.patch.object(bytedance_source.time, "sleep"):
                    q = PendingQueue(os.path.join(d, "q.db"))
                    summary = bytedance_source.run("society", 2, full=True, queue=q)
                self.assertEqual(summary["new_rows"], 1)
                self.assertEqual(q.pending_count(), 1)
                # 断点已清理，全量完成（在 STATE_DIR patch 生效期内断言）
                self.assertEqual(state_store.load_progress("society"), 0)
                self.assertFalse(os.path.exists(
                    os.path.join(state_dir, "progress_society.json")))


if __name__ == "__main__":
    unittest.main()
