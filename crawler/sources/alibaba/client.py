"""集团校招单站客户端：正常建立会话，动态发现批次、组织和项目子集。"""
from dataclasses import dataclass, field
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = 'https://campus-talent.alibaba.com'
CHANNEL = 'new_campus_group_official_site'


@dataclass
class Batch:
    id: str
    name: str
    portal: str
    has_ali_star: bool = False
    metadata: dict = field(default_factory=dict)


def parse_batches(content):
    """相同 batchId 只抓一次；topTalentPlan/aliStar仅标记对应批次。"""
    if not isinstance(content, dict):
        raise RuntimeError('阿里招聘批次结构错误')
    batches = {}
    star_ids = set()
    for category, entries in content.items():
        if category == 'sequence':
            continue
        if not isinstance(entries, list):
            raise RuntimeError('阿里招聘批次列表结构错误')
        for item in entries:
            if not isinstance(item, dict) or not item.get('id'):
                raise RuntimeError('阿里招聘批次缺少ID')
            bid = str(item['id'])
            if category in {'topTalentPlan', 'alistar'} or item.get('type') == 'aliStar':
                star_ids.add(bid)
                continue
            name = item.get('name') or bid
            portal = 'graduate' if category == 'graduate' else (
                'research_intern' if '研究' in name else 'regular_intern' if '日常' in name else 'internship')
            batches[bid] = Batch(bid, name, portal, metadata=item)
    for bid in star_ids:
        if bid not in batches:
            entries = [i for k,v in content.items() if k != 'sequence' and isinstance(v,list)
                       for i in v if isinstance(i,dict) and str(i.get('id')) == bid]
            batches[bid] = Batch(bid, entries[0].get('name',bid), 'graduate', metadata=entries[0])
        batches[bid].has_ali_star = True
    if not batches:
        raise RuntimeError('官网未返回可用校招批次，拒绝使用写死的旧批次')
    return list(batches.values())


class CampusClient:
    def __init__(self, opener=None, interval=0.2, base_url=BASE_URL, entry_path="/campus/position?lang=zh", api_prefix=""):
        self.base_url = base_url.rstrip("/")
        self.entry_path = entry_path
        self.api_prefix = api_prefix
        self.cookies = http.cookiejar.CookieJar()
        self.opener = opener or urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.csrf = None
        self.interval = interval
        self.last_request = 0

    def _open(self, request):
        wait = self.interval - (time.monotonic()-self.last_request)
        if wait > 0:
            time.sleep(wait)
        try:
            return self.opener.open(request, timeout=30)
        finally:
            self.last_request = time.monotonic()

    def bootstrap(self):
        request = urllib.request.Request(self.base_url+self.entry_path, headers={'User-Agent':'Mozilla/5.0'})
        with self._open(request) as response:
            html = response.read().decode('utf-8')
        match = re.search(r'__token__\s*:\s*"([^"]+)"', html)
        token = match[1] if match else next((c.value for c in self.cookies if c.name == 'XSRF-TOKEN'), None)
        if not token:
            raise RuntimeError('招聘首页未返回CSRF，会话初始化失败')
        self.csrf = token

    def call(self, path, payload=None, retries=4):
        refreshed = False
        for attempt in range(retries):
            try:
                if not self.csrf:
                    self.bootstrap()
                url = self.base_url+self.api_prefix+path+'?'+urllib.parse.urlencode({'_csrf':self.csrf})
                request = urllib.request.Request(url, data=json.dumps(payload or {}).encode(), method='POST',
                    headers={'User-Agent':'Mozilla/5.0', 'Content-Type':'application/json',
                             'Origin':self.base_url, 'Referer':self.base_url+self.entry_path})
                with self._open(request) as response:
                    data = json.load(response)
                if not isinstance(data,dict) or data.get('success') is not True:
                    code = data.get('errorCode') if isinstance(data,dict) else 'invalid JSON'
                    raise RuntimeError(f'阿里招聘接口拒绝请求（{code}）')
                return data.get('content')
            except urllib.error.HTTPError as error:
                if error.code in (401,403):
                    if not refreshed and attempt+1 < retries:
                        self.csrf = None
                        refreshed = True
                        continue
                    raise RuntimeError(f'阿里招聘会话刷新后仍被拒绝（HTTP {error.code}）') from None
                if error.code < 500 and error.code != 429:
                    raise RuntimeError(f'阿里招聘接口HTTP {error.code}') from None
            except (urllib.error.URLError, TimeoutError):
                pass
            if attempt+1 < retries:
                time.sleep(2**attempt)
        raise RuntimeError(f'阿里招聘接口请求失败：{path}')

    def batches(self):
        return parse_batches(self.call('/searchCondition/listBatch'))

    def conditions(self, batch):
        result = self.call('/searchCondition/list', {'batchId':batch.id,'channel':CHANNEL,'language':'zh'})
        if not isinstance(result,dict) or not isinstance(result.get('searchItems'),list):
            raise RuntimeError('校招筛选树结构错误')
        return result

    def search(self, batch, page, page_size=50, ali_star=None):
        body = dict(batchId=batch.id, pageIndex=page, pageSize=page_size, channel=CHANNEL, language='zh')
        if ali_star is not None:
            body['aliStar'] = 'Y' if ali_star else 'N'
        result = self.call('/position/search', body)
        if not isinstance(result,dict) or not isinstance(result.get('datas'),list) or not isinstance(result.get('totalCount'),int):
            raise RuntimeError('校招搜索响应结构错误')
        return result

    def star_ids(self, batch, page_size=50):
        ids = set()
        page = 1
        while True:
            result = self.search(batch,page,page_size,ali_star=True)
            posts = result['datas']
            if not posts and len(ids) < result['totalCount']:
                raise RuntimeError('阿里星列表未完成却返回空页')
            ids.update(str(post['id']) for post in posts)
            if page*page_size >= result['totalCount']:
                return ids
            page += 1

    def organizations(self, position_id):
        result = self.call('/position/queryCircleDept', {'id':position_id,'language':'zh'})
        if not isinstance(result,list):
            raise RuntimeError('职位组织关系结构错误')
        return result
