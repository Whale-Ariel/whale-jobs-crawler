# -*- coding: utf-8 -*-
"""字节招聘 API 请求与字段映射，默认50条/页；可靠分页和本地落队由 crawl_engine 统一负责。"""
import json
import os
import time
import urllib.request

from crawler.sources.base import Source
from crawler.sources.bytedance.parser import parse_job

BASE_URL = "https://jobs.bytedance.com/api/v1/search/job/posts"
LIMIT = 50  # 默认每页50条
SOURCE = "bytedance"


def build_headers(portal: str) -> dict:
    if portal == "society":
        channel, referer, path = "office", "https://jobs.bytedance.com/experienced/position", "society"
    else:
        channel, referer, path = "campus", "https://jobs.bytedance.com/campus/position", "campus"
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://jobs.bytedance.com",
        "Portal-Channel": channel,
        "Portal-Platform": "pc",
        "Referer": referer,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
        "accept-language": "zh-CN",
        "website-path": path,
    }


def fetch_page(portal_type: int, offset: int, headers: dict, retries: int = 4, page_size: int = 50) -> dict:
    """请求一页职位列表，带重试与指数退避。"""
    query = (f"?keyword=&limit={page_size}&offset={offset}"
             f"&job_category_id_list=&tag_id_list=&location_code_list=&subject_id_list="
             f"&recruitment_id_list=&portal_type={portal_type}"
             f"&job_function_id_list=&storefront_id_list=&portal_entrance=1")
    payload = {
        "keyword": "", "limit": page_size, "offset": offset,
        "job_category_id_list": [], "tag_id_list": [], "location_code_list": [],
        "subject_id_list": [], "recruitment_id_list": [], "portal_type": portal_type,
        "job_function_id_list": [], "storefront_id_list": [], "portal_entrance": 1,
    }
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                BASE_URL + query,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") != 0:
                raise RuntimeError(f"API code={data.get('code')} message={data.get('message')}")
            content = data.get("data")
            if not isinstance(content, dict) or not isinstance(content.get("job_post_list"), list) or "count" not in content:
                raise RuntimeError("接口响应结构变化，拒绝将异常响应视为空职位列表")
            return content
        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = 2 ** attempt
            print(f"  [retry] offset={offset} attempt={attempt + 1} err={e}, sleep {wait}s",
                  flush=True)
            time.sleep(wait)
    raise RuntimeError(f"fetch_page failed at offset={offset}: {last_err}")


class BytedanceClient(Source):
    """字节列表按 offset 翻页，命名空间保持历史的 society/campus。"""

    source = SOURCE
    portals = ('society', 'campus')
    portal_types = {'society': 2, 'campus': 3}

    def __init__(self, portal, page_size=50, queue=None, skip_existing=True, portal_type=None):
        super().__init__(portal, page_size, queue, skip_existing)
        expected = self.portal_types[portal]
        if portal_type is None:
            portal_type = expected
        if portal_type != expected:
            raise ValueError('无效的字节招聘频道')
        self.portal_type = portal_type
        self.headers = build_headers(portal)

    @property
    def namespace(self):
        return self.portal

    def fetch(self, offset):
        data = fetch_page(self.portal_type, offset, self.headers, page_size=self.page_size)
        return data.get('job_post_list') or [], data.get('count')

    def parse(self, job):
        return parse_job(job, self.portal)

    def execute(self, **kwargs):
        kwargs['offset_mode'] = True
        return super().execute(**kwargs)


def run(portal: str, portal_type: int, full: bool = False,
        max_pages_incremental: int = 50, request_interval: float = 0.4,
        queue=None, page_size: int = 50, skip_existing=True):
    client = BytedanceClient(portal, page_size=page_size, queue=queue,
                             skip_existing=skip_existing, portal_type=portal_type)
    return client.execute(full=full, max_pages=max_pages_incremental,
                          interval=request_interval, queue=queue)
