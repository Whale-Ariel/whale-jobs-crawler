"""网易岗位字段。用工类型必须和请求的社招、实习、派遣一致。"""
from crawler.core.text import names, timestamp
from crawler.sources.base import JobParser, SourceError, public_raw


class NeteaseParser(JobParser):
    source = 'netease'

    def parse(self, post, portal):
        job_id = str(post.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, public_raw(post))
        row.update(title=post.get('name'), description=post.get('description'), requirement=post.get('requirement'))
        expected = {'society': '0', 'internship': '1', 'dispatch': '2'}[portal]
        if str(post.get('workType')) != expected:
            raise SourceError('网易接口返回的用工类型与请求不一致')
        row.update(job_url=f'https://hr.163.com/job-detail.html?id={job_id}&lang=zh',
                   job_category_name=post.get('firstPostTypeName'), required_degree=post.get('reqEducationName'),
                   head_count=post.get('recruitNum'), publish_time=timestamp(post.get('updateTime')),
                   sub_title=post.get('productName'))
        self.places(row, names(post.get('workPlaceNameList')), names(post.get('firstDepName')))
        return self.require(row, job_id)
