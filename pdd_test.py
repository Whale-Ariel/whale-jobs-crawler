"""拼多多社招职位抓取脚本（测试版）

两阶段流程：
  1. POST position/list  翻页拿全部职位的 code 列表（total 字段是字符串，需 int 转换）
  2. POST position/detail 按 code 逐条抓详情（referer 头必须带对应 code）

结果保存为 CSV，支持断点续传：已存在于 CSV 中的 code 会被跳过。

用法示例：
  python pdd_test.py                      # 全量抓取（78 页列表 + 全部详情）
  python pdd_test.py --max-pages 1 --max-details 3   # 小规模冒烟测试
  python pdd_test.py --page-size 100      # 试探 pageSize 上限（若接口支持可大幅减少请求数）
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

LIST_URL = "https://careers.pddglobalhr.com/api/recruit/position/list"
DETAIL_URL = "https://careers.pddglobalhr.com/api/recruit/position/detail"

# 从浏览器复制的 anti_content 反爬签名。
# 若服务端强校验导致失败，需要换成浏览器自动签名方案（Playwright），见 README 说明。
ANTI_CONTENT = (
    "0aqWfxUeMwVE9qdJX4qVAs4fklF1t0E_-NmlDgKnDzKztNVf_difYN1X_WU_4N3QjumtYR1Mg6ULi"
    "-LZaQ5mJVNeP8n09ycpTanGXyOGEqX06dnY_8n0TyX0E8X0EJn9xKuPIt730XFvMezsUfv-QHMv87M34"
    "pIMRKetBUbf5eS317Fs8AEtJUM-kpMt99ssQq0s_Pd09J50dJUYpdv69Otu-G0d3lNXyoypEJniEYns"
    "0_NQdfNC7TduUtYdx7ud3lYNYdvS0ltNSnpiTjnYCTXTs9Zl0gcO_VpIIv2PLPVnqS4j0FmHN9qQNNy"
    "x4o4lpreci0A8p_UIOVUGuaHONUTt0BifG40kfdpxB6Zvs3WH1WWS3RWFaKlS1zX8xV7jIIC77829T9"
    "QrBJO1DxOR9m"
)

BASE_HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "content-type": "application/json",
    "origin": "https://careers.pddglobalhr.com",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
    ),
}

CSV_FIELDS = [
    "code", "name", "job", "recruit_type", "work_location",
    "update_time", "job_duty", "serve_requirement", "bonus",
]

TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str | None) -> str:
    """清洗详情接口返回的 HTML 片段，保留纯文本。"""
    if not text:
        return ""
    text = TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def post_json(session: requests.Session, url: str, payload: dict,
              referer: str, retries: int = 3) -> dict:
    """带重试的 POST 请求；失败时抛出异常并打印服务端返回。"""
    headers = {**BASE_HEADERS, "referer": referer}
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.post(url, json=payload, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("success"):
                raise RuntimeError(f"接口返回失败: {data}")
            return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            wait = attempt * 2
            print(f"  [重试 {attempt}/{retries}] {exc}，{wait}s 后重试", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"请求最终失败: {url} -> {last_err}")


def fetch_list_page(session: requests.Session, page: int, page_size: int) -> dict:
    payload = {
        "job": "",
        "page": page,
        "pageSize": page_size,
        "name": "",
        "workLocationList": [],
        "anti_content": ANTI_CONTENT,
    }
    data = post_json(session, LIST_URL, payload,
                     referer="https://careers.pddglobalhr.com/jobs")
    return data["result"]


def fetch_detail(session: requests.Session, code: str) -> dict:
    payload = {"code": code, "anti_content": ANTI_CONTENT}
    # 关键点：referer 必须带上当前 code
    referer = f"https://careers.pddglobalhr.com/jobs/detail?code={code}"
    data = post_json(session, DETAIL_URL, payload, referer=referer)
    return data["result"]


def load_existing_codes(csv_path: Path) -> set[str]:
    """读取已有 CSV，返回已抓取的 code 集合（断点续传）。"""
    if not csv_path.exists():
        return set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return {row["code"] for row in csv.DictReader(f) if row.get("code")}


def main() -> None:
    parser = argparse.ArgumentParser(description="拼多多社招职位抓取")
    parser.add_argument("--page-size", type=int, default=10, help="每页条数（默认 10）")
    parser.add_argument("--max-pages", type=int, default=0, help="最多抓几页列表（0=全部）")
    parser.add_argument("--max-details", type=int, default=0, help="最多抓几条详情（0=全部）")
    parser.add_argument("--delay", type=float, default=0.5, help="详情请求间隔秒数")
    parser.add_argument("--out", type=Path, default=Path("pdd_jobs.csv"), help="输出 CSV 路径")
    args = parser.parse_args()

    session = requests.Session()

    # ---------- 阶段一：列表翻页 ----------
    print("[阶段一] 抓取职位列表 ...")
    first = fetch_list_page(session, page=1, page_size=args.page_size)
    total = int(first["total"])  # total 是字符串，需转换
    total_pages = math.ceil(total / args.page_size)
    pages_to_fetch = total_pages if args.max_pages <= 0 else min(args.max_pages, total_pages)
    print(f"  共 {total} 条职位，每页 {args.page_size} 条，总页数 {total_pages}，本次抓取 {pages_to_fetch} 页")

    items: list[dict] = list(first["list"])
    for page in tqdm(range(2, pages_to_fetch + 1), desc="列表翻页"):
        result = fetch_list_page(session, page=page, page_size=args.page_size)
        items.extend(result["list"])
        time.sleep(args.delay)

    # 按 code 去重（防止翻页边界重复）
    seen: set[str] = set()
    codes: list[str] = []
    for item in items:
        code = item.get("code")
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    print(f"  列表阶段拿到 {len(codes)} 个唯一 code")

    # ---------- 阶段二：详情抓取（断点续传） ----------
    done_codes = load_existing_codes(args.out)
    todo = [c for c in codes if c not in done_codes]
    if args.max_details > 0:
        todo = todo[: args.max_details]
    print(f"[阶段二] 待抓详情 {len(todo)} 条（已跳过 {len(done_codes)} 条历史记录）")

    file_exists = args.out.exists()
    with args.out.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()

        for code in tqdm(todo, desc="详情抓取"):
            try:
                d = fetch_detail(session, code)
            except RuntimeError as exc:
                print(f"\n  [跳过] {code}: {exc}", file=sys.stderr)
                continue
            writer.writerow({
                "code": d.get("code", code),
                "name": d.get("name", ""),
                "job": d.get("job", ""),
                "recruit_type": d.get("recruitType", ""),
                "work_location": d.get("workLocation", ""),
                "update_time": d.get("updateTime", ""),
                "job_duty": strip_html(d.get("jobDuty")),
                "serve_requirement": strip_html(d.get("serveRequirement")),
                "bonus": strip_html(d.get("bonus")),
            })
            f.flush()  # 每条落盘，中断不丢
            time.sleep(args.delay)

    print(f"完成，结果已写入 {args.out.resolve()}")


if __name__ == "__main__":
    main()
