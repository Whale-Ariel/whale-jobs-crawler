"""京东校招走公开分页；社招列表需要官网追踪 cookie，失效时明确失败。"""
from crawler.sources.base import LenientSource, SourceError
from crawler.sources.jd.parser import JdParser

# 京东社招列表接口随浏览器会话带公共追踪 cookie，不是登录态。
# 缺键或失效时返回登录页，fetch 会拦截，不会当成空列表。
JD_SOCIETY_COOKIES = {
    'thor': 'A1559B6333777E51E8BB105F50CBBBE0392334B898A70E7DBBD0707B7840832BE00787D12427449B469BA04F243ADCC79959A26F80FDB8B7FFC9E86F5CF9B2AF92D71FD6926A18BFDBECDE3D98F0E0211067EDE879663B4989958CD03CC9C07279D19B78A7DFC4781DA29CF64DF7AC1BDA946B0419653A267E61B8D65207347',
    'flash': '3_POpKRHsDJhHROo78Npa4542L4OuqfgSPU1S8n1MUlIg9h4EyDlUR9mhVqDWCE9XukicmL3U0X-wB-T-XifE68opElUZDX0Rzte0kn6vWIUSTeVRbdFjFGf8uOqDrtzqzg3tPAsAKw6yEQ4aDs7M7MwvIoDOYl-elXbIE3HiuqzASh2A94Gjb',
    'bnc-uuid': '03b238c0-6c51-4541-a8eb-d45cb880899b',
    '__jdv': '176729966|direct|-|none|-|1792761637686',
    '__jdu': '17927616376861867347975',
    '__jdc': '176729966',
    '__jda': '176729966.17927616376861867347975.1792761638.1792804283.1793003098.3',
    '__jdb': '176729966.3.17927616376861867347975|3.1793003098',
    'JSESSIONID': '23C77A99F752FC295C9F84C8492716E9.s1',
}


class JdClient(LenientSource):
    source = 'jd'
    portals = ('society', 'campus')
    batch_ids = {'campus': '45'}
    entries = {
        'society': 'https://zhaopin.jd.com/web/job_info_list/3?isHunterFlag=false',
        'campus': 'https://campus.jd.com/#/jobs?selProjects=45',
    }

    def fetch(self, page):
        if self.portal == 'society':
            return self.society_page(page)
        return super().fetch(page)

    def society_page(self, page):
        response = self.session.post(
            'https://zhaopin.jd.com/web/job/job_list',
            data={'pageIndex': page, 'pageSize': self.page_size, 'workCityJson': '[]',
                  'jobTypeJson': '[]', 'jobSearch': '', 'depTypeJson': '[]'},
            cookies=JD_SOCIETY_COOKIES,
            headers={'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                     'origin': 'https://zhaopin.jd.com',
                     'referer': 'https://zhaopin.jd.com/web/job_info_list/3?isHunterFlag=false',
                     'x-requested-with': 'XMLHttpRequest',
                     'user-agent': 'Mozilla/5.0'},
            timeout=30)
        if response.status_code in (401, 403):
            raise SourceError(f'京东社招拒绝访问 HTTP {response.status_code}（cookie 可能失效）')
        response.raise_for_status()
        try:
            jobs = response.json()
        except ValueError:
            raise SourceError('京东社招未返回JSON，cookie失效或跳登录页')
        if not isinstance(jobs, list):
            raise SourceError('京东社招响应不是职位list，cookie可能失效')
        return [{**job, 'id': job.get('id'), '_crawler_id': str(job.get('id') or '')} for job in jobs], None

    def load_page(self, page):
        result = self.request('https://campus.jd.com/api/wx/position/page?type=present', {
            'pageSize': self.page_size, 'pageIndex': page - 1,
            'parameter': {'positionName': '', 'planIdList': [45], 'jobDirectionCodeList': [],
                          'workCityCodeList': [], 'positionDeptList': []},
        })
        if result.get('success') is not True:
            raise SourceError('京东返回错误：' + str(result.get('message')))
        data = result.get('body')
        if not isinstance(data, dict):
            raise SourceError('接口数据结构缺失')
        return data.get('items'), data.get('totalNumber'), 'publishId'

    def parse(self, job):
        return JdParser().parse(job, self.portal)
