# -*- coding: utf-8 -*-
"""腾讯降级 SQL 文件补录脚本（历史批次数据直接推送云库，不入新队列）。

- 用法：python3 replay_tencent.py <portal> <批次时间戳前缀|all>
  例：python3 replay_tencent.py society 20261023_091454
  或经统一入口：python3 run.py replay --source tencent --portal society --ts all
- 原理：从 output/tencent_*.sql（含 archive_*/ 归档）中提取 job_id（PostId），
  重新从腾讯 API 抓取这些职位并推送云数据库
  （推送走 upsert 冲突忽略，天然幂等）
"""
import glob
import os
import re
import sys
import time

from crawler import paths
from crawler.sources.tencent import client as tencent_source
from crawler.sync import push as cloud_push

MAX_PAGES = 100  # 补录时最多翻查的腾讯列表页数（社招 ~46 页足够）


def _extract_target_ids(files: list) -> set:
    """从 SQL 文件提取 job_id。

    行格式（按 COLUMNS 顺序）：('job_id','type',...,'raw_data','source')，
    type 列取值 society/campus，故匹配 "数字 job_id 后紧跟 'society'/'campus'"。
    """
    ids = set()
    pattern = re.compile(r"^\('(\d+)', '(?:society|campus)'", re.M)
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            ids.update(pattern.findall(f.read()))
    return ids


def replay(portal: str, ts: str) -> int:
    """补录指定频道的降级 SQL 文件：重抓对应职位并直接推送云库。返回成功推送行数。"""
    if portal not in tencent_source.ATTR_IDS:
        raise SystemExit(
            f"unknown portal: {portal}（可选: {', '.join(tencent_source.ATTR_IDS)}）")
    pat_ts = "*" if ts == "all" else ts
    # ** 递归匹配：兼容归档到 output/archive_*/ 下的批次文件
    pattern = os.path.join(paths.OUTPUT_DIR, f"**/tencent_{portal}_{pat_ts}_batch_*.sql")
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        print(f"no sql files matched: {pattern}")
        raise SystemExit(1)

    target_ids = _extract_target_ids(files)
    print(f"[replay] {len(files)} files, {len(target_ids)} job_ids to replay",
          flush=True)

    rows = []
    page = 1
    while target_ids and page <= MAX_PAGES:
        data = tencent_source.fetch_page(portal, page)
        posts = data.get("Posts") or []
        if not posts:
            break
        for post in posts:
            pid = str(post.get("PostId") or "")
            if pid in target_ids:
                target_ids.discard(pid)
                rows.append(tencent_source.parse_post(post, portal))
        print(f"[replay] page={page} collected={len(rows)} "
              f"remaining={len(target_ids)}", flush=True)
        page += 1
        time.sleep(0.4)

    if target_ids:
        print(f"[replay] WARN {len(target_ids)} ids not found on API anymore "
              f"(可能已下架), skip", flush=True)

    pushed = cloud_push.push_rows(rows)
    print(f"[replay] REPLAY_DONE collected={len(rows)} pushed={pushed}", flush=True)
    return pushed


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        print("用法: python3 replay_tencent.py <portal> <批次时间戳前缀|all>")
        sys.exit(1)
    replay(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
