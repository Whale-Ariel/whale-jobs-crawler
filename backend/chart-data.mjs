// 图表口径与课程一致：一条记录是一条职位发布，不是招聘人数。
// 城市按「覆盖」计，同一职位可以进入多个城市。薪资字段全空，这里不产出薪资序列。

export const PORTALS = {
  society: '社招',
  campus: '校招',
  internship: '实习',
  dispatch: '派遣',
  graduate: '应届',
  research_intern: '科研实习',
  regular_intern: '日常实习',
};

const PORTAL_ORDER = ['社招', '校招', '应届', '实习', '日常实习', '科研实习', '派遣'];

const DEGREE_LABELS = {
  bachelor: '本科',
  undergraduate: '本科',
  'UNDERGRADUATE-AND-ABOVE': '本科及以上',
  master: '硕士',
  'MASTER-AND-ABOVE': '硕士及以上',
  doctorate: '博士',
  doctor: '博士',
  college: '大专',
  other: '其他',
  本科: '本科',
  硕士: '硕士',
  博士: '博士',
  大专: '大专',
  不限: '不限',
};

const DEGREE_ORDER = ['博士', '硕士及以上', '硕士', '本科及以上', '本科', '大专', '不限', '其他'];

export const CITY_ALIASES = {
  beijing: '北京',
  shanghai: '上海',
  shenzhen: '深圳',
  guangzhou: '广州',
  hangzhou: '杭州',
  chengdu: '成都',
  nanjing: '南京',
  wuhan: '武汉',
  suzhou: '苏州',
  tianjin: '天津',
  chongqing: '重庆',
  "xi'an": '西安',
  'xi’an': '西安',
  xian: '西安',
  hefei: '合肥',
  dongguan: '东莞',
  sanya: '三亚',
  haikou: '海口',
  qingdao: '青岛',
  xiamen: '厦门',
  fuzhou: '福州',
  changsha: '长沙',
  zhengzhou: '郑州',
  jinan: '济南',
  'hong kong': '香港',
  hongkong: '香港',
  singapore: '新加坡',
  tokyo: '东京',
  london: '伦敦',
  seoul: '首尔',
  bangkok: '曼谷',
  sydney: '悉尼',
  'kuala lumpur': '吉隆坡',
  'san francisco': '旧金山',
  'los angeles': '洛杉矶',
  'new york': '纽约',
  taipei: '台北',
};

const PROVINCES = new Set('河北 山西 辽宁 吉林 黑龙江 江苏 浙江 安徽 福建 江西 山东 河南 湖北 湖南 广东 海南 四川 贵州 云南 陕西 甘肃 青海 台湾 内蒙古 广西 宁夏 新疆 西藏'.split(' '));
const BROAD_PLACES = new Set(['全国', '中国', '海外', '不限', '远程', '其他', '全国各地', '全球', 'China', 'Remote', '中国大陆']);

