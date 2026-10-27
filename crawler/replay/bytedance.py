# -*- coding: utf-8 -*-
"""字节降级 SQL 文件补录脚本（历史批次数据直接推送云库，不入新队列）。

- 用法：python3 replay_bytedance.py <portal> <批次时间戳前缀|all>
  例：python3 replay_bytedance.py society 20261022_213926
  或经统一入口：python3 run.py replay --source bytedance --portal society --ts all
- 原理：从 output/**/*.sql（含 archive_*/ 归档）中提取 job_id，
  重新从字节招聘 API 抓取这些职位并推送云数据库
  （推送走 upsert 冲突忽略，天然幂等）
"""
import glob
import os
import re
import sys
import time

from crawler import paths
from crawler.sources.bytedance import client as bytedance_source
from crawler.sync import push as cloud_push

PORTAL_TYPES = {"society": 2, "campus": 3}
MAX_OFFSET = 20000  # 安全上限（社招全量 ~1万 职位、校招 ~7000+）


def _extract_target_ids(files: list) -> set:
    """从 SQL 文件提取 job_id。

    行格式（按 COLUMNS 顺序）：('job_id','type',...,'raw_data','source')，
    type 列取值 society/campus，故匹配 "数字 job_id 后紧跟 'society'/'campus'"。
    """
    ids = set()
    pattern = re.compile(r"\('(\d+)', '(?:society|campus)'")
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            ids.update(pattern.findall(f.read()))
    return ids


def replay(portal: str, ts: str) -> int:
    """补录指定频道的降级 SQL 文件：重抓对应职位并直接推送云库。返回成功推送行数。"""
    if portal not in PORTAL_TYPES:
        raise SystemExit(f"unknown portal: {portal}（可选: {', '.join(PORTAL_TYPES)}）")
    pat_ts = "*" if ts == "all" else ts
    # ** 递归匹配：兼容归档到 output/archive_*/ 下的批次文件
    pattern = os.path.join(paths.OUTPUT_DIR, f"**/{portal}_{pat_ts}_batch_*.sql")
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        print(f"no sql files matched: {pattern}")
        raise SystemExit(1)

    target_ids = _extract_target_ids(files)
    print(f"[replay] {len(files)} files, {len(target_ids)} job_ids to replay",
          flush=True)

    headers = bytedance_source.build_headers(portal)
    portal_type = PORTAL_TYPES[portal]
    rows = []
    offset = 0
    while target_ids and offset < MAX_OFFSET:
        data = bytedance_source.fetch_page(portal_type, offset, headers)
        jobs = data.get("job_post_list") or []
        if not jobs:
            break
        for job in jobs:
            jid = str(job.get("id") or "")
            if jid in target_ids:
                target_ids.discard(jid)
                rows.append(bytedance_source.parse_job(job, portal))
        print(f"[replay] offset={offset} collected={len(rows)} "
              f"remaining={len(target_ids)}", flush=True)
        offset += bytedance_source.LIMIT
        time.sleep(0.8)

    if target_ids:
        print(f"[replay] WARN {len(target_ids)} ids not found on API anymore "
              f"(可能已下架), skip", flush=True)

    pushed = cloud_push.push_rows(rows)
    print(f"[replay] REPLAY_DONE collected={len(rows)} pushed={pushed}", flush=True)
    return pushed


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        print("用法: python3 replay_bytedance.py <portal> <批次时间戳前缀|all>")
        sys.exit(1)
    replay(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
