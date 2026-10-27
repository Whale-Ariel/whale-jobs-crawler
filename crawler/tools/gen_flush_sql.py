# -*- coding: utf-8 -*-
"""把 output/_flush_2947_rows.json 切成 exec_sql 直灌批次（ON CONFLICT DO UPDATE）。"""
import base64
import json
import os

from crawler.sync import push as cloud_push

ROWS = json.load(open('output/_flush_2947_rows.json', encoding='utf-8'))
BATCH = 25
OUT = 'output/_flush_sql'
os.makedirs(OUT, exist_ok=True)

cols = ", ".join(cloud_push.COLUMNS)
non_pk = [c for c in cloud_push.COLUMNS
          if c not in {"source", "recruitment_type", "batch_id", "source_site", "job_id"}]
upset = ", ".join(f"{c}=EXCLUDED.{c}" for c in non_pk)


def row_values(row):
    return ", ".join(cloud_push._sql_value(c, row.get(c)) for c in cloud_push.COLUMNS)


def build(values):
    return (f"INSERT INTO recruitment_jobs ({cols}) VALUES\n"
            + ",\n".join(values)
            + f"\nON CONFLICT (source,recruitment_type,batch_id,source_site,job_id) DO UPDATE SET {upset};")


total = 0
for i in range(0, len(ROWS), BATCH):
    chunk = ROWS[i:i + BATCH]
    values = [f"({row_values(r)})" for r in chunk]
    sql = build(values)
    b64 = base64.b64encode(sql.encode('utf-8')).decode('ascii')
    n = i // BATCH + 1
    with open(f"{OUT}/batch_{n:04d}.b64", 'w') as f:
        f.write(b64)
    total += len(chunk)

print("total chunks:", (len(ROWS) + BATCH - 1) // BATCH, "total rows:", total)
