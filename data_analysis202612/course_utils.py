"""课程的文件、文本与绘图工具；分析步骤保留在 Notebook 中。"""
from pathlib import Path
from datetime import datetime
import hashlib
import html
import json
import os
import re
import sqlite3

ROOT = Path(__file__).resolve().parent
# 将路径集中在一处，Notebook可以从不同工作目录启动，不依赖手动cd到某个固定层级。
DATA = ROOT / 'data'
TABLES = ROOT / 'artifacts' / 'tables'
FIGURES = ROOT / 'artifacts' / 'figures'
REPORTS = ROOT / 'reports'
KEY = ['source', 'portal', 'batch_id', 'source_site', 'job_id']
# 种子用于固定演示中的随机抽样/初始化，不保证不同软件版本的数值结果完全相同。
SEED = 42
COMPANIES = dict(bytedance='字节跳动', tencent='腾讯', alibaba='阿里巴巴', netease='网易',
                 jd='京东', meituan='美团', baidu='百度', kuaishou='快手', bilibili='哔哩哔哩',
                 xiaohongshu='小红书', didi='滴滴', pdd='拼多多', ctrip='携程',
                 iflytek='科大讯飞', mihoyo='米哈游', oppo='OPPO')


def sha256(path):
    """分块读取文件计算校验摘要；摘要用于确认输入不变，不是数据内容的业务ID。"""
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        # 每次只读1MiB，避免把数百MB的SQLite整份加载进内存。
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def snapshot_database():
    """返回(快照Path, 台账dict)，合并已提交WAL并保持一致性。

    原库使用mode=ro；目标是独立课程文件。已存在时只校验，不自动替换，
    这样上次生成的图表不会因为原队列同步/新增而失去对应的输入版本。
    """
    source = ROOT.parent / 'state' / 'pending_queue.db'
    target = DATA / 'raw' / 'pending_queue_snapshot.db'
    manifest_path = DATA / 'raw' / 'manifest.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        # 先写临时目标，备份成功后再更名；中途失败不会留下看似完整的正式快照。
        temporary = target.with_suffix('.tmp')
        src = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
        dst = sqlite3.connect(temporary)
        try:
            src.backup(dst)
            # 课程快照是独立文件，退出WAL模式后再设只读，免去依赖-shm/-wal。
            dst.execute('PRAGMA journal_mode=DELETE')
        finally:
            dst.close()
            src.close()
        temporary.replace(target)
        os.chmod(target, 0o444)  # 八进制权限：只读快照；只对课程副本设置，不修改源库权限。
        manifest = {
            'source': str(source), 'snapshot': str(target),
            'created_at': datetime.now().astimezone().isoformat(),
            'method': 'SQLite backup API; source mode=ro; includes committed WAL',
            'sha256': sha256(target), 'size_bytes': target.stat().st_size,
        }
        with sqlite3.connect(target.as_uri() + '?mode=ro', uri=True) as conn:
            manifest['schema_version'] = conn.execute('PRAGMA user_version').fetchone()[0]
            manifest['integrity_check'] = conn.execute('PRAGMA integrity_check').fetchone()[0]
            names = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            manifest['table_rows'] = {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                                      for (name,) in names}
        write_json(manifest_path, manifest)
    if not manifest_path.exists():
        raise RuntimeError('快照存在但台账缺失；请先核查，不自动覆盖快照。')
    # 校验摘要比仅看文件大小可靠：同样大小的文件也可能包含不同的数据。
    manifest = json.loads(manifest_path.read_text())
    assert sha256(target) == manifest['sha256'], '原始快照校验失败'
    assert manifest['integrity_check'] == 'ok'
    return target, manifest


