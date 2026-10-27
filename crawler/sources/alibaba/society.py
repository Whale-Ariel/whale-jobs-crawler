"""阿里社招唯一入口：站点配置驱动、独立会话/断点、已存在职位在详情请求前跳过。"""
import json
from pathlib import Path
import re
import urllib.parse
from crawler.sources.alibaba.client import CampusClient
from crawler.core.engine import crawl
from crawler.taxonomy import ALIASES

CONFIG_PATH = Path(__file__).with_name('sites.json')


def load_sites(config_path=None):
    config = json.loads(Path(config_path or CONFIG_PATH).read_text(encoding='utf-8'))
    sites = config['sites']
    ids,domains = set(),set()
    for site in sites:
        parsed = urllib.parse.urlsplit(site['domain'])
        if not re.fullmatch(r'[a-z0-9_]+',site['id']) or site['id'] in ids:
            raise ValueError('社招站点id重复或无效')
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query:
            raise ValueError('社招domain必须为不带路径的HTTPS地址')
        if site['domain'] in domains or not site.get('business_unit'):
            raise ValueError('社招站点域名重复或缺少事业部名称')
        ids.add(site['id']);domains.add(site['domain'])
    return config


class SocietyClient(CampusClient):
    def __init__(self, site, defaults, interval=0.4):
        self.site,self.defaults=site,defaults
        super().__init__(interval=interval,base_url=site['domain'],
                         entry_path=site['entry_path']+'?lang='+defaults['language'],api_prefix=site.get('api_prefix',''))

    def _search(self, page, page_size, filters=None):
        body=dict(channel=self.defaults['channel'],language=self.defaults['language'],batchId='',
                  categories='',deptCodes=[],key='',pageIndex=page,pageSize=page_size,regions='',subCategories='')
        body.update(filters or {})
        result=self.call(self.defaults['search_path'],body)
        if not isinstance(result,dict) or not isinstance(result.get('datas'),list) or not isinstance(result.get('totalCount'),int):
            raise RuntimeError('社招搜索响应结构错误')
        return result

    def search(self,page,page_size):
        window=self.site.get('result_window')
        if not window:
            return self._search(page,page_size)
        if not hasattr(self,'_window_snapshot'):
            found={}
            first=self._search(1,page_size)
            expected=first['totalCount']
            def collect(first,filters=None):
                for post in first['datas']:
                    found[str(post['id'])]=post
                for current in range(2,min((first['totalCount']+page_size-1)//page_size,window//page_size)+1):
                    result=self._search(current,page_size,filters)
                    if not result['datas']:
                        raise RuntimeError('窗口内提前返回空页，拒绝宣称全量完成')
                    for post in result['datas']:
                        found[str(post['id'])]=post
            collect(first)
            if len(found)<expected:
                cities=self.call('/region/hot',{'channel':self.defaults['channel'],'language':self.defaults['language']})
                if not isinstance(cities,list):
                    raise RuntimeError('城市筛选结构错误')
                for city in cities:
                    filters={'regions':str(city['code'])}
                    collect(self._search(1,page_size,filters),filters)
                    print(f"[窗口分组] {self.site['id']} {city['name']} 唯一职位 {len(found)}/{expected}",flush=True)
                    if len(found)>=expected:
                        break
            if len(found)<expected:
                # 从真实职位标题提取机构前缀，再与官方城市编码交叉分组。
                # 每组仍遵守原有搜索参数，最终以唯一ID覆盖总量为验收条件。
                prefixes=sorted({re.split('[-－—]',post.get('name') or '')[0].strip() for post in found.values()})
                for prefix in prefixes:
                    if not prefix:
                        continue
                    filters={'key':prefix}
                    first_group=self._search(1,page_size,filters)
                    collect(first_group,filters)
                    if first_group['totalCount']>window:
                        for city in cities:
                            sub_filters={'key':prefix,'regions':str(city['code'])}
                            collect(self._search(1,page_size,sub_filters),sub_filters)
                            if len(found)>=expected:
                                break
                    print(f"[窗口交叉分组] {self.site['id']} {prefix} 唯一职位 {len(found)}/{expected}",flush=True)
                    if len(found)>=expected:
                        break
            if len(found)<expected:
                raise RuntimeError(f'窗口分组仅覆盖{len(found)}/{expected}，保留失败状态，请补充筛选范围')
            self._window_snapshot=list(found.values())
        start=(page-1)*page_size
        return {'datas':self._window_snapshot[start:start+page_size],
                'totalCount':len(self._window_snapshot)}

    def detail(self, post):
        result=self.call(self.defaults['detail_path'],dict(id=post['id'],channel=self.defaults['channel'],language=self.defaults['language']))
        if not isinstance(result,dict) or str(result.get('id')) != str(post['id']):
            raise RuntimeError('社招详情缺失或职位ID不一致')
        return result


def parse_post(post,site):
    from crawler.sources.alibaba.portal import parse_post as parse_common
    from crawler.core.model import normalize_row
    row=parse_common(post,'society')
    unit=ALIASES.get(site['business_unit'],site['business_unit'])
    path=post.get('positionUrl') or '/off-campus/position-detail?'+urllib.parse.urlencode({'positionId':post['id']})
    parts=urllib.parse.urlsplit(path)
    prefix=site.get('api_prefix','')
    actual_path=parts.path
    if prefix and not actual_path.startswith(prefix+'/'):
        actual_path=prefix+'/'+actual_path.lstrip('/')
    query=urllib.parse.urlencode([(k,v) for k,v in urllib.parse.parse_qsl(parts.query) if k!='track_id'])
    address=site['domain']+actual_path+('?' +query if query else '')
    row.update(source_site=site['id'],business_unit=unit,business_units=[unit],job_url=address,
               sub_title=post.get('department'),organization_assignments=[])
    return normalize_row(row)


def run(full=False,max_pages_incremental=50,request_interval=0.4,queue=None,page_size=50,
        skip_existing=True,site_id=None,config_path=None,client_factory=SocietyClient):
    from crawler.core import queue as pending_queue
    if not 1 <= page_size <= 50 or max_pages_incremental < 1 or request_interval < 0:
        raise ValueError('无效的分页或间隔参数')
    queue=queue if queue is not None else pending_queue.default_queue()
    config=load_sites(config_path)
    sites=[s for s in config['sites'] if site_id is None or s['id']==site_id]
    if not sites:
        raise ValueError('没有匹配的社招站点')
    results,failed=[],[]
    for index,site in enumerate(sites,1):
        print(f"[阿里社招站点 {index}/{len(sites)}] {site['business_unit']} {site['domain']}",flush=True)
        try:
            client=client_factory(site,config['defaults'],interval=request_interval)
            def fetch(page):
                content=client.search(page,page_size)
                return content['datas'],content['totalCount']
            def parse(post):
                detail = client.detail(post) if config['defaults'].get('fetch_details',False) else post
                return parse_post(detail,site)
            result=crawl(source='alibaba',portal='society',namespace='alibaba_society_'+site['id'],
                fetch=fetch,parse=parse,page_size=page_size,full=full,max_pages=max_pages_incremental,
                interval=request_interval,queue=queue,skip_existing=skip_existing,
                context={'source_site':site['id'],'business_unit':site['business_unit']})
            results.append(result)
        except Exception as error:
            print(f"[ERROR] 社招站点 {site['id']}: {error}",flush=True)
            failed.append(site['id'])
    if failed:
        raise RuntimeError('阿里社招失败站点: '+', '.join(failed)+'；其他站点及已提交数据保留')
    return {'sites':results,'queued':sum(r['queued'] for r in results),
            'skipped_existing':sum(r['skipped_existing'] for r in results),
            'complete':all(r['complete'] for r in results)}


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='阿里统一社招入口')
    parser.add_argument('--site',help='只运行配置中的一个站点id')
    parser.add_argument('--full',action='store_true')
    parser.add_argument('--pages',type=int,default=50)
    parser.add_argument('--refresh-existing',action='store_true')
    args=parser.parse_args()
    run(site_id=args.site,full=args.full,max_pages_incremental=args.pages,skip_existing=not args.refresh_existing)
