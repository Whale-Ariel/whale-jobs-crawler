import { readFileSync } from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { createServer as createViteServer } from 'vite';

const root = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(root, '..');
const dbPath = path.join(projectRoot, 'state', 'pending_queue.db');
const readmePath = path.join(projectRoot, 'README.md');
const PAGE_SIZE = 20;
const ACCOUNT = { username: 'admin', password: 'ant.design', name: '管理员' };

const COMPANIES = {
  bytedance: '字节跳动',
  tencent: '腾讯',
  alibaba: '阿里巴巴',
  netease: '网易',
  jd: '京东',
  meituan: '美团',
  baidu: '百度',
  kuaishou: '快手',
  bilibili: '哔哩哔哩',
  xiaohongshu: '小红书',
  didi: '滴滴',
  pdd: '拼多多',
  ctrip: '携程',
  iflytek: '科大讯飞',
  mihoyo: '米哈游',
  oppo: 'OPPO',
};

const tokens = new Set();
const db = new DatabaseSync(dbPath, { readOnly: true });

function like(value) {
  return `%${value.replace(/[\\%_]/g, (char) => `\\${char}`)}%`;
}

function toItem(row) {
  const payload = JSON.parse(row.payload);
  return {
    seq: row.seq,
    source: row.source,
    source_name: COMPANIES[row.source] || row.source,
    portal: row.portal,
    batch_id: row.batch_id,
    source_site: row.source_site,
    job_id: row.job_id,
    title: payload.title || '',
    company: payload.company || '',
    city_name: payload.city_name || '',
    recruitment_name: payload.recruitment_name || row.portal,
    publish_time: payload.publish_time || '',
    job_url: payload.job_url || '',
    description: payload.description || '',
    requirement: payload.requirement || '',
    enqueued_at: row.enqueued_at,
    version: row.version,
  };
}

function requireUser(req, res, next) {
  const header = req.get('authorization') || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : '';
  if (!tokens.has(token)) {
    res.status(401).json({ success: false, errorMessage: '请先登录' });
    return;
  }
  next();
}

const api = express.Router();
api.use(express.json());

api.post('/login', (req, res) => {
  const { username, password } = req.body || {};
  if (username !== ACCOUNT.username || password !== ACCOUNT.password) {
    res.json({ status: 'error', type: 'account' });
    return;
  }
  const token = cryptoToken();
  tokens.add(token);
  res.json({ status: 'ok', token, name: ACCOUNT.name });
});

api.get('/currentUser', requireUser, (_req, res) => {
  res.json({ success: true, data: { name: ACCOUNT.name, userid: ACCOUNT.username } });
});

api.get('/readme', requireUser, (_req, res) => {
  res.json({ success: true, content: readFileSync(readmePath, 'utf8') });
});

api.get('/sources', requireUser, (_req, res) => {
  const order = Object.keys(COMPANIES);
  const rows = db.prepare('SELECT source, COUNT(*) AS total FROM pending_jobs GROUP BY source').all();
  rows.sort((left, right) => {
    const leftIndex = order.indexOf(left.source);
    const rightIndex = order.indexOf(right.source);
    return (leftIndex === -1 ? order.length : leftIndex) - (rightIndex === -1 ? order.length : rightIndex);
  });
  res.json({
    success: true,
    data: rows.map((row) => ({
      source: row.source,
      name: COMPANIES[row.source] || row.source,
      total: row.total,
    })),
  });
});

api.get('/jobs', requireUser, (req, res) => {
  const current = Math.max(1, Number.parseInt(req.query.current, 10) || 1);
  const filters = [
    ['title', `json_extract(payload, '$.title') LIKE ? ESCAPE '\\'`, like],
    ['source', 'source = ?', (value) => value],
    ['portal', 'portal = ?', (value) => value],
    ['city_name', `json_extract(payload, '$.city_name') LIKE ? ESCAPE '\\'`, like],
  ];
  const where = [];
  const params = [];
  for (const [key, sql, bind] of filters) {
    const value = String(req.query[key] || '').trim();
    if (!value) continue;
    where.push(sql);
    params.push(bind(value));
  }
  const clause = where.length ? `WHERE ${where.join(' AND ')}` : '';
  const total = db.prepare(`SELECT COUNT(*) AS n FROM pending_jobs ${clause}`).get(...params).n;
  const rows = db.prepare(
    `SELECT seq, source, portal, batch_id, source_site, job_id, payload, enqueued_at, version
     FROM pending_jobs ${clause} ORDER BY seq DESC LIMIT ? OFFSET ?`,
  ).all(...params, PAGE_SIZE, (current - 1) * PAGE_SIZE);
  res.json({ success: true, total, pageSize: PAGE_SIZE, data: rows.map(toItem) });
});

function cryptoToken() {
  return Array.from(crypto.getRandomValues(new Uint8Array(24)), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

const app = express();
app.use('/api', api);

const vite = await createViteServer({
  root,
  server: { middlewareMode: true },
  appType: 'spa',
});
app.use(vite.middlewares);

const port = 8001;
app.listen(port, '127.0.0.1', () => {
  console.log(`思佳职位检索器 http://127.0.0.1:${port}/user/login`);
});
