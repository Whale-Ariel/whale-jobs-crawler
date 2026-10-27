"""各公司爬虫的共同任务：会话请求、分页收口、详情补全、交给引擎落库。

公司差异放在子类的 load_page / parse，不在这里按公司名分支。
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from crawler.core.schema import COLUMNS
from crawler.taxonomy import classify


class SourceError(RuntimeError):
    pass


class Source:
    """一个公司的一个招聘入口。子类实现 fetch 与 parse。"""

    source = ''
    portals = ()
    batch_ids = {}

    def __init__(self, portal, page_size=50, queue=None, skip_existing=True):
        if portal not in self.portals:
            raise ValueError('不支持的公司或招聘形式')
        self.portal = portal
        self.page_size = self.cap_page_size(page_size)
        self.queue = queue
        self.skip_existing = skip_existing
        self.seen = set()

    def cap_page_size(self, page_size):
        return page_size

    @property
    def batch_id(self):
        return self.batch_ids.get(self.portal, '')

    @property
    def namespace(self):
        base = f'{self.source}_{self.portal}'
        return f'{base}_{self.batch_id}' if self.batch_id else base

    def context(self):
        return {'batch_id': self.batch_id} if self.batch_id else {}

    def fetch(self, cursor):
        raise NotImplementedError

    def parse(self, job):
        raise NotImplementedError

    def execute(self, *, full=False, max_pages=50, interval=0.4, queue=None, offset_mode=False):
        from crawler.core.engine import crawl
        active = queue if queue is not None else self.queue
        return crawl(source=self.source, portal=self.portal, namespace=self.namespace,
                     fetch=self.fetch, parse=self.parse, page_size=self.page_size,
                     offset_mode=offset_mode, full=full, max_pages=max_pages, interval=interval,
                     queue=active, context=self.context() or None, skip_existing=self.skip_existing)


class JsonSource(Source):
    """带重试的 JSON 会话。列表请求走 request，分页校验走 finish_*。"""

    entries = {}

    def __init__(self, portal, page_size=50, queue=None, skip_existing=True):
        super().__init__(portal, page_size, queue, skip_existing)
        self.entry_url = self.entries.get(portal) or self.entries.get('society') or ''
        self._sessions = threading.local()

    @property
    def session(self):
        if not hasattr(self._sessions, 'value'):
            self._sessions.value = requests.Session()
        return self._sessions.value

    def request(self, url, data=None, *, form=False, headers=None):
        base = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json',
                'Referer': self.entry_url or ''}
        if data is not None:
            base['Content-Type'] = 'application/x-www-form-urlencoded;charset=utf-8' if form else 'application/json'
        base.update(headers or {})
        body = None
        if data is not None:
            import urllib.parse
            body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
        for attempt in range(5):
            try:
                response = self.session.request('POST' if body is not None else 'GET', url,
                                                data=body, headers=base, timeout=30)
                if 'login' in response.url.lower():
                    raise SourceError('官网跳转登录页：' + response.url.split('?')[0])
                if response.status_code in (401, 403):
                    raise SourceError(f'官网拒绝访问 HTTP {response.status_code}')
                response.raise_for_status()
                try:
                    result = response.json()
                except ValueError as error:
                    raise SourceError('接口未返回JSON，可能是登录页或访问限制') from error
                if not isinstance(result, dict):
                    raise SourceError('JSON响应不是对象')
                return result
            except requests.RequestException:
                if attempt == 4:
                    raise
                time.sleep(1 + attempt)

    def finish_lenient(self, jobs, total, id_key):
        """跨页重复的 ID 跳过，整页都没有新 ID 时失败。"""
        if total is None or isinstance(total, bool) or not str(total).isdigit():
            raise SourceError('接口职位总数缺失或无效')
        total = int(total)
        if jobs is None and total == 0:
            jobs = []
        if not isinstance(jobs, list) or len(jobs) > self.page_size:
            raise SourceError('职位列表结构异常')
        ids = [str(job.get(id_key) or '') for job in jobs]
        fresh_jobs, fresh_ids = [], []
        for job, job_id in zip(jobs, ids):
            if not job_id:
                raise SourceError('分页返回缺失ID，停止以避免静默漏抓')
            if job_id in self.seen or job_id in fresh_ids:
                continue
            fresh_jobs.append(job)
            fresh_ids.append(job_id)
        if not fresh_ids:
            raise SourceError('本页无新增职位ID')
        self.seen.update(fresh_ids)
        fresh_jobs = self.decorate(fresh_jobs, fresh_ids)
        return [{**job, 'id': job.get('id', job_id), '_crawler_id': job_id}
                for job, job_id in zip(fresh_jobs, fresh_ids)], total

    def decorate(self, jobs, ids):
        return jobs

    def finish_strict(self, jobs, total, id_key):
        """页内或跨页重复 ID 直接失败，避免把重叠页当成完整列表。"""
        if total is None or isinstance(total, bool) or not str(total).isdigit():
            raise SourceError('接口缺少有效总数')
        total = int(total)
        if jobs is None and total == 0:
            jobs = []
        if not isinstance(jobs, list) or len(jobs) > self.page_size:
            raise SourceError('岗位列表或分页大小异常')
        ids = [str(job.get(id_key) or '') for job in jobs]
        if any(not job_id for job_id in ids) or len(set(ids)) != len(ids) or self.seen.intersection(ids):
            raise SourceError('接口分页出现重复或缺少岗位ID')
        self.seen.update(ids)
        wrapped = [{'id': job_id, '_crawler_id': job_id, '_crawler_raw': job} for job_id, job in zip(ids, jobs)]
        if self.needs_detail:
            with ThreadPoolExecutor(max_workers=4) as pool:
                wrapped = list(pool.map(self.hydrate, wrapped))
        return wrapped, total

    @property
    def needs_detail(self):
        return False

    def hydrate(self, job):
        return job

    def known(self, job):
        from crawler.core.queue import default_queue
        queue = self.queue if self.queue is not None else default_queue()
        return self.skip_existing and queue.contains(
            self.source, self.portal, job['_crawler_id'], batch_id=self.batch_id)


class LenientSource(JsonSource):
    """先查列表，再按职位 ID 丢掉跨页重复。"""

    def fetch(self, page):
        jobs, total, id_key = self.load_page(page)
        return self.finish_lenient(jobs, total, id_key)

    def load_page(self, page):
        raise NotImplementedError


class PortalSource(JsonSource):
    """先做官网初始化，再按严格分页收口。需要详情的子类打开 needs_detail。"""

    def __init__(self, portal, page_size=50, queue=None, skip_existing=True):
        super().__init__(portal, page_size, queue, skip_existing)
        self.initialized = False
        if self.queue is None:
            from crawler.core.queue import default_queue
            self.queue = default_queue()

    def prepare(self):
        return None

    def initialize(self):
        self.ensure_ready()

    def ensure_ready(self):
        if self.initialized:
            return
        self.prepare()
        self.initialized = True

    def fetch(self, page):
        self.ensure_ready()
        jobs, total, id_key = self.load_page(page)
        return self.finish_strict(jobs, total, id_key)

    def load_page(self, page):
        raise NotImplementedError


class JobParser:
    """把一条原始岗位收成 48 字段。子类只填本公司字段。"""

    source = ''
    missing_message = '职位缺少ID、名称或详情链接'

    def blank(self, portal, raw, batch_id=''):
        row = dict.fromkeys(COLUMNS)
        row.update(classify(self.source, portal, raw))
        row.update(job_id='', type=portal, source=self.source, raw_data=raw, batch_id=batch_id)
        return row

    def places(self, row, cities, units):
        row.update(city_list=cities, city_name='、'.join(cities) or None, business_units=units,
                   business_unit=units[0] if len(units) == 1 else None)
        return row

    def require(self, row, job_id):
        if not job_id or not row['title'] or not row['job_url']:
            raise SourceError(self.missing_message)
        row['job_id'] = job_id
        return row

    def parse(self, post, portal):
        raise NotImplementedError


def public_raw(post, drop_synthetic_id=False):
    hidden = {'_crawler_id', '_crawler_city_names'}
    return {key: value for key, value in post.items()
            if key not in hidden and not (drop_synthetic_id and key == 'id')}
