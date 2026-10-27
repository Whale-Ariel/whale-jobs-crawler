# -*- coding: utf-8 -*-
"""cloud_push 单元测试：SQL 生成/转义、PostgREST 推送（成功/401/403 WAF 退避）。"""
import io
import os
import tempfile
import unittest
from unittest import mock

from crawler.sync import push as cloud_push
import urllib.error


class FakeResp:
    def __init__(self, content_range="*/2"):
        self._cr = content_range

    def read(self):
        return b"[]"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def headers(self):
        return {"Content-Range": self._cr}


def http_error(code, body=b"denied"):
    return urllib.error.HTTPError("http://x", code, "err", None, io.BytesIO(body))


class RowsToSqlTest(unittest.TestCase):
    def test_value_types_and_escaping(self):
        row = {
            "job_id": "123", "type": "society", "title": "o'brien",
            "job_hot_flag": True, "min_salary": 20000,
            "city_list": ["北京", "上海"], "description": None,
            "raw_data": {"a": 1},
        }
        sql = cloud_push.rows_to_sql([row])
        self.assertIn("NULL", sql)                          # description
        self.assertIn("TRUE", sql)                           # job_hot_flag
        self.assertIn("'o''brien'", sql)                     # 单引号转义
        self.assertIn("'[\"北京\", \"上海\"]'::jsonb", sql)
        self.assertIn("20000", sql)
        self.assertIn("ON CONFLICT (source, recruitment_type, batch_id, source_site, job_id) DO UPDATE SET", sql)

    def test_column_order_matches_schema(self):
        row = dict.fromkeys(cloud_push.COLUMNS, "v")
        sql = cloud_push.rows_to_sql([row])
        head = sql.split("VALUES", 1)[0].strip()  # INSERT INTO recruitment_jobs (...)
        cols = head.rsplit("(", 1)[1].rstrip(")")
        self.assertEqual(cols, ", ".join(cloud_push.COLUMNS))


class WriteSqlBatchesTest(unittest.TestCase):
    def test_batch_files_created(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [{"job_id": str(i), "source": "bytedance"} for i in range(5)]
            files = cloud_push.write_sql_batches(rows, prefix="society",
                                                 batch_size=3, out_dir=d)
            self.assertEqual(len(files), 2)
            for p in files:
                self.assertTrue(os.path.exists(p), p)
            with open(files[0], encoding="utf-8") as f:
                self.assertIn("INSERT INTO recruitment_jobs", f.read())


class PushRowsTest(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {'CRAWLER_CLOUD_ACCESS_KEY': 'test-only'})
        env.start()
        self.addCleanup(env.stop)

    def test_success_counts_content_range(self):
        rows = [{"job_id": "1", "source": "t"}]
        with mock.patch.object(cloud_push.urllib.request, "urlopen",
                               return_value=FakeResp("*/1")) as m_open, \
             mock.patch.object(cloud_push.time, "sleep"):
            self.assertEqual(cloud_push.push_rows(rows), 1)
        self.assertEqual(m_open.call_count, 1)

    def test_empty_returns_zero(self):
        self.assertEqual(cloud_push.push_rows([]), 0)

    def test_401_raises_immediately(self):
        rows = [{"job_id": "1", "source": "t"}]
        with mock.patch.object(cloud_push.urllib.request, "urlopen",
                               side_effect=http_error(401)), \
             mock.patch.object(cloud_push.time, "sleep"):
            with self.assertRaises(RuntimeError):
                cloud_push.push_rows(rows)

    def test_403_waf_cooldowns_then_fail(self):
        rows = [{"job_id": "1", "source": "t"}]
        self._sleep_calls = []

        def record_sleep(seconds):
            self._sleep_calls.append(seconds)

        with mock.patch.object(cloud_push.urllib.request, "urlopen",
                               side_effect=http_error(403)), \
             mock.patch.object(cloud_push.time, "sleep", side_effect=record_sleep):
            with self.assertRaises(RuntimeError):
                cloud_push.push_rows(rows, retries=2)
        # 两次 403 触发 WAF 冷却 90s、180s（递增退避）
        self.assertIn(90, self._sleep_calls)
        self.assertIn(180, self._sleep_calls)


if __name__ == "__main__":
    unittest.main()
