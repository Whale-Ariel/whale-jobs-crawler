"""拼多多校招列表固定 10 条，详情补任职要求。"""
from crawler.sources.base import PortalSource, SourceError
from crawler.sources.pdd.parser import PddParser


class PddClient(PortalSource):
    source = 'pdd'
    portals = ('campus',)
    entries = {'campus': 'https://careers.pddglobalhr.com/campus/grad'}
    needs_detail = True

    def cap_page_size(self, page_size):
        return min(page_size, 10)

    def load_page(self, page):
        result = self.request('https://careers.pddglobalhr.com/api/careers/api/recruit/position/list',
                              {'page': page, 'pageSize': self.page_size})
        if result.get('success') is not True:
            raise SourceError('拼多多列表查询失败')
        data = result.get('result')
        jobs = data.get('list') if isinstance(data, dict) else None
        total = data.get('total') if isinstance(data, dict) else None
        return jobs, total, 'id'

    def hydrate(self, job):
        if self.known(job):
            return job
        job_id = job['_crawler_id']
        data = self.request('https://careers.pddglobalhr.com/api/careers/api/recruit/position/detail', {'id': job_id})
        if data.get('success') is not True:
            raise SourceError('拼多多详情查询失败')
        detail = data.get('result')
        if not isinstance(detail, dict) or str(detail.get('id')) != job_id:
            raise SourceError('岗位详情ID不一致')
        return {**job, '_crawler_detail': detail}

    def parse(self, job):
        return PddParser().parse(job, self.portal)
