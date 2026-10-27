"""百度职位列表。服务端拒绝 50 条分页，固定按 10 条推进。"""
from crawler.sources.base import LenientSource, SourceError
from crawler.sources.baidu.parser import BaiduParser


class BaiduClient(LenientSource):
    source = 'baidu'
    portals = ('society', 'campus')
    entries = {
        'society': 'https://talent.baidu.com/jobs/social-list?search=',
        'campus': 'https://talent.baidu.com/jobs/list?search=&recruitType=GRADUATE',
    }

    def cap_page_size(self, page_size):
        return min(page_size, 10)

    def load_page(self, page):
        result = self.request('https://talent.baidu.com/httservice/getPostListNew', {
            'recruitType': 'SOCIAL' if self.portal == 'society' else 'GRADUATE',
            'pageSize': self.page_size, 'curPage': page, 'keyWord': '', 'projectType': '',
        }, form=True)
        if result.get('status') != 'ok':
            raise SourceError('百度返回错误：' + str(result.get('message')))
        data = result.get('data')
        if not isinstance(data, dict):
            raise SourceError('接口数据结构缺失')
        return data.get('list'), data.get('total'), 'postId'

    def parse(self, job):
        return BaiduParser().parse(job, self.portal)
