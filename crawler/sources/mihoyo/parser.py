"""米哈游社招，以及两个固定项目的校招和实习。列表没有职责，必须带详情。"""
from crawler.core.text import place_names, text
from crawler.sources.base import JobParser, SourceError


class MihoyoParser(JobParser):
    source = 'mihoyo'
    missing_message = '岗位缺少ID、标题或链接'
    batch_ids = {'campus': '13', 'internship': '4'}

    def parse(self, job, portal):
        original = job.get('_crawler_raw', job)
        detail = job.get('_crawler_detail')
        if detail is None:
            raise SourceError('米哈游列表不含职责，必须取得详情后入库')
        post = {**original, **detail}
        job_id = str(job.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, {'list': original, 'detail': detail}, self.batch_ids.get(portal, ''))
        if int(post.get('hireType')) != (0 if portal == 'society' else 1):
            raise SourceError('米哈游招聘类型不一致')
        if portal != 'society' and str(post.get('projectId')) != row['batch_id']:
            raise SourceError('米哈游项目不一致')
        prefix = '' if portal == 'society' else 'campus/'
        row.update(title=post.get('title'), description=text(post.get('description')),
                   requirement=text(post.get('jobRequire')), job_category_name=post.get('competencyType'),
                   batch_name=post.get('projectName'),
                   job_url=f'https://jobs.mihoyo.com/#/{prefix}position/{job_id}')
        self.places(row, place_names(post.get('addressDetailList')), [])
        return self.require(row, job_id)
