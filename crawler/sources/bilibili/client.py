"""哔哩哔哩公开职位。先取匿名 CSRF，再查列表。"""
from crawler.sources.base import PortalSource, SourceError
from crawler.sources.bilibili.parser import BilibiliParser


class BilibiliClient(PortalSource):
    source = 'bilibili'
    portals = ('society', 'campus', 'internship')
    entries = {
        'society': 'https://jobs.bilibili.com/social/positions',
        'campus': 'https://jobs.bilibili.com/campus/positions?type=3',
        'internship': 'https://jobs.bilibili.com/campus/positions?type=0',
    }

    def prepare(self):
        self.session.headers.update({'X-AppKey': 'ops.ehr-api.auth', 'X-UserType': '2'})
        data = self.request('https://jobs.bilibili.com/api/auth/v1/csrf/token')
        if data.get('code') != 0 or not data.get('data'):
            raise SourceError('B站匿名CSRF初始化失败')
        self.session.headers['X-CSRF'] = data['data']

    def load_page(self, page):
        kind = 'srs' if self.portal == 'society' else 'campus'
        kind_code = '3' if self.portal == 'campus' else '0'
        result = self.request(f'https://jobs.bilibili.com/api/{kind}/position/positionList', {
            'pageSize': self.page_size, 'pageNum': page,
            'positionTypeList': [] if self.portal == 'society' else [kind_code],
            'workTypeList': [] if self.portal == 'society' else [kind_code],
            'recruitType': 0 if self.portal == 'society' else None, 'onlyHotRecruit': 0,
        })
        if result.get('code') != 0:
            raise SourceError('B站查询错误：' + str(result.get('message')))
        data = result.get('data')
        jobs = data.get('list') if isinstance(data, dict) else None
        total = data.get('total') if isinstance(data, dict) else None
        return jobs, total, 'id'

    def parse(self, job):
        return BilibiliParser().parse(job, self.portal)
