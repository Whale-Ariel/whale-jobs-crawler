import { App, Button, Card, Col, Divider, Empty, Row, Statistic, theme } from 'antd';
import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PageContainer } from '@ant-design/pro-components';
import { api } from '../api';
import './welcome.css';

const MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';

// 12×12 斜向箭头：路径撑满 viewBox，视觉宽度约 8.6px（不要用 1em 实心图标）
function DiagArrow({ className }) {
  return (
    <svg className={className} width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path
        d="M1.7 10.3 10.3 1.7M10.3 6.3V1.7H5.7"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// 一次性落点高亮：先移除再强制重排，保证连续触发也能重放动画
const flash = (el) => {
  if (!el) return;
  el.classList.remove('flash');
  void el.offsetWidth;
  el.classList.add('flash');
  setTimeout(() => el.classList.remove('flash'), 1000);
};

const keyboardActivate = (event, action) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    action();
  }
};

export default function Welcome() {
  const { token } = theme.useToken();
  const { message } = App.useApp();
  const navigate = useNavigate();
  // null = 未就绪（加载中或失败）；[] = 成功但为空。避免把失败当成 0 展示。
  const [sources, setSources] = useState(null);
  const [charts, setCharts] = useState(null);
  const [content, setContent] = useState('');
  const [readmeOk, setReadmeOk] = useState(false);
  const [loading, setLoading] = useState(true);
  const readmeRef = useRef(null);

  useEffect(() => {
    let alive = true;
    Promise.allSettled([api('/api/sources'), api('/api/charts'), api('/api/readme')])
      .then(([s, c, r]) => {
        if (!alive) return;
        if (s.status === 'fulfilled' && s.value?.success) setSources(s.value.data || []);
        if (c.status === 'fulfilled' && c.value?.success) setCharts(c.value);
        if (r.status === 'fulfilled') {
          setContent(r.value?.content || '');
          setReadmeOk(Boolean(r.value?.content));
        }
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const scrollToReadme = () => {
    const el = readmeRef.current;
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    flash(el.querySelector('.readme') || el.firstElementChild || el);
  };

  // README 的 markdown 是服务端返回的，拿不到节点 ref，用现有 .readme 类名定位；
  // 第一个 pre 是目录树，运行命令块用 run.py 关键字匹配
  const scrollToCode = () => {
    const pres = Array.from(document.querySelectorAll('.readme pre'));
    const el = pres.find((p) => p.textContent.includes('run.py')) || pres[0];
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    flash(el);
  };

  const copyCommands = async () => {
    const text = 'python3 run.py crawl\npython3 run.py sync';
    try {
      await navigator.clipboard.writeText(text);
      message.success('已复制');
    } catch {
      // 剪贴板 API 被拒/不可用时退回 execCommand，失败也要给反馈
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      if (ok) message.success('已复制');
      else message.error('复制失败，请手动复制');
    }
  };

  const typeCount = charts?.recruitment ? new Set(charts.recruitment.map((r) => r.type)).size : null;
  const stats = [
    { label: '覆盖公司', value: sources ? sources.length : null, accent: false },
    { label: '已入库职位', value: charts?.total ?? null, accent: true },
    { label: '招聘形式', value: typeCount, accent: false },
    { label: '覆盖城市', value: charts?.cities?.length ?? null, accent: false },
  ];

  const sortedSources = Array.isArray(sources) ? [...sources].sort((a, b) => (b.total || 0) - (a.total || 0)) : [];

  const guides = [
    {
      no: '1',
      title: '本地队列',
      desc: '抓取结果先写入 state/pending_queue.db 的 pending_jobs。',
      action: scrollToCode,
      aria: '滚动到 README 的运行命令',
    },
    {
      no: '2',
      title: '项目说明',
      desc: `本页 README 含 ${sources?.length ?? '—'} 家公司的入口、运行规则与代码布局。`,
      action: scrollToReadme,
      aria: '滚动到项目说明',
    },
    {
      no: '3',
      title: '查询表格',
      desc: '点上方任意公司卡片，进入该来源的职位列表。',
      action: () => navigate('/list'),
      aria: '进入查询表格',
    },
    {
      no: '4',
      title: '图表分析',
      desc: '各公司职位数与招聘形式占比，趋势都在这页。',
      action: () => navigate('/charts'),
      aria: '进入图表分析',
    },
  ];

  return (
    <PageContainer
      title="欢迎使用鲸鱼职位检索助手"
      extra={<span style={{ fontSize: 12, color: token.colorTextQuaternary }}>数据源 · state/pending_queue.db</span>}
    >
      {/* 3.1 首屏卡 */}
      <Card loading={loading} styles={{ body: { padding: 28 } }}>
        <div className="hero-wrap">
          <div className="hero-left">
            <span
              className="hero-tag"
              style={{ background: token.colorPrimaryBg, color: token.colorPrimary }}
            >
              本地优先 · SQLite
            </span>
            <h1 style={{ fontSize: 28, lineHeight: '40px', fontWeight: 600, color: token.colorText, margin: '16px 0 8px' }}>
              {sources?.length ? `${sources.length} 家公司的职位，一处检索` : '多家公司的职位，一处检索'}
            </h1>
            <p style={{ fontSize: 14, lineHeight: '24px', color: token.colorTextSecondary, margin: 0 }}>
              抓取只写本地 SQLite，已采集的职位自动跳过；云端同步单独执行 run.py sync。
            </p>
            <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
              <Button type="primary" onClick={() => navigate('/list')}>
                去查询表格
              </Button>
              <Button onClick={scrollToReadme}>查看 README</Button>
            </div>
          </div>
          <div className="hero-right">
            {/* 浅色命令卡：与浅色后台同体系，不做深色终端 */}
            <Card
              size="small"
              className="cmd-card"
              style={{ background: token.colorFillQuaternary, borderColor: token.colorBorderSecondary, borderRadius: token.borderRadius }}
              styles={{ body: { padding: 16 } }}
            >
              <div className="cmd-head">
                <span style={{ fontSize: 11, color: token.colorTextQuaternary, fontFamily: MONO }}>bash</span>
                <button type="button" className="cmd-copy" style={{ fontSize: 11, color: token.colorPrimary }} onClick={copyCommands}>
                  复制
                </button>
              </div>
              <div style={{ fontFamily: MONO }}>
                <div style={{ fontSize: 12, lineHeight: '18px', color: token.colorTextQuaternary }}># 抓取（已采集自动跳过）</div>
                <div style={{ fontSize: 12, lineHeight: '18px', fontWeight: 500, color: token.colorText }}>$ python3 run.py crawl</div>
                <div style={{ fontSize: 12, lineHeight: '18px', color: token.colorTextQuaternary }}># 推送云端</div>
                <div style={{ fontSize: 12, lineHeight: '18px', fontWeight: 500, color: token.colorText }}>$ python3 run.py sync</div>
              </div>
            </Card>
          </div>
        </div>
      </Card>

      {/* 3.2 指标行：四张都是 /charts 的次路径入口 */}
      <Row gutter={16} style={{ marginTop: 16 }}>
        {stats.map(({ label, value, accent }) => (
          <Col xs={24} sm={12} lg={6} key={label}>
            <Card
              size="small"
              hoverable
              className="stat-card"
              aria-label={`${label}，点击查看图表分析`}
              role="button"
              tabIndex={0}
              loading={loading}
              onClick={() => navigate('/charts')}
              onKeyDown={(event) => keyboardActivate(event, () => navigate('/charts'))}
              styles={{ body: { padding: '16px 20px' } }}
            >
              <div title="点击查看图表分析">
                <Statistic
                  title={
                    <div className="stat-head">
                      <span style={{ fontSize: 13, color: token.colorTextSecondary }}>{label}</span>
                      <DiagArrow className="stat-arrow" />
                    </div>
                  }
                  value={value ?? '—'}
                  styles={{
                    content: {
                      fontSize: 26,
                      fontWeight: 600,
                      lineHeight: '34px',
                      color: accent ? token.colorPrimary : token.colorText,
                    },
                  }}
                />
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* 3.3 按公司进入查询表格 */}
      {sortedSources.length > 0 && (
        <Card style={{ marginTop: 16 }} styles={{ body: { padding: '20px 24px' } }}>
          <div className="section-head">
            <span style={{ fontSize: 16, fontWeight: 600, color: token.colorText }}>按公司进入查询表格</span>
            <span style={{ fontSize: 12, color: token.colorTextQuaternary }}>
              共 {sources.length} 家 · {charts?.total ? `${charts.total.toLocaleString()} 条` : '—'} 职位
            </span>
          </div>
          <Row gutter={[12, 12]}>
            {sortedSources.map((item) => (
              <Col xs={12} sm={8} md={6} key={item.source}>
                <div
                  className="company-tile"
                  role="button"
                  tabIndex={0}
                  aria-label={`${item.name}，${item.total ?? 0} 条职位`}
                  onClick={() => navigate(`/list/${item.source}`)}
                  onKeyDown={(event) => keyboardActivate(event, () => navigate(`/list/${item.source}`))}
                >
                  <div style={{ fontSize: 14, fontWeight: 600, lineHeight: '20px', color: token.colorText }}>{item.name}</div>
                  <div style={{ fontSize: 12, lineHeight: '18px', color: token.colorTextSecondary }}>
                    {(item.total ?? 0).toLocaleString()} 条
                  </div>
                </div>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {/* 3.4 底部双栏：README + 引导卡 */}
      <Row gutter={16} align="top" className="bottom-row" style={{ marginTop: 16 }}>
        <Col className="readme-col">
          <div ref={readmeRef}>
            <Card className="readme" loading={loading} styles={{ body: { padding: '20px 24px' } }}>
              <div className="section-head">
                <span style={{ fontSize: 16, fontWeight: 600, color: token.colorText }}>项目说明</span>
                <span style={{ fontSize: 12, color: token.colorTextQuaternary, fontFamily: MONO }}>README.md</span>
              </div>
              {readmeOk ? (
                <>
                  <Divider style={{ margin: '0 0 16px' }} />
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                </>
              ) : (
                !loading && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="数据暂不可用" />
              )}
            </Card>
          </div>
        </Col>
        <Col className="guide-col">
          {guides.map(({ no, title, desc, action, aria }) => (
            <Card
              key={no}
              size="small"
              hoverable
              className="guide-card"
              role="button"
              tabIndex={0}
              aria-label={aria}
              onClick={action}
              onKeyDown={(event) => keyboardActivate(event, action)}
              styles={{ body: { display: 'flex', gap: 12, alignItems: 'flex-start', padding: 16 } }}
            >
              <div
                className="guide-no"
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: token.borderRadius,
                  background: token.colorPrimary,
                  color: '#fff',
                  fontSize: 14,
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {no}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="guide-title-row">
                  <span style={{ fontSize: 14, fontWeight: 600, color: token.colorText }}>{title}</span>
                  <DiagArrow className="stat-arrow" />
                </div>
                <div style={{ fontSize: 13, lineHeight: '21px', color: token.colorTextSecondary }}>{desc}</div>
              </div>
            </Card>
          ))}
        </Col>
      </Row>

      {/* 3.5 页脚 */}
      <div style={{ textAlign: 'center', fontSize: 12, color: token.colorTextQuaternary, padding: '24px 0 8px' }}>
        鲸鱼职位检索助手 · 数据来自 {sources?.length || '—'} 家公司的公开招聘页面 · 本地 SQLite 存储
      </div>
    </PageContainer>
  );
}
