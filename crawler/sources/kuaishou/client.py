"""快手公开列表。签名是官网前端随请求发送的参数，不是登录凭证。"""
import hashlib
import hmac
import time
import urllib.parse

from crawler.sources.base import LenientSource, SourceError
from crawler.sources.kuaishou.parser import KuaishouParser

PUBLIC_SIGN_KEY = '652f962a-0575-4575-98d2-f04e2291bee2'
CAMPUS_BATCH = '20271779425607'


def kuaishou_headers(params, timestamp=None):
    ts = str(timestamp if timestamp is not None else int(time.time() * 1000))
    parts = []
    for key, value in sorted(params.items()):
        values = value if isinstance(value, list) else [value]
        values = sorted(str(item) for item in values if item is not None and item != '')
        if values:
            encoded = ','.join(urllib.parse.quote_plus(item, safe="~!*'()-._") for item in values)
            parts.append(key + '=' + encoded)
    message = ts + '&'.join(parts) + PUBLIC_SIGN_KEY
    sign = hmac.new(PUBLIC_SIGN_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {'signTimestamp': ts, 'sign': sign}


class KuaishouClient(LenientSource):
    source = 'kuaishou'
    portals = ('society', 'internship', 'campus')
    batch_ids = {'campus': CAMPUS_BATCH}
    entries = {
        'society': 'https://zhaopin.kuaishou.cn/#/official/social/?workLocationCode=domestic',
        'internship': 'https://zhaopin.kuaishou.cn/#/official/trainee/?workLocationCode=domestic',
        'campus': 'https://campus.kuaishou.cn/recruit/campus/e/#/campus/jobs?recruitSubProjectCodes=' + CAMPUS_BATCH,
    }

    def __init__(self, portal, page_size=50, queue=None, skip_existing=True):
        super().__init__(portal, page_size, queue, skip_existing)
        self.city_names = None

    def load_page(self, page):
        if self.portal == 'campus':
            result = self.request('https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple',
                                  {'pageNum': page, 'pageSize': self.page_size, 'recruitSubProjectCodes': [CAMPUS_BATCH]})
        else:
            query = {'pageNum': page, 'pageSize': self.page_size, 'workLocationCode': 'domestic',
                     'positionNatureCode': 'C001' if self.portal == 'society' else 'C002'}
            if self.portal == 'society':
                query['recruitProject'] = 'socialr'
            result = self.request('https://zhaopin.kuaishou.cn/recruit/e/api/v1/open/positions/simple?'
                                  + urllib.parse.urlencode(query), headers=kuaishou_headers(query))
        if result.get('code') != 0:
            raise SourceError('快手返回错误：' + str(result.get('message')))
        data = result.get('result')
        if not isinstance(data, dict):
            raise SourceError('接口数据结构缺失')
        return data.get('list'), data.get('total'), 'id'

    def decorate(self, jobs, ids):
        if self.portal == 'campus':
            return jobs
        if self.city_names is None:
            self.city_names = {}
            nature = 'C001' if self.portal == 'society' else 'C002'
            labels = self.request('https://zhaopin.kuaishou.cn/recruit/e/api/v1/open/positions/label?'
                                  + urllib.parse.urlencode({'channelCode': 'G002', 'positionNatureCode': nature}))
            if labels.get('code') != 0 or not isinstance(labels.get('result'), dict):
                raise SourceError('快手城市字典读取失败')
            for region in ('domestic', 'foreign'):
                for city in labels['result'].get(region) or []:
                    self.city_names[city['code']] = city['name']
        return [{**job, '_crawler_city_names': [self.city_names[code] for code in
                 (job.get('workLocationsCode') or [job.get('workLocationCode')]) if code in self.city_names]}
                for job in jobs]

    def parse(self, job):
        return KuaishouParser().parse(job, self.portal)
