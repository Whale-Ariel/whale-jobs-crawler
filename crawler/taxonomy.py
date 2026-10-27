"""公司、事业部、招聘形式分开存储；未知事业部不靠职位描述猜测。"""
COMPANIES = {'bytedance': '字节跳动', 'tencent': '腾讯', 'alibaba': '阿里巴巴', 'netease':'网易', 'jd':'京东', 'meituan':'美团', 'baidu':'百度', 'kuaishou':'快手', 'bilibili':'哔哩哔哩', 'xiaohongshu':'小红书', 'didi':'滴滴', 'pdd':'拼多多', 'ctrip':'携程', 'iflytek':'科大讯飞', 'mihoyo':'米哈游', 'oppo':'OPPO'}
RECRUITMENT_TYPES = {'dispatch':'派遣', 'society': '社招', 'campus': '校招', 'graduate': '应届生', 'internship': '实习生', 'ali_star': '阿里星',
                     'research_intern': '研究型实习生', 'regular_intern': '日常实习生'}
ALIBABA_UNITS = ['淘天集团', '淘宝闪购', '飞猪', '阿里国际', '阿里云', 'Token Foundry',
                 '千问办公', '千问事业部', '平头哥', '高德地图', '菜鸟', '虎鲸文娱集团',
                 '盒马', '阿里健康', '菜鸟驿站', '亚博科技', '橙狮体育', '阿里巴巴控股集团']
ALIASES = {'阿里巴巴国际数字商业集团': '阿里国际', '阿里国际数字商业集团': '阿里国际', '阿里云智能集团': '阿里云',
           '菜鸟集团': '菜鸟', '高德': '高德地图', '淘天': '淘天集团'}
FIELDS = ['company', 'business_unit', 'business_units', 'recruitment_type', 'recruitment_name']


def classify(source, portal, raw):
    units = []
    if source == 'alibaba':
        units = [ALIASES.get(x, x) for x in raw.get('circleNames') or []]
        if not units and portal == 'society':
            units = ['淘天集团']  # 专属招聘站点；不套用到集团校招站
    elif source == 'tencent':
        units = [raw['BGName']] if raw.get('BGName') else []
    else:
        dept = raw.get('department') or raw.get('department_name')
        if isinstance(dept, dict):
            dept = dept.get('name')
        if isinstance(dept, str) and dept:
            units = [dept]
    return dict(company=COMPANIES[source], business_unit=units[0] if len(units) == 1 else None,
                business_units=units, recruitment_type=portal,
                recruitment_name=RECRUITMENT_TYPES.get(portal, portal),
                source_site='', batch_id='', batch_name=None, program_tags=[], organization_assignments=[])