export const SKILLS = [
  ['Python', /(?<![a-z0-9_])python(?![a-z0-9_])/i],
  ['SQL', /(?<![a-z0-9_])(?:sql|mysql|postgresql|postgres|sql\s*server|hive\s*sql)(?![a-z0-9_])/i],
  ['Java', /(?<![a-z0-9_])java(?![a-z0-9_])/i],
  ['JavaScript/TypeScript', /(?<![a-z0-9_])(?:javascript|typescript)(?![a-z0-9_])/i],
  ['Excel', /(?<![a-z0-9_])excel(?![a-z0-9_])/i],
  ['BI工具', /(?<![a-z0-9_])(?:tableau|power\s*bi|superset)(?![a-z0-9_])|商业智能/i],
  ['Spark', /(?<![a-z0-9_])(?:spark|pyspark)(?![a-z0-9_])/i],
  ['Hadoop/Hive', /(?<![a-z0-9_])(?:hadoop|hive)(?![a-z0-9_])/i],
  ['机器学习', /机器学习|machine\s+learning/i],
  ['深度学习', /深度学习|deep\s+learning|(?<![a-z0-9_])(?:pytorch|tensorflow)(?![a-z0-9_])/i],
  ['大模型', /大模型|大语言模型|(?<![a-z0-9_])(?:llm|llms|chatgpt)(?![a-z0-9_])/i],
  ['A/B测试', /a\s*\/\s*b\s*(?:test|实验|测试)|ab\s*(?:test|实验|测试)|实验设计/i],
  ['统计分析', /统计分析|统计学|假设检验|回归分析|statistical\s+analysis/i],
  ['数据可视化', /数据可视化|可视化分析|data\s+visuali[sz]ation/i],
  ['沟通协作', /沟通|跨团队|跨部门|communication|collaboration/i],
  ['项目管理', /项目管理|project\s+management/i],
  ['用户研究', /用户研究|用户调研|user\s+research/i],
  ['英语', /英语|英文|(?<![a-z])english(?![a-z])/i],
];

const FOCUS = /数据分析|数据科学|数据挖掘|商业分析|商业智能|\bdata\s+(?:analyst|scientist)\b|business\s+intelligence/i;

export function cleanText(value) {
  if (typeof value !== 'string') return '';
  return value
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;|&#160;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/\s+/g, ' ')
    .trim();
}

function locationLevel(label) {
  if (PROVINCES.has(label) || /(?:省|自治区|自治州|地区)$/.test(label)) return '省级或地区';
  if (BROAD_PLACES.has(label)) return '范围或国家';
  if (/(?:区|县)$/.test(label)) return '区县待核验';
  if (/[A-Za-z0-9]|省|路|街|（|\(/.test(label)) return '待核验';
  return '城市候选';
}

export function cityCandidates(payload) {
  const cityList = payload.city_list;
  const values = Array.isArray(cityList) && cityList.length ? cityList : [payload.city_name];
  const locations = [];
  for (const item of values) {
    let text = item;
    if (text && typeof text === 'object') text = text.name || text.i18n_name || text.en_name;
    if (typeof text !== 'string') continue;
    for (let token of text.split(/[,，、;；/|\n]+/)) {
      token = token.trim();
      if (token.includes('·')) token = token.split('·').pop().trim();
      token = CITY_ALIASES[token.toLowerCase()] || token;
      if (token.endsWith('市')) token = token.slice(0, -1);
      if (token && !locations.includes(token)) locations.push(token);
    }
  }
  return locations.filter((label) => locationLevel(label) === '城市候选');
}

function degreeLabel(value) {
  if (value == null || value === '') return '';
  const text = String(value).trim();
  return DEGREE_LABELS[text] || DEGREE_LABELS[text.toLowerCase()] || text;
}

function ranked(counter, limit) {
  return [...counter.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0], 'zh')).slice(0, limit);
}

