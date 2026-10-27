"""OPPO 社招与应届生。应届项目从官网动态发现，同时带上外籍应届筛选。"""
from crawler.sources.base import PortalSource, SourceError
from crawler.sources.oppo.parser import OppoParser


class OppoClient(PortalSource):
    source = 'oppo'
    portals = ('society', 'campus')
    entries = {
        'society': 'https://career.oppo.com/official/oppo/recruitment/post?recruitType=SOCIAL-RECRUITMENT',
        'campus': 'https://careers.oppo.com/university/oppo/campus/post?recruitType=Graduate',
    }
    batch_ids = {'campus': 'Graduate'}

    def prepare(self):
        if self.portal != 'campus':
            return
        data = self.request('https://careers.oppo.com/openapi/position/project/list', headers={'Tenant-Id': '1000'})
        if data.get('code') != 0 or not isinstance(data.get('data'), list):
            raise SourceError('OPPO项目发现失败')
        self.oppo_projects = [{'projectId': item['idRecruitProject'], 'recruitmentType': 'Graduate',
                               'isAllNode': 'Y', 'themeList': []}
                              for item in data['data'] if item.get('recruitmentType') == 'Graduate']
        if not self.oppo_projects:
            raise SourceError('OPPO未发现应届生项目，不能扩大查询范围')

    def load_page(self, page):
        if self.portal == 'society':
            result = self.request('https://career.oppo.com/ats-candidate-api/open-api/position/queryPositionList', {
                'pageNum': page, 'pageSize': self.page_size, 'positionName': '', 'projectList': [],
                'positionTypeList': [], 'workCityCodeList': [], 'recruitType': 'SOCIAL-RECRUITMENT',
            }, headers={'Tenant-Id': '1000'})
            list_key, id_key = 'list', 'positionId'
        else:
            result = self.request('https://careers.oppo.com/openapi/position/pageNew', {
                'pageNum': page, 'pageSize': self.page_size, 'positionName': '', 'projectList': self.oppo_projects,
                'foreignRecruitmentTypeList': ['Graduate'], 'positionTypeList': [], 'workCityCodeList': [],
            }, headers={'Tenant-Id': '1000'})
            list_key, id_key = 'records', 'idProjPosition'
        if str(result.get('code')) != '0':
            raise SourceError('OPPO列表查询失败：' + str(result.get('msg')))
        data = result.get('data')
        jobs = data.get(list_key) if isinstance(data, dict) else None
        total = data.get('total') if isinstance(data, dict) else None
        return jobs, total, id_key

    def parse(self, job):
        return OppoParser().parse(job, self.portal)
