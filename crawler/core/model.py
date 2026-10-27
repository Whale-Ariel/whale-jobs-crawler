"""统一职位身份与兼容旧队列。阿里星是项目标签，不是独立招聘批次。"""
from crawler.taxonomy import classify

CAMPUS_TYPES = {'graduate', 'campus', 'ali_star', 'research_intern', 'regular_intern', 'internship'}


def normalize_row(row):
    result = dict(row)
    raw = result.get('raw_data') or {}
    source = result.get('source')
    portal = result.get('recruitment_type') or result.get('type', 'society')
    tags = set(result.get('program_tags') or [])
    result['source_site'] = result.get('source_site') or ('taotian' if source == 'alibaba' and portal == 'society' else '')
    if source == 'alibaba' and portal == 'ali_star':
        portal = 'graduate'
        tags.add('ali_star')
    if source in {'bytedance', 'tencent', 'alibaba'}:
        classification = classify(source, portal, raw)
        keys = ('company','recruitment_type','recruitment_name') if source == 'alibaba' and portal == 'society' and row.get('source_site') else ('company','business_unit','business_units','recruitment_type','recruitment_name')
        result.update({key:classification[key] for key in keys})
    result['batch_id'] = str(result.get('batch_id') or (raw.get('batchId') if source == 'alibaba' else '') or '')
    if source == 'alibaba' and portal == 'society':
        result['batch_id'] = ''
    result['batch_name'] = result.get('batch_name') or (raw.get('batchName') if source == 'alibaba' else None)
    result['program_tags'] = sorted(tags)
    result['organization_assignments'] = result.get('organization_assignments') or []
    # 以明确的组织关系为准，不把不同顺序的名称/编码数组按下标配对。
    assignments = result['organization_assignments']
    if assignments:
        units = list(dict.fromkeys(g['business_unit'] for g in assignments if g.get('business_unit')))
        result['business_units'] = units
        result['business_unit'] = units[0] if len(units) == 1 else None
    return normalize_job_location(result)


def normalize_job_location(row):
    """job_url只存官网职位链接；address只保留实际办公地址，未知为None。"""
    result = dict(row)
    source = result.get('source')
    raw = result.get('raw_data') or {}
    address = result.get('address')
    legacy_url = address if isinstance(address, str) and address.startswith(('http://', 'https://')) else None
    url = result.get('job_url') or legacy_url
    if source == 'bytedance' and result.get('job_id'):
        channel = 'experienced' if (result.get('recruitment_type') or result.get('type')) == 'society' else 'campus'
        url = f'https://jobs.bytedance.com/{channel}/position/{result["job_id"]}/detail'
    elif source == 'tencent':
        url = url or raw.get('PostURL')
        if not url and result.get('job_id'):
            url = f'https://careers.tencent.com/jobdesc.html?postId={result["job_id"]}'
    elif source == 'alibaba' and not url and result.get('job_id'):
        from urllib.parse import urljoin
        if result.get('recruitment_type') == 'society':
            from crawler.sources.alibaba.society import load_sites
            site = next((s for s in load_sites()["sites"] if s['id'] == result.get('source_site')), None)
            if site:
                url = urljoin(site['domain'], raw.get('positionUrl') or f'/off-campus/position-detail?positionId={result["job_id"]}')
        else:
            url = urljoin('https://campus-talent.alibaba.com', raw.get('positionUrl') or f'/campus/position/{result["job_id"]}')
    result['job_url'] = url
    if legacy_url:
        result['address'] = None
    return result
