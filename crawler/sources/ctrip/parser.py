"""携程社招与校招。链接和去重都用稳定的 fromId。"""
from crawler.core.text import date, place_names, split_duty, text
from crawler.sources.base import JobParser, SourceError


class CtripParser(JobParser):
    source = 'ctrip'
    missing_message = '岗位缺少ID、标题或链接'

    def parse(self, job, portal):
        original = job.get('_crawler_raw', job)
        detail = job.get('_crawler_detail')
        post = {**original, **detail} if detail else original
        job_id = str(job.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, {'list': original, 'detail': detail} if detail else original)
        if int(post.get('category')) != (1 if portal == 'society' else 2):
            raise SourceError('携程招聘范围不一致')
        channel = 'experienced' if portal == 'society' else 'campus'
        row.update(title=post.get('jobTitle'), description=text(post.get('duty')),
                   requirement=text(post.get('requirements')), job_code=post.get('fromId'),
                   job_category_name=post.get('jobFamilyGroupName'), publish_time=date(post.get('publishDate')),
                   job_url='https://job.ctrip.com/#/' + channel + '/job-detail/' + str(post['fromId']))
        if not row['description']:
            row['description'], row['requirement'] = split_duty(post.get('requirements'))
        self.places(row, place_names(post.get('cityName')), place_names(post.get('buName')))
        return self.require(row, job_id)
