"""网易公开职位列表。"""
from crawler.sources.base import LenientSource, SourceError
from crawler.sources.netease.parser import NeteaseParser


class NeteaseClient(LenientSource):
    source = 'netease'
    portals = ('society', 'internship', 'dispatch')
    entries = {'society': 'https://hr.163.com/job-list.html'}
    work_types = {'society': '0', 'internship': '1', 'dispatch': '2'}

    def load_page(self, page):
        result = self.request('https://hr.163.com/api/hr163/position/queryPage', {
            'currentPage': page, 'pageSize': self.page_size, 'sortType': 2,
            'workType': self.work_types[self.portal],
        })
        if result.get('code') != 200:
            raise SourceError('网易返回错误：' + str(result.get('msg')))
        data = result.get('data')
        if not isinstance(data, dict):
            raise SourceError('接口数据结构缺失')
        return data.get('list'), data.get('total'), 'id'

    def parse(self, job):
        return NeteaseParser().parse(job, self.portal)
