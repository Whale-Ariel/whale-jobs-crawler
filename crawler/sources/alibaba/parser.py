"""阿里职位与组织关系映射。社招和校招共用这一套字段。"""
import urllib.parse

from crawler.core.schema import COLUMNS
from crawler.sources.bytedance.parser import _ms_to_ts
from crawler.taxonomy import ALIASES, classify

SOURCE = 'alibaba'

def parse_post(post, portal, batch=None, organizations=None, program_tags=None):
    # 同一列集合适配所有来源。
    row = dict.fromkeys(COLUMNS)
    row.update(classify(SOURCE, portal, post))
    locations = post.get('workLocations') or []
    url = post.get('positionUrl')
    if url:
        url = urllib.parse.urljoin('https://talent.taotian.com' if portal == 'society'
                                   else 'https://campus-talent.alibaba.com', url).split('&track_id=')[0]
    row.update(job_id=str(post.get('id') or ''), source=SOURCE,
               type='society' if portal == 'society' else 'campus',
               title=post.get('name'), job_code=post.get('code'),
               description=post.get('description'), requirement=post.get('requirement'),
               city_list=locations, city_name='、'.join(locations) or None,
               job_category_name=post.get('categoryName'), required_degree=post.get('degree'),
               department_id=None,
               job_url=url, publish_time=_ms_to_ts(post.get('publishTime') or post.get('modifyTime')),
               recruit_type_name=post.get('batchName'), raw_data=post)
    if batch:
        row.update(batch_id=batch.id, batch_name=batch.name)
    row['organization_assignments'] = organizations or []
    row['program_tags'] = list(program_tags or (['ali_star'] if portal == 'ali_star' else []))
    if portal != 'society' and not url and row['job_id']:
        row['job_url'] = f'https://campus-talent.alibaba.com/campus/position/{row["job_id"]}'
    from crawler.core.model import normalize_row
    return normalize_row(row)



def organization_assignments(groups):
    result = []
    for group in groups:
        if not group.get('circleCode') or not group.get('name'):
            raise RuntimeError('职位组织关系缺少事业群编码或名称')
        departments = []
        for dept in group.get('deptList') or []:
            if not dept.get('deptCode') or not dept.get('name'):
                raise RuntimeError('职位组织关系缺少部门编码或名称')
            departments.append(dict(department_code=str(dept['deptCode']),department_name=dept['name'],
                work_cities=sorted(dept.get('workCityList') or [],key=lambda city:str(city.get('code','')))))
        result.append(dict(circle_code=str(group['circleCode']),business_unit=ALIASES.get(group['name'],group['name']),
                           departments=sorted(departments,key=lambda d:d['department_code'])))
    return sorted(result,key=lambda g:g['circle_code'])


