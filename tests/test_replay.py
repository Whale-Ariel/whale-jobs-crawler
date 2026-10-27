# -*- coding: utf-8 -*-
"""replay 补录脚本单元测试：SQL 文件 job_id 提取、补录主流程（网络/云库打桩）。"""
import os
import tempfile
import unittest
from unittest import mock

from crawler import paths
from crawler.sources.bytedance import client as bytedance_source
from crawler.sources.tencent import client as tencent_source
from crawler.replay import bytedance as replay_bytedance
from crawler.replay import tencent as replay_tencent
from crawler.sync import push as cloud_push


SQL_BODY = """INSERT INTO bytedance_jobs (job_id, type, source) VALUES
('12345', 'society', 'bytedance'),
('12346', 'society', 'bytedance');
ON CONFLICT (job_id) DO NOTHING
"""


class ExtractIdsTest(unittest.TestCase):
    def test_bytedance_extracts_numeric_job_ids(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False,
                                         encoding="utf-8") as f:
            f.write(SQL_BODY)
            path = f.name
        try:
            self.assertEqual(replay_bytedance._extract_target_ids([path]),
                             {"12345", "12346"})
        finally:
            os.remove(path)

    def test_tencent_extracts_numeric_job_ids(self):
        with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False,
                                         encoding="utf-8") as f:
            f.write(SQL_BODY)
            path = f.name
        try:
            self.assertEqual(replay_tencent._extract_target_ids([path]),
                             {"12345", "12346"})
        finally:
            os.remove(path)


class ReplayBytedanceTest(unittest.TestCase):
    def test_unknown_portal_raises(self):
        with self.assertRaises(SystemExit):
            replay_bytedance.replay("unknown", "all")

    def test_no_matching_files_raises(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.object(paths, "OUTPUT_DIR", d):
            with self.assertRaises(SystemExit):
                replay_bytedance.replay("society", "20990101_000000")

    def test_replay_collects_and_pushes(self):
        with tempfile.TemporaryDirectory() as d:
            out_dir = os.path.join(d, "output")
            os.makedirs(out_dir)
            sql_file = os.path.join(out_dir, "society_20261022_213926_batch_0001.sql")
            with open(sql_file, "w", encoding="utf-8") as f:
                f.write(SQL_BODY)

            pushed = []

            def fake_fetch(pt, offset, headers, retries=4):
                return {"count": 10, "job_post_list": [
                    {"id": "12345", "title": "工程师", "job_post_info": {}},
                    {"id": "12346", "title": "研究员", "job_post_info": {}},
                ]}

            def fake_push(rows, retries=8):
                pushed.extend(rows)
                return len(rows)

            with mock.patch.object(paths, "OUTPUT_DIR", out_dir), \
                 mock.patch.object(bytedance_source, "fetch_page", side_effect=fake_fetch), \
                 mock.patch.object(cloud_push, "push_rows", side_effect=fake_push), \
                 mock.patch.object(replay_bytedance.time, "sleep"):
                n = replay_bytedance.replay("society", "20261022_213926")
            self.assertEqual(n, 2)
            self.assertEqual({r["job_id"] for r in pushed}, {"12345", "12346"})
            self.assertTrue(all(r["source"] == "bytedance" for r in pushed))


class ReplayTencentTest(unittest.TestCase):
    def test_unknown_portal_raises(self):
        with self.assertRaises(SystemExit):
            replay_tencent.replay("unknown", "all")

    def test_replay_collects_and_pushes(self):
        with tempfile.TemporaryDirectory() as d:
            out_dir = os.path.join(d, "output")
            os.makedirs(out_dir)
            sql_file = os.path.join(out_dir, "tencent_society_20261023_091454_batch_0001.sql")
            with open(sql_file, "w", encoding="utf-8") as f:
                f.write(SQL_BODY)

            pushed = []

            def fake_fetch(portal, page, retries=4):
                return {"Count": 2, "Posts": [
                    {"PostId": "12345", "RecruitPostName": "工程师"},
                    {"PostId": "12346", "RecruitPostName": "研究员"},
                ]}

            def fake_push(rows, retries=8):
                pushed.extend(rows)
                return len(rows)

            with mock.patch.object(paths, "OUTPUT_DIR", out_dir), \
                 mock.patch.object(tencent_source, "fetch_page", side_effect=fake_fetch), \
                 mock.patch.object(cloud_push, "push_rows", side_effect=fake_push), \
                 mock.patch.object(replay_tencent.time, "sleep"):
                n = replay_tencent.replay("society", "20261023_091454")
            self.assertEqual(n, 2)
            self.assertEqual({r["job_id"] for r in pushed}, {"12345", "12346"})
            self.assertTrue(all(r["source"] == "tencent" for r in pushed))


if __name__ == "__main__":
    unittest.main()
