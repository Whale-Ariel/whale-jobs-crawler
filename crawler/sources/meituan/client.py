"""美团官方职位列表。"""
from crawler.sources.base import LenientSource, SourceError
from crawler.sources.meituan.parser import MeituanParser


class MeituanClient(LenientSource):
    source = 'meituan'
    portals = ('society', 'campus')
    entries = {
        'society': 'https://hr.meituan.com/web/social',
        'campus': 'https://hr.meituan.com/web/campus',
    }

    def load_page(self, page):
        codes = ['3'] if self.portal == 'society' else ['1', '2']
        result = self.request('https://hr.meituan.com/api/official/job/getJobList', {
            'page': {'pageNo': page, 'pageSize': self.page_size}, 'jobShareType': '1',
            'jobType': [{'code': code, 'subCode': []} for code in codes], 'cityList': [],
            'department': [], 'jfJgList': [], 'typeCode': [], 'keywords': '',
        })
        if result.get('status') != 1:
            raise SourceError('美团返回错误：' + str(result.get('message')))
        data = result.get('data')
        if not isinstance(data, dict) or not isinstance(data.get('page'), dict):
            raise SourceError('美团分页结构缺失')
        return data.get('list'), data['page'].get('totalCount'), 'jobUnionId'

    def parse(self, job):
        return MeituanParser().parse(job, self.portal)