export function buildChartData(db, companies) {
  const companyJobs = new Map();
  const recruitment = new Map();
  const cities = new Map();
  const degreeByCompany = new Map();
  const degreeFilled = new Map();
  const categories = new Map();
  const skillHits = new Map(SKILLS.map(([name]) => [name, 0]));
  let total = 0;
  let focusJobs = 0;
  let bytedanceSociety = 0;

  // node:sqlite 的 iterate() 会把较长的 payload 读坏，所以按 seq 分页用 all()。
  const page = db.prepare('SELECT source, portal, payload FROM pending_jobs ORDER BY seq LIMIT ? OFFSET ?');
  const pageSize = 500;
  for (let offset = 0; ; offset += pageSize) {
    const rows = page.all(pageSize, offset);
    if (!rows.length) break;
    for (const row of rows) accumulate(row);
  }

  function accumulate(row) {
    total += 1;
    const payload = JSON.parse(row.payload);
    const company = companies[row.source] || payload.company || row.source;
    companyJobs.set(company, (companyJobs.get(company) || 0) + 1);
    const portal = PORTALS[row.portal] || row.portal;
    const recruitmentKey = `${company}\0${portal}`;
    recruitment.set(recruitmentKey, (recruitment.get(recruitmentKey) || 0) + 1);
    if (row.source === 'bytedance' && row.portal === 'society') bytedanceSociety += 1;

    for (const city of cityCandidates(payload)) cities.set(city, (cities.get(city) || 0) + 1);

    const degree = degreeLabel(payload.required_degree);
    if (degree) {
      degreeFilled.set(company, (degreeFilled.get(company) || 0) + 1);
      const key = `${company}\0${degree}`;
      degreeByCompany.set(key, (degreeByCompany.get(key) || 0) + 1);
    }

    const category = String(payload.job_category_name || '').trim() || '未分类';
    categories.set(category, (categories.get(category) || 0) + 1);

    if (FOCUS.test(payload.title || '')) {
      focusJobs += 1;
      const text = `${cleanText(payload.description)}\n${cleanText(payload.requirement)}`;
      for (const [name, pattern] of SKILLS) {
        if (pattern.test(text)) skillHits.set(name, skillHits.get(name) + 1);
      }
    }
  }

  const companyRows = ranked(companyJobs).map(([company, jobs]) => ({
    company,
    jobs,
    share: jobs / total,
  }));
  const recruitmentRows = [];
  for (const { company } of companyRows) {
    const slices = PORTAL_ORDER
      .map((type) => ({ company, type, jobs: recruitment.get(`${company}\0${type}`) || 0 }))
      .filter((item) => item.jobs > 0);
    const known = new Set(slices.map((item) => item.type));
    for (const [key, jobs] of recruitment) {
      const [name, type] = key.split('\0');
      if (name === company && !known.has(type) && jobs > 0) slices.push({ company, type, jobs });
    }
    recruitmentRows.push(...slices);
  }

  const degreeCompanies = companyRows
    .filter((item) => (degreeFilled.get(item.company) || 0) / item.jobs >= 0.3)
    .map((item) => item.company);
  const degreeRows = [];
  for (const company of degreeCompanies) {
    for (const degree of DEGREE_ORDER) {
      const jobs = degreeByCompany.get(`${company}\0${degree}`) || 0;
      if (jobs > 0) degreeRows.push({ company, degree, jobs });
    }
  }

  const notes = [
    `当前队列 ${total.toLocaleString('zh-CN')} 条职位发布。一条记录不是一个招聘名额，也不能当成整个招聘市场。`,
    '城市按覆盖计算，一个职位可以同时计入多个城市。省级、国家和待核验地点不进城市榜。',
    '学历图只保留结构化学历有值率不低于 30% 的公司。薪资字段有值率为 0，本页不画薪资。',
    `技能图的分母是标题命中的数据相关岗位，共 ${focusJobs.toLocaleString('zh-CN')} 条。柱高是正文提及率，不是必须掌握的比例。`,
  ];
  if (bytedanceSociety === 10000) {
    notes.splice(1, 0, '字节跳动社招恰好 10,000 条，可能是采集停止线。类型构成图描述的是当前队列，不是官网全量。');
  }

  return {
    total,
    notes,
    companies: companyRows,
    recruitment: recruitmentRows,
    cities: ranked(cities, 12).map(([city, jobs]) => ({ city, jobs, coverage: jobs / total })),
    degrees: degreeRows,
    categories: ranked(categories, 12).map(([category, jobs]) => ({ category, jobs, share: jobs / total })),
    skills: [...skillHits.entries()]
      .map(([skill, jobs]) => ({ skill, jobs, rate: focusJobs ? jobs / focusJobs : 0 }))
      .sort((left, right) => right.rate - left.rate || left.skill.localeCompare(right.skill, 'zh')),
    skillSubset: focusJobs,
  };
}
