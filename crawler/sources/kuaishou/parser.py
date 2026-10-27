"""快手社招、日常实习与指定校招子项目。"""
from crawler.core.text import names, timestamp
from crawler.sources.base import JobParser, SourceError, public_raw


class KuaishouParser(JobParser):
    source = 'kuaishou'
    batch_ids = {'campus': '20271779425607'}

    def parse(self, post, portal):
        job_id = str(post.get('_crawler_id') or post.get('id') or '')
        row = self.blank(portal, public_raw(post), self.batch_ids.get(portal, ''))
        row.update(title=post.get('name'), description=post.get('description'), requirement=post.get('requirement'))
        if portal == 'campus':
            if str(post.get('recruitSubProjectCode')) != row['batch_id']:
                raise SourceError('快手接口未遵守校招项目筛选')
            cities = names(post.get('workLocationDicts'))
            row['job_url'] = ('https://campus.kuaishou.cn/recruit/campus/e/#/campus/job-info/'
                              f'{job_id}?recruitSubProjectCodes={row["batch_id"]}')
        else:
            expected = 'C001' if portal == 'society' else 'C002'
            if post.get('positionNatureCode') != expected:
                raise SourceError('快手接口返回的招聘类型与请求不一致')
            cities = names(post.get('workLocations')) or post.get('_crawler_city_names') or []
            channel = 'social' if portal == 'society' else 'trainee'
            row['job_url'] = f'https://zhaopin.kuaishou.cn/#/official/{channel}/job-info/{job_id}'
        row.update(requirement=post.get('positionDemand'), job_category_id=post.get('positionCategoryCode'),
                   city_code=post.get('workLocationCode'), department_id=post.get('departmentCode'),
                   publish_time=timestamp(post.get('releaseTime')),
                   head_count=post.get('recruitNumber'), job_code=post.get('code'))
        self.places(row, cities, names(post.get('departmentName')))
        return self.require(row, job_id)
