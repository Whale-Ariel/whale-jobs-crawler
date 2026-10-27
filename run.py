#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招聘爬虫统一运行入口（公共操作界面）

架构：抓取与推送解耦
  crawl（抓取各家数据，只写本地 SQLite 待同步队列，不阻塞）
  sync （独立慢速程序，按 WAF 限频节奏把队列数据慢慢推云库）
  replay（历史 SQL 降级文件补录，直接推云库）
  status（运行汇总 / 本地状态 / 待同步队列 / 降级文件）

支持命令行子命令与交互菜单两种方式：

  # 命令行
  python3 run.py crawl  --source all                                   # 4 频道全增量，数据落本地队列
  python3 run.py crawl  --source bytedance --portal society --full
  python3 run.py sync                                               # 排空本地队列（WAF 节奏）
  python3 run.py sync --loop                                         # 常驻慢速同步
  python3 run.py replay --source bytedance --portal society --ts all
  python3 run.py status
  python3 run.py menu

  # 交互菜单（不带参数直接运行）
  python3 run.py

说明:
- 原有 4 个 crawl_*.py 保留可用（定时任务仍直接调它们，行为不变：抓取落本地队列）。
- 定时同步建议：每小时跑一次 `run.py sync`（或在后台常驻 `run.py sync --loop`）。
"""
import argparse
import glob
import json
import os
import sys

from crawler import paths
from crawler.core import queue as pending_queue
from crawler.replay import bytedance as replay_bytedance
from crawler.replay import tencent as replay_tencent
from crawler.sources import additional_sources, new_sources, run_source
from crawler.sources.alibaba import portal as alibaba_source
from crawler.sync import worker as sync_cloud
from crawler.taxonomy import ALIBABA_UNITS, RECRUITMENT_TYPES

PORTALS = ["society", "campus"]
BYTEDANCE_PORTAL_TYPES = {"society": 2, "campus": 3}

MENU = """
========== 招聘爬虫统一入口 ==========
 1. 抓取 字节 (bytedance)
 2. 抓取 腾讯 (tencent)
 3. 抓取 全部 16 家公司
 4. 补录 字节 降级 SQL（直推云库）
 5. 补录 腾讯 降级 SQL（直推云库）
 6. 查看运行状态
 8. 抓取 阿里（18站社招 + 集团全部开放校招批次）
 9. 抓取 新增5家公司（网易、京东、美团、百度、快手）
 7. 同步本地队列 → 云库（慢速，WAF 节奏）
 10. 抓取 本轮新增8家公司（B站、小红书、滴滴等）
 0. 退出
