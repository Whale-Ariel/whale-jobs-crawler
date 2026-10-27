# -*- coding: utf-8 -*-
"""sync_cloud 单元测试：分批推送、失败保留、总量限制、常驻循环。"""
import os
import tempfile
import unittest
from unittest import mock

from crawler.sync import push as cloud_push
from crawler.sync import worker as sync_cloud
from crawler.core.queue import PendingQueue


def row(job_id, source="tencent"):
    return {"job_id": job_id, "title": "t", "source": source, "type": "society"}


class SyncTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.q = PendingQueue(os.path.join(self._tmp.name, "q.db"))
        self._push_calls = []

    def tearDown(self):
        self._tmp.cleanup()

    def _seed(self, n, source="tencent"):
        self.q.enqueue([row(str(i), source) for i in range(n)], source, "society")

    def _patch_push(self, ok=True):
        def fake_push(rows, retries=8):
            if not ok:
                raise RuntimeError("waf blocked")
            self._push_calls.append(len(rows))
            return len(rows)
        return mock.patch.object(cloud_push, "push_rows", fake_push)


class DrainTest(SyncTestBase, unittest.TestCase):
    def test_drain_batches_and_marks_pushed(self):
        self._seed(65)
        with self._patch_push(), \
             mock.patch.object(sync_cloud.time, "sleep"):
            res = sync_cloud.drain(queue=self.q, batch_interval=0)
        # 30 + 30 + 5
        self.assertEqual(self._push_calls, [30, 30, 5])
        self.assertEqual(res["pushed"], 65)
        self.assertFalse(res["failed"])
        self.assertEqual(self.q.pending_count(), 0)

    def test_drain_respects_max_rows(self):
        self._seed(65)
        with self._patch_push(), \
             mock.patch.object(sync_cloud.time, "sleep"):
            res = sync_cloud.drain(max_rows=35, queue=self.q, batch_interval=0)
        self.assertEqual(res["pushed"], 35)
        self.assertEqual(self.q.pending_count(), 30)

    def test_drain_failure_keeps_batch_in_queue(self):
        self._seed(65)
        with self._patch_push(ok=False), \
             mock.patch.object(sync_cloud.time, "sleep"):
            res = sync_cloud.drain(queue=self.q, batch_interval=0)
        self.assertTrue(res["failed"])
        self.assertEqual(res["pushed"], 0)
        # 失败批次保留在队列，等下次重试（幂等）
        self.assertEqual(self.q.pending_count(), 65)

    def test_drain_empty_queue_noop(self):
        with self._patch_push(), \
             mock.patch.object(sync_cloud.time, "sleep"):
            res = sync_cloud.drain(queue=self.q, batch_interval=0)
        self.assertEqual(res["pushed"], 0)
        self.assertEqual(self._push_calls, [])


class LoopTest(SyncTestBase, unittest.TestCase):
    def test_loop_cycles_and_waits_on_empty(self):
        self._seed(5)
        self._sleep_calls = []
        with self._patch_push(), \
             mock.patch.object(sync_cloud.time, "sleep",
                               side_effect=self._sleep_calls.append):
            res = sync_cloud.loop(max_rows_per_cycle=300, empty_wait=300,
                                  queue=self.q, max_cycles=2)
        self.assertEqual(res, {"cycles": 2, "pushed": 5})
        self.assertEqual(self.q.pending_count(), 0)
        # 第二个周期队列已空 → 触发 300s 等待
        self.assertIn(300, self._sleep_calls)


if __name__ == "__main__":
    unittest.main()
