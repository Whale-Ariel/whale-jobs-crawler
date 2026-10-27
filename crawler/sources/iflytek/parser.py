"""科大讯飞社招与校招。"""
from crawler.core.text import date, place_names, text
from crawler.sources.base import JobParser, SourceError


class IflytekParser(JobParser):
    source = 'iflytek'
    missing_message = '岗位缺少ID、标题或链接'

    def parse(self, job, portal):
        original = job.get('_crawler_raw', job)
        detail = job.get('_crawler_detail')
        post = {**original, **detail} if detail else original
        job_id = str(job.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, {'list': original, 'detail': detail} if detail else original)
        if str(post.get('CategoryId')) != ('1' if portal == 'society' else '2'):
            raise SourceError('科大讯飞招聘范围不一致')
        channel = 'social' if portal == 'society' else 'campus'
        row.update(title=post.get('JobAdName'), description=text(post.get('Duty')),
                   requirement=text(post.get('Require')), publish_time=date(post.get('PostDate')),
                   expiry_time=date(post.get('EndTime')), address=text(post.get('DetailAddress')),
                   job_url=f'https://iflytek.zhiye.com/{channel}/detail?jobAdId=' + job_id)
        self.places(row, place_names(post.get('LocNames')), place_names(post.get('Org')))
        return self.require(row, job_id)
