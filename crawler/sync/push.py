# -*- coding: utf-8 -*-
"""云端招聘表 upsert 与 SQL 导出。失败由同步调用方保留本地队列；按来源、招聘形式、ID 联合去重。"""
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
import os

from crawler import paths
from crawler.core.schema import BOOL_COLS, COLUMNS, INT_COLS, JSONB_COLS
from crawler.settings import cloud_access_key

CLOUD_ENDPOINT = os.environ.get("CRAWLER_CLOUD_ENDPOINT", "https://bytedance-jobs.app.workbuddy.host").rstrip("/")
# 凭证从环境变量加载；新表以来源+招聘形式+职位 ID 作为联合主键。
REST_TABLE_URL = f"{CLOUD_ENDPOINT}/.cloud/database/rest/recruitment_jobs?on_conflict=source,recruitment_type,batch_id,source_site,job_id"
PUSH_BATCH_SIZE = 30
PUSH_INTERVAL = 10  # 批间隔秒数（WAF 限频下保守一点）
WAF_COOLDOWN = 90  # 403 后的冷却退避基数（秒，随重试次数递增）


def push_rows(rows: list, retries: int = 8) -> int:
    """通过 PostgREST 批量 upsert（覆盖变化字段）。返回成功提交的行数。

    全部重试失败时抛 RuntimeError；调用方（同步程序/补录脚本）负责降级处理。
    """
    if not rows:
        return 0
    if not cloud_access_key():
        raise RuntimeError("请设置 CRAWLER_CLOUD_ACCESS_KEY，并先执行 migrations/001_recruitment_jobs.sql 、002_alibaba_campus_batches.sql、003_alibaba_society_sites.sql")
    inserted = 0
    for i in range(0, len(rows), PUSH_BATCH_SIZE):
        if i:
            time.sleep(PUSH_INTERVAL)
        batch = rows[i:i + PUSH_BATCH_SIZE]
        body = json.dumps(batch, ensure_ascii=False).encode("utf-8")
        last_err = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    REST_TABLE_URL, data=body, method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "x-wb-webapp-access-key": cloud_access_key(),
                        "Origin": CLOUD_ENDPOINT,
                        "Prefer": "resolution=merge-duplicates,count=exact",
                    })
                with urllib.request.urlopen(req, timeout=60) as resp:
                    content_range = resp.headers.get("Content-Range", "")
                    # 形如 "*/35"
                    if "/" in content_range:
                        try:
                            inserted += int(content_range.split("/")[-1])
                        except ValueError:
                            inserted += len(batch)
                    else:
                        inserted += len(batch)
                last_err = None
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="replace")[:300]
                last_err = f"HTTP {e.code}: {detail}"
                if e.code in (400, 401, 404, 409, 422):
                    raise RuntimeError(f"cloud push configuration/schema failed: {last_err}")
                if e.code == 403:
                    wait = WAF_COOLDOWN * (attempt + 1)
                    print(f"  [WAF] batch {i // PUSH_BATCH_SIZE + 1} 403 "
                          f"(attempt {attempt + 1}), cooldown {wait}s", flush=True)
                    time.sleep(wait)
                    continue
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
            if last_err:
                time.sleep(2 ** min(attempt, 4))
        if last_err:
            raise RuntimeError(f"cloud push failed at batch {i // PUSH_BATCH_SIZE + 1}: {last_err}")
    return inserted


# ---------- SQL 降级备份 ----------

def _sql_value(col, v):
    if v is None:
        return "NULL"
    if col in BOOL_COLS:
        return "TRUE" if v else "FALSE"
    if col in INT_COLS:
        try:
            return str(int(v))
        except (TypeError, ValueError):
            return "NULL"
    if col in JSONB_COLS:
        s = json.dumps(v, ensure_ascii=False).replace("'", "''")
        return f"'{s}'::jsonb"
    s = str(v).replace("'", "''")
    return f"'{s}'"


def rows_to_sql(rows: list) -> str:
    cols = ", ".join(COLUMNS)
    values = []
    for row in rows:
        vals = ", ".join(_sql_value(c, row.get(c)) for c in COLUMNS)
        values.append(f"({vals})")
    return (
        f"INSERT INTO recruitment_jobs ({cols}) VALUES\n"
        + ",\n".join(values)
        + "\nON CONFLICT (source, recruitment_type, batch_id, source_site, job_id) DO UPDATE SET "
        + ", ".join(f"{c}=EXCLUDED.{c}" for c in COLUMNS if c not in {"source", "recruitment_type", "batch_id", "source_site", "job_id"})
    )


def write_sql_batches(rows: list, prefix: str, batch_size: int = 30,
                      out_dir: str = None) -> list:
    """把 rows 分批写成 INSERT SQL 文件，文件名 {prefix}_{时间戳}_batch_NNNN.sql。"""
    if not rows:
        return []
    out_dir = out_dir or paths.OUTPUT_DIR
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.abspath(out_dir)
    os.makedirs(out_path, exist_ok=True)
    paths_list = []
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        path = os.path.join(out_path, f"{prefix}_{ts}_batch_{i // batch_size + 1:04d}.sql")
        with open(path, "w", encoding="utf-8") as f:
            f.write(rows_to_sql(batch))
        paths_list.append(path)
    return paths_list
