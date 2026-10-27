"""小红书列表会跨页重叠。先按职位 ID 做成完整快照，覆盖总量后才入库。"""
import os
import time

from tqdm.auto import tqdm

from crawler import paths
from crawler.core import state as state_store
from crawler.sources.base import PortalSource, SourceError
from crawler.sources.xiaohongshu.parser import XiaohongshuParser


class XiaohongshuClient(PortalSource):
    source = 'xiaohongshu'
    portals = ('society', 'campus', 'internship')
    entries = {
        'society': 'https://job.xiaohongshu.com/social/position',
        'campus': 'https://job.xiaohongshu.com/campus/position',
        'internship': 'https://job.xiaohongshu.com/campus/intern',
    }

    def __init__(self, portal, page_size=50, queue=None, skip_existing=True):
        super().__init__(portal, page_size, queue, skip_existing)
        self.xhs_snapshot = None
        self.xhs_projects = None

    def prepare(self):
        if self.portal == 'society':
            return
        data = self.request('https://job.xiaohongshu.com/websiterecruit/common/findEnumList', ['PositionProjectEnum'])
        if data.get('statusCode') != 200:
            raise SourceError('小红书项目字典读取失败')
        category = 'regular' if self.portal == 'campus' else 'intern'
        self.xhs_projects = [item['code'] for item in data.get('data', {}).get('PositionProjectEnum', [])
                             if item.get('extMap', {}).get('category') == category]
        if not self.xhs_projects:
            raise SourceError('小红书未发现指定类别项目，禁止扩大范围')

    def xhs_page(self, page):
        query = {'pageNum': page, 'pageSize': self.page_size,
                 'recruitType': 'social' if self.portal == 'society' else 'campus',
                 'positionName': '', 'jobTypes': [], 'workplaces': []}
        if self.portal != 'society':
            query['jobProjects'] = self.xhs_projects
        result = self.request('https://job.xiaohongshu.com/websiterecruit/position/pageQueryPosition', query)
        if result.get('statusCode') != 200 or not isinstance(result.get('data'), dict):
            raise SourceError('小红书岗位查询失败')
        data = result['data']
        total = data.get('total')
        jobs = data.get('list')
        if total is None or not str(total).isdigit() or not isinstance(jobs, list) or len(jobs) > self.page_size:
            raise SourceError('小红书分页结构异常')
        return jobs, int(total)

    def xhs_consistent_snapshot(self, first_page):
        key = 'xhs_snapshot:' + self.portal + ':' + str(self.page_size)
        if first_page > 1:
            cached = self.queue.cache_get(key, '2', max_age=10**10)
            if cached is None:
                state_store.clear_progress(self.namespace)
                raise SourceError('小红书断点对应的快照缺失，已重置；重跑会从第一页安全扫描')
            return cached
        merged = {}
        expected = None
        received = 0
        for attempt in range(1, 4):
            page = 1
            with tqdm(desc=f'小红书/{self.portal}列表快照第{attempt}轮', unit='条', dynamic_ncols=True) as progress:
                while expected is None or (page - 1) * self.page_size < expected:
                    jobs, total = self.xhs_page(page)
                    if expected is not None and expected != total:
                        raise SourceError('小红书快照期间总量变更，请重跑，未将快照标记为完整')
                    expected = total
                    progress.total = total
                    if not jobs and (page - 1) * self.page_size < total:
                        raise SourceError('小红书快照提前返回空页')
                    for job in jobs:
                        job_id = str(job.get('positionId') or '')
                        if not job_id:
                            raise SourceError('小红书岗位缺少ID')
                        merged[job_id] = job
                    received += len(jobs)
                    progress.update(len(jobs))
                    page += 1
                    if (page - 1) * self.page_size < expected:
                        time.sleep(.3)
            if len(merged) == expected:
                snapshot = {'jobs': [merged[job_id] for job_id in sorted(merged)], 'total': expected,
                            'passes': attempt, 'api_rows_scanned': received, 'unique_positions': len(merged)}
                self.queue.cache_put(key, '2', snapshot)
                return snapshot
            if len(merged) > expected:
                raise SourceError('小红书快照职位变更导致并集超出总量，请重跑')
        raise SourceError(f'小红书三轮快照仍未覆盖唯一岗位总数：{len(merged)}/{expected}')

    def load_page(self, page):
        if self.xhs_snapshot is None:
            self.xhs_snapshot = self.xhs_consistent_snapshot(page)
        data = self.xhs_snapshot
        start = (page - 1) * self.page_size
        return data['jobs'][start:start + self.page_size], data['total'], 'positionId'

    def execute(self, **kwargs):
        result = super().execute(**kwargs)
        if self.xhs_snapshot is not None:
            result.update({key: self.xhs_snapshot[key] for key in ('passes', 'api_rows_scanned', 'unique_positions')})
            state_store.atomic_json(os.path.join(paths.OUTPUT_DIR, self.namespace + '_last_run_summary.json'), result)
        return result

    def parse(self, job):
        return XiaohongshuParser().parse(job, self.portal)
