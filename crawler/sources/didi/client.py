"""滴滴社招直连门户；校招和实习走 Moka，实习必须带用工类型筛选。"""
from urllib.parse import urlencode

from crawler.sources.base import PortalSource, SourceError
from crawler.sources.didi.moka import decode_moka, moka_bootstrap

ENTRIES = {
    'society': 'https://talent.didiglobal.com/social?page=1&size=10',
    'campus': 'https://campus.didiglobal.com/campus_apply/didiglobal/96064',
    'internship': 'https://app.mokahr.com/apply/didiglobal/6222',
}


class DidiClient(PortalSource):
    source = 'didi'
    portals = ('society', 'campus', 'internship')
    entries = ENTRIES
    batch_ids = {'campus': '96064', 'internship': '6222'}

    @property
    def needs_detail(self):
        return self.portal != 'society'

    def prepare(self):
        if self.portal == 'society':
            return
        data = moka_bootstrap(self.landing())
        if str(data.get('siteId')) != self.batch_id or data.get('org', {}).get('id') != 'didiglobal':
            raise SourceError('Moka招聘门户身份不一致')
        self.moka_iv = data['aesIv']

    def landing(self):
        response = self.session.get(self.entry_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()
        if 'login' in response.url.lower():
            raise SourceError('官网跳转登录页')
        return response.text

    def load_page(self, page):
        if self.portal == 'society':
            result = self.request('https://talent.didiglobal.com/recruit-portal-service/api/job/front/list?'
                                  + urlencode({'page': page, 'size': self.page_size}))
            if result.get('meta', {}).get('code') != 0:
                raise SourceError('滴滴查询失败')
            data = result.get('data')
            jobs = data.get('items') if isinstance(data, dict) else None
            total = data.get('total') if isinstance(data, dict) else None
            return jobs, total, 'jdId'
        host = 'https://campus.didiglobal.com' if self.portal == 'campus' else 'https://app.mokahr.com'
        result = self.request(host + '/api/outer/ats-apply/website/jobs/v2', {
            'orgId': 'didiglobal', 'siteId': int(self.batch_id), 'limit': self.page_size,
            'offset': (page - 1) * self.page_size, 'needStat': True,
            'site': 'campus' if self.portal == 'campus' else 'social',
            'commitments': ['实习'] if self.portal == 'internship' else [], 'locale': 'zh-CN',
        })
        data = decode_moka(result, self.moka_iv)
        return data.get('jobs'), data.get('jobStats', {}).get('total'), 'id'

    def hydrate(self, job):
        if self.known(job):
            return job
        raw = job['_crawler_raw']
        job_id = job['_crawler_id']
        if raw.get('jobDescription'):
            return job
        host = 'https://campus.didiglobal.com' if self.portal == 'campus' else 'https://app.mokahr.com'
        detail = decode_moka(self.request(host + '/api/outer/ats-apply/website/job', {
            'orgId': 'didiglobal', 'siteId': int(self.batch_id), 'jobId': job_id, 'locale': 'zh-CN',
        }), self.moka_iv)
        if not isinstance(detail, dict) or str(detail.get('id')) != job_id:
            raise SourceError('岗位详情ID不一致')
        return {**job, '_crawler_detail': detail}

    def parse(self, job):
        from crawler.sources.didi.parser import DidiParser
        return DidiParser().parse(job, self.portal)
