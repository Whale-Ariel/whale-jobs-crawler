"""滴滴社招，以及两个 Moka 门户里的校招和实习。"""
from crawler.core.text import date, place_names, split_duty, text
from crawler.sources.base import JobParser, SourceError
from crawler.sources.didi.client import ENTRIES


class DidiParser(JobParser):
    source = 'didi'
    missing_message = '岗位缺少ID、标题或链接'
    batch_ids = {'campus': '96064', 'internship': '6222'}

    def parse(self, job, portal):
        original = job.get('_crawler_raw', job)
        detail = job.get('_crawler_detail')
        post = {**original, **detail} if detail else original
        job_id = str(job.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, {'list': original, 'detail': detail} if detail else original,
                         self.batch_ids.get(portal, ''))
        if portal == 'society':
            row.update(title=post.get('jobName'), description=text(post.get('jobDuty')),
                       requirement=text(post.get('jobQualification')), job_code=post.get('jdNo'),
                       job_category_name=post.get('jobTypeName'), publish_time=date(post.get('createTime')),
                       job_url='https://talent.didiglobal.com/social/jobDetail?jdId=' + job_id)
            cities = place_names(post.get('workArea'))
            units = place_names(post.get('deptName'))
        else:
            if post.get('orgId') != 'didiglobal':
                raise SourceError('Moka公司身份不一致')
            if portal == 'internship' and post.get('commitment') != '实习':
                raise SourceError('滴滴实习范围混入其他用工类型')
            row.update(title=post.get('title'), publish_time=date(post.get('publishedAt') or post.get('openedAt')),
                       required_degree=post.get('education'),
                       batch_name=(post.get('projectFolder') or {}).get('name'),
                       job_url=ENTRIES[portal] + '#/job/' + job_id)
            row['description'], row['requirement'] = split_duty(post.get('jobDescription'))
            cities = place_names(post.get('locations'))
            units = place_names(post.get('department'))
        self.places(row, cities, units)
        return self.require(row, job_id)
