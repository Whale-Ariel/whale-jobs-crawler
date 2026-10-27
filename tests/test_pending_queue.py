# -*- coding: utf-8 -*-
"""pending_queue 单元测试：入队判重/更新、FIFO 出队、推送标记、按来源统计。"""
import os
import tempfile
import unittest

from crawler.core.queue import PendingQueue


def make_row(job_id, title="x", source="t"):
    return {"job_id": job_id, "title": title, "source": source}


class PendingQueueTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self._tmp.name, "q.db")
        self.q = PendingQueue(self.db)

    def tearDown(self):
        self._tmp.cleanup()

    def test_enqueue_and_fifo_dequeue(self):
        self.q.enqueue([make_row("1"), make_row("2")], "tencent", "society")
        self.q.enqueue([make_row("3")], "bytedance", "campus")
        rows = self.q.dequeue(2)
        self.assertEqual([r["job_id"] for r in rows], ["1", "2"])
        self.assertEqual(self.q.pending_count(), 3)

    def test_enqueue_dedup_updates_payload(self):
        self.q.enqueue([make_row("1", "old")], "tencent", "society")
        self.q.enqueue([make_row("1", "new")], "tencent", "society")
        self.assertEqual(self.q.pending_count(), 1)
        self.assertEqual(self.q.dequeue(1)[0]["title"], "new")

    def test_dequeue_by_source(self):
        self.q.enqueue([make_row("1")], "bytedance", "society")
        self.q.enqueue([make_row("2")], "tencent", "society")
        self.assertEqual([r["job_id"] for r in self.q.dequeue(5, "bytedance")], ["1"])
        self.assertEqual(self.q.pending_count("bytedance"), 1)
        self.assertEqual(self.q.pending_count("tencent"), 1)

    def test_mark_pushed_removes_only_specified(self):
        self.q.enqueue([make_row("1"), make_row("2")], "tencent", "society")
        removed = self.q.mark_pushed(self.q.dequeue(1))
        self.assertEqual(removed, 1)
        self.assertEqual(self.q.pending_count(), 1)

    def test_dequeue_limit(self):
        self.q.enqueue([make_row(str(i)) for i in range(5)], "t", "s")
        self.assertEqual(len(self.q.dequeue(3)), 3)
        self.assertEqual(len(self.q.dequeue(10)), 5)


if __name__ == "__main__":
    unittest.main()
