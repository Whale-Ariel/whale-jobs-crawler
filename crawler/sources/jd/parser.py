"""京东社招与指定校招项目 45。项目号不对就拒绝入库。"""
from crawler.core.text import names, timestamp
from crawler.sources.base import JobParser, SourceError, public_raw


class JdParser(JobParser):
    source = 'jd'
    batch_ids = {'campus': '45'}

    def parse(self, post, portal):
        job_id = str(post.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, public_raw(post, drop_synthetic_id=True), self.batch_ids.get(portal, ''))
        row.update(title=post.get('name'), description=post.get('description'), requirement=post.get('requirement'))
        if portal == 'society':
            cities = [post.get('workCity')]
            units = [post.get('positionDeptName')]
            row.update(title=post.get('positionName'), description=post.get('workContent'),
                       requirement=post.get('qualification'), job_category_name=post.get('jobType'),
                       publish_time=post.get('formatPublishTime') or timestamp(post.get('publishTime')),
                       job_url='https://zhaopin.jd.com/web/job_info_list/3?isHunterFlag=false',
                       job_code=post.get('reqNumber'), job_hot_flag=bool(post.get('isHot')))
        else:
            if str(post.get('planId')) != row['batch_id']:
                raise SourceError('京东接口未遵守项目45筛选')
            reqs = post.get('requirementVoList') or []
            cities = names([item.get('workCity') for item in reqs]) or names(post.get('workCity'))
            units = names([item.get('positionBg') for item in reqs])
            row.update(title=post.get('positionName'), description=post.get('workContent'),
                       requirement=post.get('qualification'), job_category_name=post.get('jobDirection'),
                       required_degree=post.get('education'), publish_time=timestamp(post.get('publishTime')),
                       batch_name=post.get('planName'),
                       job_url=f'https://campus.jd.com/#/details?id={job_id}&type=present')
        self.places(row, cities, units)
        return self.require(row, job_id)