def write_json(path, value):
    """写出UTF-8台账/指标；ensure_ascii=False保留可读中文，default=str兼容路径/时间。"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


def clean_text(value):
    """把非字符串缺失转为空串，去脚本/样式和HTML标签，并规范文本空白。

    调用方应写入新列保留原文。本函数是课程的轻量文本清洗，不是完整网页DOM解析器。
    """
    if not isinstance(value, str):
        return ''
    # re.S允许点号跨行；\1引用前面捕获的标签名，防止只删标签却保留脚本正文。
    value = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', ' ', value, flags=re.I | re.S)
    value = re.sub(r'<[^>]+>', ' ', value)
    # HTML实体例如&amp;还原成&；连续空白缩成一个空格，再去除两端空白。
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()


CITY_ALIASES = {
    'Beijing': '北京', 'Shanghai': '上海', 'Shenzhen': '深圳', 'Guangzhou': '广州',
    'Hangzhou': '杭州', 'Chengdu': '成都', 'Nanjing': '南京', 'Wuhan': '武汉',
    'Suzhou': '苏州', 'Tianjin': '天津', 'Chongqing': '重庆', "Xi’an": '西安',
    "Xi'an": '西安', 'Xian': '西安', 'Hefei': '合肥', 'Dongguan': '东莞',
    'Sanya': '三亚', 'Haikou': '海口', 'Qingdao': '青岛', 'Xiamen': '厦门',
    'Fuzhou': '福州', 'Changsha': '长沙', 'Zhengzhou': '郑州', 'Jinan': '济南',
    'Hong Kong': '香港', 'HongKong': '香港', 'Singapore': '新加坡', 'Tokyo': '东京',
    'London': '伦敦', 'Seoul': '首尔', 'Bangkok': '曼谷', 'Sydney': '悉尼',
    'Kuala Lumpur': '吉隆坡', 'San Francisco': '旧金山', 'Los Angeles': '洛杉矶',
    'New York': '纽约', 'Taipei': '台北',
}
PROVINCES = set('河北 山西 辽宁 吉林 黑龙江 江苏 浙江 安徽 福建 江西 山东 河南 湖北 湖南 广东 海南 四川 贵州 云南 陕西 甘肃 青海 台湾 内蒙古 广西 宁夏 新疆 西藏'.split())


def normalize_locations(city_list, city_name):
    """返回去重地点标签list[str]，支持列表含字典、复合字符串与备用city_name。

    本函数只做格式/别名规范化；是否为城市交给location_level判断。
    因此不会把“广东省”偷偷改成“广州”，未知地点也不会无记录丢弃。
    """
    values = city_list if isinstance(city_list, list) and city_list else [city_name]
    locations = []
    aliases = {k.casefold(): v for k, v in CITY_ALIASES.items()}  # 比较别名时忽略英文大小写。
    for item in values:
        if isinstance(item, dict):
            # 不同官网的城市对象字段不同，按明确顺序取可读名称，不展开成任意值。
            item = item.get('name') or item.get('i18n_name') or item.get('en_name')
        if not isinstance(item, str):
            continue
        for token in re.split(r'[,，、;；/|\n]+', item):
            token = token.strip()
            if '·' in token:  # “安徽省·合肥市”的最后一段是更具体的地点。
                token = token.split('·')[-1].strip()
            token = aliases.get(token.casefold(), token)
            if token.endswith('市'):
                token = token[:-1]
            if token and token not in locations:  # 职位内去重，同时保留官网首次出现的顺序。
                locations.append(token)
    return locations


def location_level(label):
    """规则标记地理层级；城市候选不是通过完整地名库校验的地理编码。"""
    if label in PROVINCES or label.endswith(('省', '自治区', '自治州', '地区')):
        return '省级或地区'
    if label in {'全国', '中国', '海外', '不限', '远程', '其他', '全国各地', '全球', 'China', 'Remote', '中国大陆'}:
        return '范围或国家'
    if label.endswith(('区', '县')):
        return '区县待核验'
    # 英文未映射、地址和复杂标签不直接归入城市排行榜。
    if re.search(r'[A-Za-z0-9]|省|路|街|（|\(', label):
        return '待核验'
    return '城市候选'


SKILLS = {
    'Python': r'(?<![a-z0-9_])python(?![a-z0-9_])',
    'SQL': r'(?<![a-z0-9_])(?:sql|mysql|postgresql|postgres|sql\s*server|hive\s*sql)(?![a-z0-9_])',
    'Java': r'(?<![a-z0-9_])java(?![a-z0-9_])',
    'JavaScript/TypeScript': r'(?<![a-z0-9_])(?:javascript|typescript)(?![a-z0-9_])',
    'Excel': r'(?<![a-z0-9_])excel(?![a-z0-9_])',
    'BI工具': r'(?<![a-z0-9_])(?:tableau|power\s*bi|superset)(?![a-z0-9_])|商业智能',
    'Spark': r'(?<![a-z0-9_])(?:spark|pyspark)(?![a-z0-9_])',
    'Hadoop/Hive': r'(?<![a-z0-9_])(?:hadoop|hive)(?![a-z0-9_])',
    '机器学习': r'机器学习|machine\s+learning',
    '深度学习': r'深度学习|deep\s+learning|(?<![a-z0-9_])(?:pytorch|tensorflow)(?![a-z0-9_])',
    '大模型': r'大模型|大语言模型|(?<![a-z0-9_])(?:llm|llms|chatgpt)(?![a-z0-9_])',
    'A/B测试': r'a\s*/\s*b\s*(?:test|实验|测试)|ab\s*(?:test|实验|测试)|实验设计',
    '统计分析': r'统计分析|统计学|假设检验|回归分析|statistical\s+analysis',
    '数据可视化': r'数据可视化|可视化分析|data\s+visuali[sz]ation',
    '沟通协作': r'沟通|跨团队|跨部门|communication|collaboration',
    '项目管理': r'项目管理|project\s+management',
    '用户研究': r'用户研究|用户调研|user\s+research',
    '英语': r'英语|英文|(?<![a-z])english(?![a-z])',
}


def skill_hits(text):
    """返回每个词典技能的0/1命中；1仅表示文本提及，不代表必须、精通或个人能力。"""
    # re.search找到第一次匹配即可；int(bool(...))显式得到可聚合的0/1。
    return {name: int(bool(re.search(pattern, text, re.I))) for name, pattern in SKILLS.items()}


def experience_min(text):
    """仅抽取明确的阿拉伯数字+年+经验；复杂/英文/中文数字留空。"""
    if re.search(r'不限经验|经验不限|无经验要求', text):
        return 0.0
    # 上限条件不构成最低经验，先排除，防止从“3年以下”误抽出最低3年。
    text = re.sub(r'\d{1,2}\s*年(?:及)?以下[^，。；;]*经验', '', text)
    # 不把“3年规划”“团队成立5年”识别为个人工作经验。
    matches = re.findall(r'(?<!\d)(\d{1,2})(?:\s*[-~—至到]\s*\d{1,2})?\s*年(?:以上|及以上|左右)?(?:的)?(?:相关|工作|岗位|行业|开发|分析|数据|产品|运营|项目|实际|从业|专业|领域|研究|实践){0,4}经验', text)
    # 一个岗位可能写多项经验；这里返回匹配到的最小值，只是宽松下界线索，并非严格门槛。
    return float(min(map(int, matches))) if matches else float('nan')


def degree_from_text(text):
    """返回中文学历提示；不替换官网结构化字段，也不把未抽取解释为不限学历。"""
    if re.search(r'学历不限|不限学历', text):
        return '不限'
    # 只保留邻近“学历/学位/以上/毕业”等要求语境的中文匹配。
    for token in ['大专', '本科', '硕士', '博士']:
        if re.search(token + r'(?:及以上|以上|或以上|学历|学位|毕业)', text):
            return token
    return '未抽取'


FOCUS_PATTERN = r'数据分析|数据科学|数据挖掘|商业分析|商业智能|\bdata\s+(?:analyst|scientist)\b|business\s+intelligence'


def setup_plotting():
    """优先选可用中文字体，统一图形显示；缺字不静默忽略，便于视觉验收。"""
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    choices = ['Arial Unicode MS', 'Heiti TC', 'Songti SC', 'Noto Sans CJK SC', 'SimHei']
    available = [n for n in choices if n in names]
    plt.rcParams.update({'font.family': available + ['DejaVu Sans'], 'axes.unicode_minus': False,
                         'figure.dpi': 110, 'savefig.dpi': 160, 'axes.spines.top': False,
                         'axes.spines.right': False, 'font.size': 10})
    if not available:
        print('提示：当前系统无中文字体，建议安装 Noto Sans CJK SC 后重启内核。')


def save_figure(fig, name, note):
    """为图添加快照日期、来源和口径，导出PNG后在Notebook显示，再关闭画布。"""
    import matplotlib.pyplot as plt
    manifest = json.loads((DATA / 'raw' / 'manifest.json').read_text())
    fig.text(0.01, 0.01, f"来源：官网采集队列快照 | 快照日期 {manifest['created_at'][:10]}\n{note}",
             fontsize=8, color='#555555', va='bottom')
    fig.tight_layout(rect=(0, 0.09, 1, 1))  # 画布底部留9%给两行来源/口径说明。
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f'{name}.png', bbox_inches='tight')
    plt.show()
    plt.close(fig)


def csv_export(frame, name):
    """导出无行索引的CSV底稿；utf-8-sig便于常见表格软件正确显示中文。"""
    TABLES.mkdir(parents=True, exist_ok=True)
    frame.to_csv(TABLES / f'{name}.csv', index=False, encoding='utf-8-sig')
