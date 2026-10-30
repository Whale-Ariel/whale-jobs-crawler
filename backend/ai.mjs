// AI 层：默认纯本地（零依赖、离线可用），可选接入大模型增强自然语言理解。
// 设计原则：与图表层共用同一份信号定义（SKILLS / CITY_ALIASES / PORTALS），
// 避免「AI 理解的技能」和「图表统计的技能」对不上。

import { SKILLS, CITY_ALIASES, PORTALS, cleanText, cityCandidates } from './chart-data.mjs';

const SKILL_MAP = new Map(SKILLS);
const CITY_CANON = [...new Set(Object.values(CITY_ALIASES))];

// 类别/方向关键词：既用于简历信号，也用于自然语言里的「职位方向」
const CATEGORY_KEYWORDS = [
  '数据分析', '数据科学', '数据挖掘', '商业分析', '商业智能',
  '算法', '前端', '后端', '全栈', '产品', '产品经理', '运营', '测试', '运维', '安全',
  '客户端', 'android', 'ios', 'go', 'rust', 'java', 'python', 'c++',
];

/**
 * 从一段文本里抽取信号：命中的技能、城市、方向关键词。
 * 复用 chart-data 里的 SKILLS 正则，保证和图表口径一致。
 */
export function extractSignals(text) {
  const cleaned = cleanText(text).toLowerCase();
  const skills = [];
  for (const [name, pattern] of SKILLS) {
    if (pattern.test(cleaned)) skills.push(name);
  }
  const cities = [];
  for (const cn of CITY_CANON) {
    if (cleaned.includes(cn.toLowerCase()) && !cities.includes(cn)) cities.push(cn);
  }
  for (const key of Object.keys(CITY_ALIASES)) {
    if ((key.includes(' ') || /[a-z]/.test(key)) && cleaned.includes(key.toLowerCase())) {
      const cn = CITY_ALIASES[key];
      if (!cities.includes(cn)) cities.push(cn);
    }
  }
  const categories = CATEGORY_KEYWORDS.filter((kw) =>
    kw.toLowerCase().split(' ').some((part) => cleaned.includes(part)),
  );
  return { skills, cities, categories };
}

function scanJobs(db, cb) {
  // node:sqlite 的 iterate 会把较长 payload 读坏，按 seq 分页用 all()。
  const page = db.prepare('SELECT seq, source, portal, payload FROM pending_jobs ORDER BY seq LIMIT ? OFFSET ?');
  const pageSize = 500;
  for (let offset = 0; ; offset += pageSize) {
    const rows = page.all(pageSize, offset);
    if (!rows.length) break;
    for (const row of rows) cb(row);
  }
}

/**
 * 简历匹配：把简历文本抽成信号，对库内每条职位做信号重叠打分。
 * 返回 Top N + 命中理由，方便用户判断「为什么匹配」。
 */
export function matchResume(db, companies, text, { limit = 30 } = {}) {
  const { skills, cities, categories } = extractSignals(text);
  const wantedSkills = new Set(skills);
  const wantedCities = new Set(cities.map((c) => c.toLowerCase()));
  const wantedCats = new Set(categories.map((c) => c.toLowerCase()));
  const results = [];
  let scanned = 0;

  scanJobs(db, (row) => {
    scanned += 1;
    const payload = JSON.parse(row.payload);
    const title = String(payload.title || '').toLowerCase();
    const body = cleanText(`${payload.title || ''} ${payload.description || ''} ${payload.requirement || ''}`).toLowerCase();
    let score = 0;
    const matched = { skills: [], categories: [], cities: [] };

    for (const name of wantedSkills) {
      const pattern = SKILL_MAP.get(name);
      if (pattern && pattern.test(body)) {
        score += 3;
        matched.skills.push(name);
        if (pattern.test(title)) score += 2; // 出现在标题权重更高
      }
    }
    for (const cat of wantedCats) {
      if (body.includes(cat) || title.includes(cat)) {
        score += 1;
        if (!matched.categories.includes(cat)) matched.categories.push(cat);
      }
    }
    const jobCities = cityCandidates(payload);
    for (const jc of jobCities) {
      if (wantedCities.has(jc.toLowerCase())) {
        score += 2;
        if (!matched.cities.includes(jc)) matched.cities.push(jc);
      }
    }

    if (score > 0) {
      results.push({
        seq: row.seq,
        source: row.source,
        source_name: companies[row.source] || row.source,
        portal: row.portal,
        title: payload.title || '',
        company: payload.company || '',
        city_name: payload.city_name || jobCities[0] || '',
        job_url: payload.job_url || '',
        score,
        matched,
      });
    }
  });

  results.sort((a, b) => b.score - a.score || b.seq - a.seq);
  return {
    total: scanned,
    matched: results.length,
    signals: { skills, cities, categories },
    results: results.slice(0, limit),
  };
}

