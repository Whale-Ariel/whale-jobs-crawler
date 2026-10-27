"""公司注册表。新增一家公司时登记客户端和解析器，调度不再改分支。"""
from crawler.sources.baidu.client import BaiduClient
from crawler.sources.baidu.parser import BaiduParser
from crawler.sources.bilibili.client import BilibiliClient
from crawler.sources.bilibili.parser import BilibiliParser
from crawler.sources.bytedance.client import BytedanceClient
from crawler.sources.ctrip.client import CtripClient
from crawler.sources.ctrip.parser import CtripParser
from crawler.sources.didi.client import DidiClient
from crawler.sources.didi.parser import DidiParser
from crawler.sources.iflytek.client import IflytekClient
from crawler.sources.iflytek.parser import IflytekParser
from crawler.sources.jd.client import JdClient
from crawler.sources.jd.parser import JdParser
from crawler.sources.kuaishou.client import KuaishouClient
from crawler.sources.kuaishou.parser import KuaishouParser
from crawler.sources.meituan.client import MeituanClient
from crawler.sources.meituan.parser import MeituanParser
from crawler.sources.netease.client import NeteaseClient
from crawler.sources.netease.parser import NeteaseParser
from crawler.sources.oppo.client import OppoClient
from crawler.sources.oppo.parser import OppoParser
from crawler.sources.pdd.client import PddClient
from crawler.sources.pdd.parser import PddParser
from crawler.sources.tencent.client import TencentClient
from crawler.sources.xiaohongshu.client import XiaohongshuClient
from crawler.sources.xiaohongshu.parser import XiaohongshuParser
from crawler.sources.mihoyo.client import MihoyoClient
from crawler.sources.mihoyo.parser import MihoyoParser
from crawler.sources.base import SourceError
from crawler.sources.kuaishou.client import kuaishou_headers

CLIENTS = {
    'bytedance': BytedanceClient,
    'tencent': TencentClient,
    'netease': NeteaseClient,
    'jd': JdClient,
    'meituan': MeituanClient,
    'baidu': BaiduClient,
    'kuaishou': KuaishouClient,
    'bilibili': BilibiliClient,
    'xiaohongshu': XiaohongshuClient,
    'didi': DidiClient,
    'pdd': PddClient,
    'ctrip': CtripClient,
    'iflytek': IflytekClient,
    'mihoyo': MihoyoClient,
    'oppo': OppoClient,
}
PARSERS = {
    'netease': NeteaseParser,
    'jd': JdParser,
    'meituan': MeituanParser,
    'baidu': BaiduParser,
    'kuaishou': KuaishouParser,
    'bilibili': BilibiliParser,
    'xiaohongshu': XiaohongshuParser,
    'didi': DidiParser,
    'pdd': PddParser,
    'ctrip': CtripParser,
    'iflytek': IflytekParser,
    'mihoyo': MihoyoParser,
    'oppo': OppoParser,
}
NEW = ('netease', 'jd', 'meituan', 'baidu', 'kuaishou')
EXTRA = ('bilibili', 'xiaohongshu', 'didi', 'pdd', 'ctrip', 'iflytek', 'mihoyo', 'oppo')
PORTALS = {name: CLIENTS[name].portals for name in (*NEW, *EXTRA)}
NEW_PORTALS = {name: CLIENTS[name].portals for name in NEW}
EXTRA_PORTALS = {name: CLIENTS[name].portals for name in EXTRA}


class _PortalGroup:
    def __init__(self, mapping):
        self.PORTALS = mapping


new_sources = _PortalGroup(NEW_PORTALS)
additional_sources = _PortalGroup(EXTRA_PORTALS)


def client(source, portal, page_size=50, queue=None, skip_existing=True):
    if source not in CLIENTS:
        raise ValueError('不支持的公司或招聘形式')
    return CLIENTS[source](portal, page_size=page_size, queue=queue, skip_existing=skip_existing)


def parse_post(post, source, portal):
    return PARSERS[source]().parse(post, portal)


def run_source(source, portal, full=False, max_pages_incremental=50, request_interval=0.4,
               page_size=50, queue=None, skip_existing=True, batch_id=None):
    if source == 'alibaba':
        from crawler.sources.alibaba.portal import run
        kwargs = dict(full=full, max_pages_incremental=max_pages_incremental,
                      request_interval=request_interval, queue=queue, page_size=page_size,
                      skip_existing=skip_existing)
        if batch_id is not None:
            kwargs['batch_id'] = batch_id
        return run(portal, **kwargs)
    if source == 'bytedance':
        from crawler.sources.bytedance.client import run
        portal_type = {'society': 2, 'campus': 3}[portal]
        return run(portal, portal_type, full=full, max_pages_incremental=max_pages_incremental,
                   request_interval=request_interval, queue=queue, page_size=page_size,
                   skip_existing=skip_existing)
    if source == 'tencent':
        from crawler.sources.tencent.client import run
        return run(portal, full=full, max_pages_incremental=max_pages_incremental,
                   request_interval=request_interval, queue=queue, page_size=page_size,
                   skip_existing=skip_existing)
    created = client(source, portal, page_size=page_size, queue=queue, skip_existing=skip_existing)
    return created.execute(full=full, max_pages=max_pages_incremental, interval=request_interval, queue=queue)
