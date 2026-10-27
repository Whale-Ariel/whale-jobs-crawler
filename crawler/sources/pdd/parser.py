"""拼多多校招。任职要求来自详情接口。"""
from crawler.core.text import date, place_names, text
from crawler.sources.base import JobParser


class PddParser(JobParser):
    source = 'pdd'
    missing_message = '岗位缺少ID、标题或链接'

    def parse(self, job, portal):
        original = job.get('_crawler_raw', job)
        detail = job.get('_crawler_detail')
        post = {**original, **detail} if detail else original
        job_id = str(job.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, {'list': original, 'detail': detail} if detail else original)
        row.update(title=post.get('name'), description=text(post.get('jobDuty')),
                   requirement=text(post.get('serveRequirement') or post.get('jobRequirement')),
                   job_code=post.get('code'), job_category_name=post.get('jobName'),
                   publish_time=date(post.get('releaseTime')),
                   job_url='https://careers.pddglobalhr.com/campus/grad/detail?positionId=' + job_id)
        self.places(row, place_names(post.get('workLocationName')), [])
        return self.require(row, job_id)
