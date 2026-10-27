"""美团社招与校招。校招入口里的实习保留官方子类型标签。"""
from crawler.core.text import names, timestamp
from crawler.sources.base import JobParser, SourceError, public_raw


class MeituanParser(JobParser):
    source = 'meituan'

    def parse(self, post, portal):
        job_id = str(post.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, public_raw(post, drop_synthetic_id=True))
        row.update(title=post.get('name'), description=post.get('description'), requirement=post.get('requirement'))
        expected = {'society': {'3'}, 'campus': {'1', '2'}}[portal]
        if str(post.get('jobType')) not in expected:
            raise SourceError('美团接口返回的招聘类型与请求不一致')
        row.update(description=post.get('jobDuty'), requirement=post.get('jobRequirement'),
                   job_category_name=post.get('jobFamily'), job_function=post.get('jobFamilyGroup'),
                   job_url=f'https://hr.meituan.com/web/position/detail?jobUnionId={job_id}&jobShareType=1',
                   publish_time=timestamp(post.get('firstPostTime')), expiry_time=timestamp(post.get('expiredTime')))
        if str(post.get('jobType')) == '2':
            row['program_tags'] = ['internship']
        self.places(row, names(post.get('cityList')), names(post.get('department')))
        return self.require(row, job_id)
