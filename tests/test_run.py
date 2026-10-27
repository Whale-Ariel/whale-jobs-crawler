# -*- coding: utf-8 -*-
"""run.py 统一入口调度测试：子命令分发、参数映射、status 不抛异常。"""
import os
import tempfile
import unittest
from unittest import mock

from crawler import paths
from crawler.sync import worker as sync_cloud
from crawler.replay import bytedance as replay_bytedance
from crawler.replay import tencent as replay_tencent
import run


class CrawlDispatchTest(unittest.TestCase):
    def test_crawl_single_source_single_portal(self):
        with mock.patch.object(run, "crawl_source") as m_crawl, \
             mock.patch.object(run.pending_queue, "default_queue") as m_q:
            m_q.return_value.pending_count.return_value = 0
            self.assertEqual(run.main(["crawl", "--source", "bytedance",
                                       "--portal", "society", "--full"]), 0)
        m_crawl.assert_called_once_with("bytedance", ["society"], True, 50, 0.4, 50)

    def test_crawl_all_expands_to_registered_targets(self):
        calls = []

        def fake_crawl(source, portals, full, pages, interval, page_size=50):
            calls.extend((source, p) for p in portals)

        with mock.patch.object(run, "crawl_source", side_effect=fake_crawl), \
             mock.patch.object(run.pending_queue, "default_queue") as m_q:
            m_q.return_value.pending_count.return_value = 0
            run.main(["crawl"])
        self.assertEqual(calls, [
            ("bytedance", "society"), ("bytedance", "campus"),
            ("tencent", "society"), ("tencent", "campus"),
            ("alibaba", "society"), ("alibaba", "campus"),
        ] + [(source,p) for source,portals in run.new_sources.PORTALS.items() for p in portals] + [(s,p) for s,ps in run.additional_sources.PORTALS.items() for p in ps])

    def test_crawl_respects_pages_and_interval(self):
        with mock.patch.object(run, "crawl_source") as m_crawl, \
             mock.patch.object(run.pending_queue, "default_queue") as m_q:
            m_q.return_value.pending_count.return_value = 0
            run.main(["crawl", "--source", "tencent", "--portal", "campus",
                      "--pages", "7", "--interval", "0.1"])
        m_crawl.assert_called_once_with("tencent", ["campus"], False, 7, 0.1, 50)

    def test_crawl_with_sync_flag_drains_queue(self):
        with mock.patch.object(run, "crawl_source"), \
             mock.patch.object(run.pending_queue, "default_queue") as m_q, \
             mock.patch.object(sync_cloud, "drain",
                               return_value={"pushed": 10, "failed": False,
                                             "remaining": 0}) as m_drain:
            m_q.return_value.pending_count.return_value = 10
            self.assertEqual(run.main(["crawl", "--sync"]), 0)
        m_drain.assert_called_once_with()

    def test_crawl_with_sync_failure_returns_nonzero(self):
        with mock.patch.object(run, "crawl_source"), \
             mock.patch.object(run.pending_queue, "default_queue") as m_q, \
             mock.patch.object(sync_cloud, "drain",
                               return_value={"pushed": 0, "failed": True,
                                             "remaining": 10}):
            m_q.return_value.pending_count.return_value = 10
            self.assertEqual(run.main(["crawl", "--sync"]), 1)


class SyncDispatchTest(unittest.TestCase):
    def test_sync_once_calls_drain(self):
        with mock.patch.object(sync_cloud, "drain",
                               return_value={"pushed": 3, "failed": False,
                                             "remaining": 0}) as m_drain:
            self.assertEqual(run.main(["sync", "--max-rows", "99"]), 0)
        m_drain.assert_called_once_with(max_rows=99)

    def test_sync_failure_returns_nonzero(self):
        with mock.patch.object(sync_cloud, "drain",
                               return_value={"pushed": 0, "failed": True,
                                             "remaining": 65}):
            self.assertEqual(run.main(["sync"]), 1)

    def test_sync_loop_dispatch(self):
        with mock.patch.object(sync_cloud, "loop") as m_loop:
            self.assertEqual(run.main(["sync", "--loop", "--empty-wait", "60"]), 0)
        m_loop.assert_called_once_with(max_rows_per_cycle=300, empty_wait=60)


class ReplayDispatchTest(unittest.TestCase):
    def test_replay_bytedance_dispatch(self):
        with mock.patch.object(replay_bytedance, "replay") as m_replay:
            run.main(["replay", "--source", "bytedance",
                     "--portal", "society", "--ts", "all"])
        m_replay.assert_called_once_with("society", "all")

    def test_replay_tencent_dispatch(self):
        with mock.patch.object(replay_tencent, "replay") as m_replay:
            run.main(["replay", "--source", "tencent",
                     "--portal", "campus", "--ts", "20261023_091454"])
        m_replay.assert_called_once_with("campus", "20261023_091454")


class StatusTest(unittest.TestCase):
    def test_status_smoke_no_crash(self):
        with tempfile.TemporaryDirectory() as d:
            state_dir, out_dir = os.path.join(d, "state"), os.path.join(d, "output")
            os.makedirs(state_dir)
            os.makedirs(out_dir)
            with mock.patch.object(paths, "STATE_DIR", state_dir), \
                 mock.patch.object(paths, "OUTPUT_DIR", out_dir), \
                 mock.patch.object(run.pending_queue, "default_queue") as m_q:
                m_q.return_value.pending_count.return_value = 0
                run.status()  # 无任何记录时也不应抛异常


if __name__ == "__main__":
    unittest.main()
