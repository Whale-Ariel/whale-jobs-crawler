"""OPPO 社招与应届生。应届范围不能混入实习或博士。"""
from crawler.core.text import date, place_names, text
from crawler.sources.base import JobParser, SourceError


class OppoParser(JobParser):
    source = 'oppo'
    missing_message = '岗位缺少ID、标题或链接'
    batch_ids = {'campus': 'Graduate'}

    def parse(self, job, portal):
        original = job.get('_crawler_raw', job)
        detail = job.get('_crawler_detail')
        post = {**original, **detail} if detail else original
        job_id = str(job.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, {'list': original, 'detail': detail} if detail else original,
                         self.batch_ids.get(portal, ''))
        if portal == 'society':
            if post.get('recruitType') != 'SOCIAL-RECRUITMENT':
                raise SourceError('OPPO社招范围混入实习')
            row.update(title=post.get('publishName') or post.get('jobName'), description=text(post.get('jobDuty')),
                       requirement=text(post.get('workRequire')), job_code=post.get('jobCode'),
                       required_degree=post.get('educationRequire'), publish_time=date(post.get('publishDate')),
                       job_url='https://career.oppo.com/official/oppo/recruitment/post/'
                               + job_id + '?recruitType=SOCIAL-RECRUITMENT')
        else:
            if post.get('recruitmentType') != 'Graduate':
                raise SourceError('OPPO应届生范围混入其他类型')
            row.update(title=post.get('positionName'), description=text(post.get('positionDesc')),
                       requirement=text(post.get('positionRequire')), batch_name=post.get('projectName'),
                       publish_time=date(post.get('releaseTime')),
                       job_url='https://careers.oppo.com/university/oppo/campus/post/'
                               + job_id + '?recruitType=Graduate')
        self.places(row, place_names(post.get('workCityName')), [])
        return self.require(row, job_id)
