# -*- coding: utf-8 -*-
"""慢速同步程序：把本地待同步队列（pending_queue）慢慢推送到 WorkBuddy 云数据库。

用法：
  python3 sync_cloud.py                 # 排空一次：分批推送直到队列为空
  python3 sync_cloud.py --loop          # 常驻模式：队列空时等待 300s 再查，持续慢慢同步
  python3 sync_cloud.py --max-rows 300  # 单次最多推送 300 行（留给下次/下轮定时）

节奏控制（WAF 限频实测结论，见 cloud_push）：
- 单批 ≤30 行、批间隔 10s → 峰值吞吐约 180 行/分钟，日常积压很快消化完
- 403 走 WAF 冷却退避（90s 起递增），彻底失败本批保留在队列，下次继续（幂等）
- 崩溃/断网不丢数据：dequeue 只读，推送成功才 mark_pushed
"""
import argparse
import sys
import time

from crawler.sync import push as cloud_push
from crawler.core import queue as pending_queue
from crawler.core import state as state_store
from crawler.core.model import normalize_row
from tqdm.auto import tqdm

DEFAULT_BATCH_SIZE = cloud_push.PUSH_BATCH_SIZE
DEFAULT_EMPTY_WAIT = 300  # 常驻模式下队列空时的轮询间隔（秒）


def _drain(max_rows: int = None, queue=None,
          batch_size: int = DEFAULT_BATCH_SIZE,
          batch_interval: float = cloud_push.PUSH_INTERVAL) -> dict:
    """把队列数据分批推送到云库；max_rows 限制本次推送总量（None=不限）。

    推送彻底失败（重试耗尽）时本批保留在队列并停止本次 drain，
    避免 WAF 持续拦截下空转；等冷却期过后（下次运行/下一轮循环）再继续。
    """
    queue = queue or pending_queue.default_queue()
    pushed_total = 0
    batches = 0
    failed = False
    target = queue.pending_count() if max_rows is None else min(max_rows, queue.pending_count())
    with tqdm(total=target, desc='同步云端', unit='职位', dynamic_ncols=True) as bar:
        while max_rows is None or pushed_total < max_rows:
            limit = batch_size
            if max_rows is not None:
                limit = min(batch_size, max_rows - pushed_total)
            rows = queue.dequeue(limit)
            if not rows:
                break
            try:
                # 兼容旧队列：补全独立分类字段，保持确认凭证绑定原记录。
                wire_rows = []
                for row in rows:
                    wire = normalize_row(row)
                    wire_rows.append(wire)
                cloud_push.push_rows(wire_rows)
            except Exception as e:  # noqa: BLE001
                print(f"[sync] 推送失败，本批 {len(rows)} 行保留在队列，稍后重试: {e}",
                      flush=True)
                failed = True
                break
            queue.mark_pushed(rows)
            pushed_total += len(rows)
            batches += 1
            bar.update(len(rows))
            print(f"[sync] batch={batches} pushed_total={pushed_total} "
                  f"remaining={queue.pending_count()}", flush=True)
            if queue.pending_count() and (max_rows is None or pushed_total < max_rows):
                time.sleep(batch_interval)
    return {"pushed": pushed_total, "batches": batches,
            "failed": failed, "remaining": queue.pending_count()}


def drain(max_rows=None, queue=None, batch_size=DEFAULT_BATCH_SIZE,
          batch_interval=cloud_push.PUSH_INTERVAL):
    if max_rows is not None and max_rows < 1:
        raise ValueError('max_rows 必须大于零')
    if batch_size < 1 or batch_interval < 0:
        raise ValueError('无效的同步批次参数')
    with state_store.channel_lock('cloud_sync'):
        return _drain(max_rows, queue, batch_size, batch_interval)


def loop(max_rows_per_cycle: int = 300, empty_wait: float = DEFAULT_EMPTY_WAIT,
         queue=None, max_cycles: int = None) -> dict:
    """常驻慢慢同步：排空一个周期后若队列为空则等待 empty_wait 秒再查。

    max_cycles=None 时无限运行（后台常驻）；传整数用于测试。
    """
    queue = queue or pending_queue.default_queue()
    cycles = 0
    total_pushed = 0
    while max_cycles is None or cycles < max_cycles:
        cycles += 1
        res = drain(max_rows=max_rows_per_cycle, queue=queue)
        total_pushed += res["pushed"]
        if res["failed"]:
            time.sleep(max(empty_wait, cloud_push.WAF_COOLDOWN))
        if res["pushed"] == 0 and not res["failed"]:
            print(f"[sync] 队列为空，等待 {int(empty_wait)}s 后再查（Ctrl+C 退出）",
                  flush=True)
            time.sleep(empty_wait)
    return {"cycles": cycles, "pushed": total_pushed}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync_cloud.py",
        description="本地待同步队列 → WorkBuddy 云库 的慢速同步")
    parser.add_argument("--loop", action="store_true",
                        help="常驻模式：队列空时轮询等待，持续慢慢同步")
    parser.add_argument("--max-rows", type=int, default=None,
                        help="单次（每周期）最多推送行数（默认不限/常驻每周期 300）")
    parser.add_argument("--empty-wait", type=int, default=DEFAULT_EMPTY_WAIT,
                        help="常驻模式队列空时的等待秒数（默认 300）")
    args = parser.parse_args(argv)

    if args.loop:
        print("[sync] 常驻同步启动：慢慢推送本地队列到云库（Ctrl+C 退出）", flush=True)
        try:
            loop(max_rows_per_cycle=args.max_rows or 300, empty_wait=args.empty_wait)
        except KeyboardInterrupt:
            print("\n[sync] 已退出常驻同步", flush=True)
    else:
        res = drain(max_rows=args.max_rows)
        if res["failed"]:
            print(f"[sync] 本次同步中断（WAF/网络），已推 {res['pushed']} 行，"
                  f"队列剩余 {res['remaining']} 行（下次运行继续，幂等）", flush=True)
            return 1
        print(f"[sync] SYNC_DONE pushed={res['pushed']} batches={res['batches']} "
              f"remaining={res['remaining']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
