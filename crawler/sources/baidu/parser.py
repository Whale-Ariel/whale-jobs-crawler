"""百度社招与校招。"""
from crawler.core.text import names, timestamp
from crawler.sources.base import JobParser, public_raw


class BaiduParser(JobParser):
    source = 'baidu'

    def parse(self, post, portal):
        job_id = str(post.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, public_raw(post, drop_synthetic_id=True))
        recruit = 'SOCIAL' if portal == 'society' else 'GRADUATE'
        row.update(title=post.get('name'),
                   description=(post.get('workContent') or '').replace('\\n', '\n'),
                   requirement=(post.get('serviceCondition') or '').replace('\\n', '\n'),
                   required_degree=post.get('education'), job_category_name=post.get('postType'),
                   publish_time=timestamp(post.get('publishDate')),
                   job_url=f'https://talent.baidu.com/jobs/detail/{recruit}/{job_id}',
                   job_code=post.get('jobId'))
        self.places(row, names(post.get('workPlace')), names(post.get('orgName')))
        return self.require(row, job_id)
