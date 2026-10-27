"""科大讯飞北森门户。字段列表从当前页面配置读取，避免城市和日期丢失。"""
import json

from crawler.sources.base import PortalSource, SourceError
from crawler.sources.iflytek.parser import IflytekParser


class IflytekClient(PortalSource):
    source = 'iflytek'
    portals = ('society', 'campus')
    entries = {
        'society': 'https://iflytek.zhiye.com/social/jobs',
        'campus': 'https://iflytek.zhiye.com/campus/jobs',
    }

    def landing(self):
        response = self.session.get(self.entry_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        response.raise_for_status()
        if 'login' in response.url.lower():
            raise SourceError('官网跳转登录页')
        return response.text

    def prepare(self):
        body = self.landing()
        try:
            data = json.JSONDecoder().raw_decode(body.split('BSGlobal = ', 1)[1])[0]
        except (ValueError, IndexError) as error:
            raise SourceError('北森门户配置缺失') from error
        self.portal_id = data['PortalId']
        category = '1' if self.portal == 'society' else '2'
        config_page = next((item for item in data['Pages']
                            if str(item.get('BusinessType')) == category and item.get('PageType') == 2), None)
        if not config_page:
            raise SourceError('北森招聘页面配置缺失')
        config = self.request(config_page['ConfigAddress'])
        self.display_fields = []

        def collect(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == 'ListItems':
                        self.display_fields.extend(item['Key'] for item in child if item.get('Select'))
                    else:
                        collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        collect(config)
        if not self.display_fields:
            raise SourceError('北森字段配置缺失')

    def load_page(self, page):
        result = self.request('https://iflytek.zhiye.com/api/Jobad/GetJobAdPageList', {
            'PageIndex': page - 1, 'PageSize': self.page_size,
            'Category': [1 if self.portal == 'society' else 2],
            'PortalId': self.portal_id, 'KeyWords': '', 'SpecialType': 0,
            'DisplayFields': self.display_fields,
        })
        if result.get('Code') != 200:
            raise SourceError('科大讯飞查询失败：' + str(result.get('Message')))
        return result.get('Data'), result.get('Count'), 'Id'

    def parse(self, job):
        return IflytekParser().parse(job, self.portal)
