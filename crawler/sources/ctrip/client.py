"""携程职位列表。同一岗位会换广告 id，按 fromId 去重。"""
from crawler.sources.base import PortalSource, SourceError
from crawler.sources.ctrip.parser import CtripParser


class CtripClient(PortalSource):
    source = 'ctrip'
    portals = ('society', 'campus')
    entries = {
        'society': 'https://job.ctrip.com/#/experienced/jobList',
        'campus': 'https://job.ctrip.com/#/campus/jobList',
    }

    def load_page(self, page):
        result = self.request('https://job.ctrip.com/api/hrrecruit/getJobAd', {
            'condition': {'fromId': [], 'keyword': '', 'kind': [], 'country': [], 'city': [], 'bucode': [],
                          'jobFamilyCode': [], 'jobFamilyGroupCode': [],
                          'category': 1 if self.portal == 'society' else 2},
            'pager': {'index': page, 'size': self.page_size},
        })
        if str(result.get('retCode')) != '201':
            raise SourceError('携程查询失败：' + str(result.get('retMessage')))
        data = result.get('retValue')
        jobs = data.get('recruitJobAdList') if isinstance(data, dict) else None
        total = data.get('total') if isinstance(data, dict) else None
        seen = set()
        stable = []
        for job in jobs or []:
            from_id = str(job.get('fromId') or '')
            if not from_id:
                raise SourceError('携程岗位缺少 fromId，拒绝使用不稳定的 ad id 兜底')
            if from_id in seen:
                raise SourceError('携程本页 fromId 重复，接口排序不稳定，禁止跨页复用')
            seen.add(from_id)
            stable.append(job)
        return stable, total, 'fromId'

    def parse(self, job):
        return CtripParser().parse(job, self.portal)