// ===== 自然语言查询：本地规则解析（始终可用） =====

const COMPANY_SHORT = (name) => (name.length >= 4 ? name.slice(0, 2) : name);

const PORTAL_RULES = [
  ['科研实习', 'research_intern'],
  ['日常实习', 'regular_intern'],
  ['实习', 'internship'],
  ['校招', 'campus'],
  ['校园招聘', 'campus'],
  ['社招', 'society'],
  ['社会招聘', 'society'],
  ['应届', 'graduate'],
  ['派遣', 'dispatch'],
];

function parseLocal(text, companies) {
  const t = text.toLowerCase();
  const filters = {};
  const notes = [];

  for (const [key, name] of Object.entries(companies)) {
    const aliases = [name, COMPANY_SHORT(name), key].map((s) => s.toLowerCase()).filter(Boolean);
    if (aliases.some((a) => t.includes(a))) {
      filters.source = key;
      notes.push(`公司：${name}`);
      break;
    }
  }

  for (const [kw, val] of PORTAL_RULES) {
    if (t.includes(kw)) {
      filters.portal = val;
      notes.push(`招聘形式：${PORTALS[val] || kw}`);
      break;
    }
  }

  const cityHits = [];
  for (const cn of CITY_CANON) {
    if (t.includes(cn.toLowerCase()) && !cityHits.includes(cn)) cityHits.push(cn);
  }
  for (const key of Object.keys(CITY_ALIASES)) {
    if ((key.includes(' ') || /[a-z]/.test(key)) && t.includes(key.toLowerCase())) {
      const cn = CITY_ALIASES[key];
      if (!cityHits.includes(cn)) cityHits.push(cn);
    }
  }
  if (cityHits.length) {
    filters.city_name = cityHits.join(' ');
    notes.push(`城市：${cityHits.join('、')}`);
  }

  const kw = [];
  for (const name of SKILLS.map(([n]) => n)) {
    if (SKILL_MAP.get(name).test(t)) kw.push(name);
  }
  for (const c of CATEGORY_KEYWORDS) {
    if (t.includes(c.toLowerCase()) && !kw.includes(c)) kw.push(c);
  }
  if (kw.length) {
    filters.title = kw.join(' ');
    notes.push(`关键词：${kw.join('、')}`);
  }

  const understanding = notes.length ? notes.join('；') : '未识别到明确条件，已返回全部职位';
  return { filters, understanding, llm: false };
}

// ===== 可选：大模型增强的自然语言解析 =====

async function chatJSON(llm, sys, user) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 15000);
  try {
    const res = await fetch(`${llm.baseURL}/chat/completions`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${llm.apiKey}` },
      body: JSON.stringify({
        model: llm.model,
        messages: [
          { role: 'system', content: sys },
          { role: 'user', content: user },
        ],
        response_format: { type: 'json_object' },
        temperature: 0,
      }),
      signal: ctrl.signal,
    });
    const json = await res.json();
    const content = json.choices?.[0]?.message?.content || '{}';
    return JSON.parse(content);
  } finally {
    clearTimeout(timer);
  }
}

async function parseWithLLM(text, companies, llm) {
  const sys =
    '你是招聘检索助手。把用户问题解析为 JSON：' +
    '{source:公司英文key或空串, portal:招聘形式英文key或空串, city:城市中文或空串, keyword:职位关键词或空串}。只输出 JSON。';
  const user = `可选公司：${Object.values(companies).join('/')}。可选招聘形式：${Object.values(PORTALS).join('/')}。问题：${text}`;
  const data = await chatJSON(llm, sys, user);
  const filters = {};
  const notes = [];
  if (data.source && companies[data.source]) {
    filters.source = data.source;
    notes.push(`公司：${companies[data.source]}`);
  }
  if (data.portal && PORTALS[data.portal]) {
    filters.portal = data.portal;
    notes.push(`招聘形式：${PORTALS[data.portal]}`);
  }
  if (data.city) {
    filters.city_name = String(data.city);
    notes.push(`城市：${data.city}`);
  }
  if (data.keyword) {
    filters.title = String(data.keyword);
    notes.push(`关键词：${data.keyword}`);
  }
  return {
    filters,
    understanding: notes.length ? notes.join('；') : '未识别到明确条件',
    llm: true,
  };
}

/**
 * 自然语言查询：配置了大模型就走大模型，否则退回本地规则解析。
 * llmConfig 为空或请求失败时不影响功能——始终有可用的本地结果。
 */
export async function parseQuery(text, { companies = {}, llmConfig = null } = {}) {
  if (llmConfig && llmConfig.apiKey) {
    try {
      return await parseWithLLM(text, companies, llmConfig);
    } catch {
      // 大模型不可用（没配 key / 超时 / 返回异常）→ 安静退回本地
    }
  }
  return parseLocal(text, companies);
}
