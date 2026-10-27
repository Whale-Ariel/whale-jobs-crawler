"""米哈游职位。校招项目 13、实习项目 4，详情里再核对一次。"""
from crawler.sources.base import PortalSource, SourceError
from crawler.sources.mihoyo.parser import MihoyoParser


class MihoyoClient(PortalSource):
    source = 'mihoyo'
    portals = ('society', 'campus', 'internship')
    entries = {
        'society': 'https://jobs.mihoyo.com/#/position',
        'campus': 'https://jobs.mihoyo.com/#/campus/position?projectIds%5B0%5D=13',
        'internship': 'https://jobs.mihoyo.com/#/campus/position?projectIds%5B0%5D=4',
    }
    batch_ids = {'campus': '13', 'internship': '4'}
    needs_detail = True

    def load_page(self, page):
        query = {'pageNo': page, 'pageSize': self.page_size,
                 'hireType': 0 if self.portal == 'society' else 1, 'channelDetailIds': [1]}
        if self.portal != 'society':
            query['projectIds'] = [int(self.batch_id)]
        result = self.request('https://ats.openout.mihoyo.com/ats-portal/v1/job/list', query)
        if result.get('code') != 0:
            raise SourceError('米哈游列表查询失败')
        data = result.get('data')
        jobs = data.get('list') if isinstance(data, dict) else None
        total = data.get('total') if isinstance(data, dict) else None
        return jobs, total, 'id'

    def hydrate(self, job):
        if self.known(job):
            return job
        job_id = job['_crawler_id']
        data = self.request('https://ats.openout.mihoyo.com/ats-portal/v1/job/info', {
            'id': job_id, 'hireType': 0 if self.portal == 'society' else 1, 'channelDetailIds': [1],
        })
        if data.get('code') != 0:
            raise SourceError('米哈游详情查询失败')
        detail = data.get('data')
        if not isinstance(detail, dict) or str(detail.get('id')) != job_id:
            raise SourceError('岗位详情ID不一致')
        return {**job, '_crawler_detail': detail}

    def parse(self, job):
        return MihoyoParser().parse(job, self.portal)
