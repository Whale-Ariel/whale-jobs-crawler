# -*- coding: utf-8 -*-
"""腾讯招聘 API 请求与字段映射。社招 attrId=1，校招 attrId=2,3，默认50条/页。"""
import json
import os
import time
import urllib.parse
import urllib.request

from crawler.sources.base import Source
from crawler.sources.tencent.parser import parse_post

BASE_URL = "https://careers.tencent.com/tencentcareer/api/post/Query"
PAGE_SIZE = 50  # 每页条数，越大请求次数越少（官方页面默认 10，此处取 50 提速）
SOURCE = "tencent"

# 无 Cookie 时使用的最小请求头（已验证 API 可直接访问）
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "referer": "https://careers.tencent.com/search.html",
    "user-agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"),
}

# 腾讯 API 返回的两种招聘类型参数
# 社招：attrId=1（社会招聘）；校招：attrId=2,3（官方校招筛选条件）
ATTR_IDS = {"society": "1", "campus": "2,3"}


def state_ns(portal: str) -> str:
    """状态命名空间：与历史文件名保持一致（tencent_known_ids_{portal}.json 等）。"""
    return f"tencent_{portal}"


def fetch_page(portal: str, page_index: int, retries: int = 4, page_size: int = 50) -> dict:
    """请求一页腾讯职位列表（GET），带重试与指数退避。"""
    params = {
        "timestamp": str(int(time.time() * 1000)),
        "countryId": "", "cityId": "", "bgIds": "", "productId": "",
        "categoryId": "", "parentCategoryId": "",
        "attrId": ATTR_IDS[portal],
        "keyword": "", "pageIndex": str(page_index),
        "pageSize": str(page_size), "language": "zh-cn", "area": "cn",
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method="GET")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("Code") != 200:
                raise RuntimeError(f"API Code={data.get('Code')} Msg={data.get('Msg')}")
            content = data.get("Data")
            if not isinstance(content, dict) or not isinstance(content.get("Posts"), list) or "Count" not in content:
                raise RuntimeError("接口响应结构变化，拒绝将异常响应视为空职位列表")
            return content
        except Exception as e:  # noqa: BLE001
            last_err = e
            wait = 2 ** attempt
            print(f"  [retry] tencent-{portal} page={page_index} attempt={attempt + 1} "
                  f"err={e}, sleep {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"fetch_page failed: tencent-{portal} page={page_index}: {last_err}")


class TencentClient(Source):
    """腾讯列表按页码翻页，断点文件沿用 tencent_society / tencent_campus。"""

    source = SOURCE
    portals = ('society', 'campus')

    def __init__(self, portal, page_size=50, queue=None, skip_existing=True):
        if portal not in ATTR_IDS:
            raise ValueError('无效的腾讯招聘频道')
        super().__init__(portal, page_size, queue, skip_existing)

    @property
    def namespace(self):
        return state_ns(self.portal)

    def fetch(self, page):
        data = fetch_page(self.portal, page, page_size=self.page_size)
        return data.get('Posts') or [], data.get('Count')

    def parse(self, post):
        return parse_post(post, self.portal)


def run(portal: str, full: bool = False,
        max_pages_incremental: int = 50, request_interval: float = 0.4,
        queue=None, page_size: int = 50, skip_existing=True):
    client = TencentClient(portal, page_size=page_size, queue=queue, skip_existing=skip_existing)
    return client.execute(full=full, max_pages=max_pages_incremental, interval=request_interval, queue=queue)
