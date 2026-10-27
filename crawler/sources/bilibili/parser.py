"""哔哩哔哩社招、校招与实习。实习按岗位类型名校验，不把留用实习收成应届。"""
from crawler.core.text import date, place_names, split_duty
from crawler.sources.base import JobParser, SourceError


class BilibiliParser(JobParser):
    source = 'bilibili'
    missing_message = '岗位缺少ID、标题或链接'

    def parse(self, job, portal):
        original = job.get('_crawler_raw', job)
        detail = job.get('_crawler_detail')
        post = {**original, **detail} if detail else original
        job_id = str(job.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, {'list': original, 'detail': detail} if detail else original)
        expected = {'society': 0, 'campus': 1, 'internship': 0}[portal]
        if portal == 'internship':
            if '实习' not in (post.get('positionTypeName') or ''):
                raise SourceError('B站实习列表混入非实习岗位')
        elif post.get('recruitType') != expected:
            raise SourceError('B站招聘类型不一致')
        suffix = '' if portal == 'society' else '?type=' + ('3' if portal == 'campus' else '0')
        channel = 'social' if portal == 'society' else 'campus'
        row.update(title=post.get('positionName'), job_category_name=post.get('postCodeName'),
                   job_hot_flag=bool(post.get('hotRecruit')), publish_time=date(post.get('pushTime')),
                   job_url=f'https://jobs.bilibili.com/{channel}/positions/{job_id}{suffix}')
        row['description'], row['requirement'] = split_duty(post.get('positionDescription'))
        self.places(row, place_names(post.get('workLocation') or post.get('workCity')), [])
        return self.require(row, job_id)