======================================
"""


# ---------- 交互辅助 ----------

def _pick(prompt, options):
    """交互选择，返回 1..n；输入 0/q 返回 None（取消）。"""
    while True:
        print(prompt)
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        raw = input("选择 (0/q=取消): ").strip().lower()
        if raw in ("0", "q", "quit", "exit", "cancel"):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print("无效输入，请重试")


def _ask_full():
    raw = input("模式: 1=增量(默认)  2=全量(--full)  [1]: ").strip()
    return raw in ("2", "full")


def _ask_number(prompt, default):
    raw = input(prompt).strip()
    if not raw:
        return default
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        print(f"无效数字，使用默认值 {default}")
        return default


# ---------- 调度 ----------

def crawl_source(source, portals, full, max_pages, interval, page_size=50, batch_id=None, skip_existing=True):
    """抓取指定来源的频道，新数据入本地待同步队列。"""
    extra = {} if skip_existing else {'skip_existing': False}
    for portal in portals:
        print(f"\n>>> run.py crawl source={source} portal={portal} "
              f"full={full} pages={max_pages}", flush=True)
        run_source(source, portal, full=full, max_pages_incremental=max_pages,
                   request_interval=interval, page_size=page_size, batch_id=batch_id, **extra)


def menu_crawl(source):
    """交互抓取。source: bytedance / tencent / all"""
    targets = (["bytedance", "tencent", "alibaba", *new_sources.PORTALS, *additional_sources.PORTALS] if source == "all"
               else list(new_sources.PORTALS) if source == "new" else [source])

    if source in {"all","new"}:
        portals = PORTALS
    else:
        p = _pick("选择频道:", ["社招 society", "校招 campus", "全部频道 (社招+校招)"])
        if p is None:
            print("已取消")
            return
        portals = PORTALS if p == 3 else [PORTALS[p - 1]]

    full = _ask_full()
    max_pages = int(_ask_number("增量模式最大页数 [50]: ", 50))
    interval = float(_ask_number("页间请求间隔秒 [0.4]: ", 0.4))
    for target in targets:
        crawl_source(target, list(alibaba_source.DEFAULT_PORTALS) if target == "alibaba"
                     else list(new_sources.PORTALS[target]) if target in new_sources.PORTALS
                     else list(additional_sources.PORTALS[target]) if target in additional_sources.PORTALS else portals,
                     full, max_pages, interval)
    q = pending_queue.default_queue()
    print(f"\n抓取完成。本地待同步队列: {q.pending_count()} 行"
          f"（字节 {q.pending_count('bytedance')} / 腾讯 {q.pending_count('tencent')} / 阿里 {q.pending_count('alibaba')}），"
          f"运行 menu 第 7 项或 `run.py sync` 推送云库。")


def menu_replay(module, source):
    p = _pick("选择频道:", ["社招 society", "校招 campus"])
    if p is None:
        print("已取消")
        return
    portal = PORTALS[p - 1]
    raw = input("批次时间戳前缀 (all=全部批次) [all]: ").strip()
    module.replay(portal, raw or "all")


def menu_sync():
    m = _pick("同步模式:",
              ["一次性排空（跑完退出，适合定时任务）", "常驻循环（队列空时等待 300s 再查）"])
    if m is None:
        print("已取消")
        return
    if m == 1:
        raw = input("单次最多推送行数 (回车=不限) [回车]: ").strip()
        max_rows = int(raw) if raw else None
        res = sync_cloud.drain(max_rows=max_rows)
        print(f"同步结束: pushed={res['pushed']} failed={res['failed']} "
              f"remaining={res['remaining']}")
    else:
        raw = input("常驻模式每周期最多推送行数 [300]: ").strip()
        cycle_rows = int(raw) if raw else 300
        print("常驻同步已启动（Ctrl+C 退出）")
        try:
            sync_cloud.loop(max_rows_per_cycle=cycle_rows)
        except KeyboardInterrupt:
            print("\n已退出常驻同步")


def status():
    paths.ensure_dirs()
    print("== 最近运行汇总 (output/*_last_run_summary.json) ==")
    found = False
    for name in sorted(os.listdir(paths.OUTPUT_DIR)):
        if name.endswith("_last_run_summary.json"):
            with open(os.path.join(paths.OUTPUT_DIR, name), encoding="utf-8") as f:
                s = json.load(f)
            queued = s.get("queued", s.get("pushed", "-"))
            print(f"  {s.get('portal'):>18}  mode={s.get('mode'):<12} "
                  f"new={s.get('new_rows')} skipped={s.get('skipped_existing', 0)} queued/pushed={queued}  "
                  f"site={s.get('source_site', '-')} batch={s.get('batch_id', '-')} status={s.get('status', 'finished')} complete={s.get('complete', '-')} "
                  f"at={s.get('finished_at', s.get('started_at'))}")
            found = True
    if not found:
        print("  (暂无运行记录)")

    q = pending_queue.default_queue()
    print("\n== 本地待同步队列 (state/pending_queue.db) ==")
    print(f"  总计 {q.pending_count()} 行  " +
          ' / '.join(f'{s} {q.pending_count(s)}' for s in ['bytedance','tencent','alibaba',*new_sources.PORTALS]))

    print("\n== 本地状态缓存 (state/) ==")
    for name in sorted(os.listdir(paths.STATE_DIR)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(paths.STATE_DIR, name), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(data, list):
            print(f"  {name}: 已知职位 {len(data)} 条")
        else:
            print(f"  {name}: {json.dumps(data, ensure_ascii=False)}")

    print("\n== 事业群关联职位数（共享职位会在各群分别计数） ==")
    import sqlite3
    with sqlite3.connect(paths.queue_db_path()) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='pending_jobs'").fetchone():
            return
        for record in conn.execute("""SELECT p.source,COALESCE(unit.value,'未标注'),
             COALESCE(json_extract(p.payload,'$.recruitment_type'),p.portal),p.batch_id,COUNT(DISTINCT p.seq)
             FROM pending_jobs AS p
             LEFT JOIN json_each(COALESCE(json_extract(p.payload,'$.business_units'),'[]')) AS unit ON true
             GROUP BY 1,2,3,4 ORDER BY 1,2,3,4"""):
            print('  '+ ' | '.join(map(str,record)))
    # 递归匹配：兼容归档到 output/archive_*/ 下的批次文件
    sql_files = sorted({
        os.path.relpath(p, paths.OUTPUT_DIR)
        for p in glob.glob(os.path.join(paths.OUTPUT_DIR, "**", "*.sql"), recursive=True)
    })
    print(f"\n== 降级 SQL 文件: {len(sql_files)} 个 (output/**/*.sql，含已归档) ==")
    for n in sql_files:
        print(f"  {n}")


def menu_loop():
    while True:
        print(MENU)
        try:
            choice = input("选项> ").strip()
        except EOFError:
            print()
            return
        if choice in ("0", "q", "quit", "exit"):
            break
        elif choice == "1":
            menu_crawl("bytedance")
        elif choice == "2":
            menu_crawl("tencent")
        elif choice == "3":
            menu_crawl("all")
        elif choice == "4":
            menu_replay(replay_bytedance, "bytedance")
        elif choice == "5":
            menu_replay(replay_tencent, "tencent")
        elif choice == "6":
            status()
        elif choice == "8":
            p = _pick('选择阿里招聘范围:', ['集团全部校招批次','18个事业部社招','社招和校招'])
            if p is not None:
                targets = ['campus'] if p == 1 else ['society'] if p == 2 else list(alibaba_source.DEFAULT_PORTALS)
                full = _ask_full()
                crawl_source('alibaba',targets,full,50,0.4)
        elif choice == "9":
            menu_crawl("new")
        elif choice == "10":
            main(["crawl","--source","extra","--full"])
        elif choice == "7":
            menu_sync()
        else:
            print("无效选项")


# ---------- 命令行入口 ----------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="run.py", description="招聘爬虫统一运行入口（16家公司，本地抓取）")
    sub = parser.add_subparsers(dest="cmd")

    c = sub.add_parser("crawl", help="抓取并写入本地待同步队列（不推云库）")
    c.add_argument("--source", choices=["bytedance", "tencent", "alibaba", *new_sources.PORTALS, *additional_sources.PORTALS, "new", "extra", "all"],
                   default="all", help="来源（默认 all）")
    c.add_argument("--portal", choices=[*RECRUITMENT_TYPES, "all"],
                   default="all", help="频道（默认 all）")
    c.add_argument("--full", action="store_true", help="全量抓取（默认增量）")
    c.add_argument("--pages", type=int, default=50,
                   help="增量模式最大页数（默认 50）")
    c.add_argument("--interval", type=float, default=0.4,
                   help="页间请求间隔秒（默认 0.4）")
    c.add_argument("--page-size", type=int, default=50, help="每页条数（默认 50）")
    c.add_argument("--batch-id", help="阿里统一校招：只抓官网当前开放的指定批次")
    c.add_argument("--refresh-existing", action="store_true", help="显式刷新已有职位；默认跳过已有ID")
    c.add_argument("--sync", action="store_true",
                   help="抓取完成后立即同步本地队列到云库（推空为止，默认关闭）")

    s = sub.add_parser("sync", help="本地待同步队列 → 云库 的慢速同步")
    s.add_argument("--loop", action="store_true",
                   help="常驻模式：队列空时轮询等待，持续慢慢同步")
    s.add_argument("--max-rows", type=int, default=None,
                   help="单次（每周期）最多推送行数（默认不限/常驻每周期 300）")
    s.add_argument("--empty-wait", type=int, default=300,
                   help="常驻模式队列空时的等待秒数（默认 300）")

    r = sub.add_parser("replay", help="补录 output/*.sql 降级文件（直接推云库）")
    r.add_argument("--source", choices=["bytedance", "tencent"], required=True)
    r.add_argument("--portal", choices=["society", "campus"], required=True)
    r.add_argument("--ts", default="all", help="批次时间戳前缀（默认 all=全部批次）")

    sub.add_parser("plan", help="查看抓取频道、公司和事业部分层")
    sub.add_parser("status", help="查看最近运行汇总 / 本地状态 / 待同步队列 / 降级 SQL")
    sub.add_parser("menu", help="交互式菜单（不带参数运行等价于此）")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.cmd in (None, "menu"):
        menu_loop()
        return 0
    if args.cmd == "crawl":
        if args.pages < 1 or not 1 <= args.page_size <= 50 or args.interval < 0:
            raise ValueError('pages/page-size 必须为正数，interval 不得小于零')
        sources = (["bytedance", "tencent", "alibaba", *new_sources.PORTALS, *additional_sources.PORTALS] if args.source == "all"
                   else list(new_sources.PORTALS) if args.source == "new"
                   else list(additional_sources.PORTALS) if args.source == "extra" else [args.source])
        if args.batch_id and (args.source != 'alibaba' or args.portal == 'society'):
            raise ValueError('--batch-id 仅支持 --source alibaba 的校招查询')
        if args.batch_id and args.portal == 'all':
            args.portal = 'campus'
        failed = []
        def available(source):
            return (list(alibaba_source.DEFAULT_PORTALS) if source == 'alibaba'
                    else list(new_sources.PORTALS[source]) if source in new_sources.PORTALS
                    else list(additional_sources.PORTALS[source]) if source in additional_sources.PORTALS else PORTALS)
        task_count = sum(len(available(s)) if args.portal == 'all' else int(args.portal in available(s)) for s in sources)
        task_index = 0
        for source in sources:
            supported = list(alibaba_source.SUPPORTED_PORTALS) if source == 'alibaba' else available(source)
            portals = available(source) if args.portal == 'all' else [args.portal]
            for portal in portals:
                if portal not in supported:
                    if args.source in {'all','new','extra'}:
                        continue
                    raise ValueError(f'{source} 不支持 {portal}；可选 {supported}')
                task_index += 1
                print(f'\n[任务 {task_index}/{task_count}] {source}/{portal}', flush=True)
                try:
                    extra = {} if not args.refresh_existing else {'skip_existing':False}
                    if args.batch_id:
                        crawl_source(source,[portal],args.full,args.pages,args.interval,args.page_size,batch_id=args.batch_id,**extra)
                    else:
                        crawl_source(source,[portal],args.full,args.pages,args.interval,args.page_size,**extra)
                except Exception as e:
                    failed.append(f'{source}/{portal}')
                    print(f'[ERROR] {source}/{portal}: {e}', flush=True)
        if failed:
            print('失败频道: '+', '.join(failed)+'；已落盘数据保留，请重跑对应频道')
            return 1
        q = pending_queue.default_queue()
        if args.sync:
            print(f"\n抓取完成，开始同步本地队列（{q.pending_count()} 行，WAF 节奏）...")
            res = sync_cloud.drain()
            if res["failed"]:
                print(f"同步中断（WAF/网络），已推 {res['pushed']} 行，"
                      f"剩余 {res['remaining']} 行，稍后重跑 `run.py sync`", flush=True)
                return 1
            print(f"CRAWL+SYNC_DONE synced={res['pushed']} remaining=0")
        else:
            print(f"\n抓取完成。本地待同步队列: {q.pending_count()} 行，"
                  f"运行 `run.py sync` 推送云库（加 --sync 可自动同步）。")
    elif args.cmd == "sync":
        if args.loop:
            try:
                sync_cloud.loop(max_rows_per_cycle=args.max_rows or 300,
                                empty_wait=args.empty_wait)
            except KeyboardInterrupt:
                print("\n已退出常驻同步")
        else:
            res = sync_cloud.drain(max_rows=args.max_rows)
            if res["failed"]:
                print(f"同步中断（WAF/网络），已推 {res['pushed']} 行，"
                      f"剩余 {res['remaining']} 行下次继续", flush=True)
                return 1
            print(f"SYNC_DONE pushed={res['pushed']} remaining={res['remaining']}")
    elif args.cmd == "replay":
        if args.source == "bytedance":
            replay_bytedance.replay(args.portal, args.ts)
        else:
            replay_tencent.replay(args.portal, args.ts)
    elif args.cmd == "plan":
        for source, portals in [('bytedance', PORTALS), ('tencent', PORTALS), ('alibaba', list(alibaba_source.DEFAULT_PORTALS)), *new_sources.PORTALS.items(), *additional_sources.PORTALS.items()]:
            for portal in portals:
                print(f'{source:12} {portal:18} {RECRUITMENT_TYPES[portal]}  默认{10 if source in {"baidu","pdd"} else 50}条/页')
        print('阿里 campus 自动发现应届生和实习批次；ali_star仅是应届生子集标签。可用 --batch-id 限定批次。')
        print('阿里社招按18站配置分类，校招按官网组织关系接口分类；未知名称原样保留。')
    elif args.cmd == "status":
        status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
