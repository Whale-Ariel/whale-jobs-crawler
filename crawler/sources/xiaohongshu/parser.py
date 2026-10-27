"""小红书社招、常规校招与日常实习。"""
from crawler.core.text import date, place_names, text
from crawler.sources.base import JobParser


class XiaohongshuParser(JobParser):
    source = 'xiaohongshu'
    missing_message = '岗位缺少ID、标题或链接'

    def parse(self, job, portal):
        original = job.get('_crawler_raw', job)
        detail = job.get('_crawler_detail')
        post = {**original, **detail} if detail else original
        job_id = str(job.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, {'list': original, 'detail': detail} if detail else original)
        if portal == 'internship':
            url = 'https://job.xiaohongshu.com/campus/intern/position/' + job_id
        else:
            channel = 'social' if portal == 'society' else 'campus'
            url = f'https://job.xiaohongshu.com/{channel}/position/' + job_id
        row.update(title=post.get('positionName'), description=text(post.get('duty')),
                   requirement=text(post.get('qualification')), job_category_name=post.get('jobType'),
                   publish_time=date(post.get('publishTime')), job_url=url)
        self.places(row, place_names(post.get('workplace')), [])
        return self.require(row, job_id)
