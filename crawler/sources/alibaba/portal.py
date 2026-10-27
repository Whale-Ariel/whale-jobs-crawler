"""阿里招聘调度：社招交给站点配置，校招按集团开放批次。"""
from crawler.core.engine import crawl
from crawler.sources.alibaba.parser import organization_assignments, parse_post

SOURCE = 'alibaba'
DEFAULT_PORTALS = ('society', 'campus')
SUPPORTED_PORTALS = (*DEFAULT_PORTALS, 'graduate', 'research_intern', 'regular_intern', 'internship', 'ali_star')


def run(portal, full=False, max_pages_incremental=50, request_interval=0.4, queue=None,
        page_size=50, batch_id=None, client=None, skip_existing=True):
    from crawler.core import queue as pending_queue
    from crawler.sources.alibaba.client import CampusClient
    if not 1 <= page_size <= 50 or max_pages_incremental < 1 or request_interval < 0:
        raise ValueError('无效的分页或请求间隔参数')
    if portal not in SUPPORTED_PORTALS:
        raise ValueError('无效的阿里招聘形式')
    queue = queue if queue is not None else pending_queue.default_queue()
    if portal == 'society':
        if batch_id:
            raise ValueError('社招不接受校招batch-id')
        from crawler.sources.alibaba import society as alibaba_society
        return alibaba_society.run(full=full,max_pages_incremental=max_pages_incremental,
            request_interval=request_interval,queue=queue,page_size=page_size,skip_existing=skip_existing)
    client = client or CampusClient(interval=min(request_interval,0.4))
    discovered = client.batches()
    queue.save_batches(discovered)
    selected = [batch for batch in discovered if
                (portal == 'campus' or portal == batch.portal or (portal == 'ali_star' and batch.has_ali_star))
                and (batch_id is None or batch.id == str(batch_id))]
    if not selected:
        raise ValueError(f'官网没有匹配的开放校招批次: portal={portal}, batch_id={batch_id}')
    results,failed = [],[]
    for index,batch in enumerate(selected,1):
        print(f'[阿里集团校招批次 {index}/{len(selected)}] {batch.name} ({batch.id})',flush=True)
        try:
            if not batch.id.isdigit():
                raise ValueError('无效的校招批次ID')
            conditions = client.conditions(batch)
            queue.cache_put(f'alibaba:conditions:{batch.id}','current',conditions)
            stars = client.star_ids(batch,page_size) if batch.has_ali_star and portal != 'ali_star' else set()
            def fetch(page):
                content = client.search(batch,page,page_size,ali_star=True if portal == 'ali_star' else None)
                return content['datas'],content['totalCount']
            def parse(post):
                version = str(post.get('modifyTime') or post.get('publishTime') or 'unknown')
                cache_key = f'alibaba:organizations:{batch.id}:{post["id"]}'
                groups = queue.cache_get(cache_key,version)
                if groups is None:
                    groups = client.organizations(post['id'])
                    queue.cache_put(cache_key,version,groups)
                tags = ['ali_star'] if portal == 'ali_star' or str(post['id']) in stars else []
                return parse_post(post,batch.portal,batch,organization_assignments(groups),tags)
            namespace = f'alibaba_campus_{batch.id}'+('_ali_star' if portal == 'ali_star' else '')
            result = crawl(source=SOURCE,portal=batch.portal,namespace=namespace,fetch=fetch,parse=parse,
                           page_size=page_size,full=full,max_pages=max_pages_incremental,
                           interval=request_interval,queue=queue,context={'batch_id':batch.id,'batch_name':batch.name},skip_existing=skip_existing)
            results.append(result)
        except Exception as error:
            print(f'[ERROR] 阿里校招批次 {batch.id}: {error}',flush=True)
            failed.append(batch.id)
    if failed:
        raise RuntimeError('阿里校招失败批次: '+', '.join(failed)+'；已提交的页面和其他批次保留')
    return {'batches':results,'queued':sum(r['queued'] for r in results),
            'new_rows':sum(r['new_rows'] for r in results),'complete':all(r['complete'] for r in results)}
