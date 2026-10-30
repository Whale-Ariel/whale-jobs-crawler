import { App, Alert, Button, Card, Input, List, Space, Table, Tabs, Tag, Typography, Upload } from 'antd';
import { FileTextOutlined, LinkOutlined, RobotOutlined } from '@ant-design/icons';
import { useRef, useState } from 'react';
import { PageContainer } from '@ant-design/pro-components';
import { api } from '../api';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const PORTALS = {
  society: '社招',
  campus: '校招',
  internship: '实习',
  dispatch: '派遣',
  graduate: '应届',
  research_intern: '研究型实习',
  regular_intern: '日常实习',
};

function JobLink({ url, children }) {
  if (!url) return <span style={{ color: 'rgba(0,0,0,0.45)' }}>{children}</span>;
  return (
    <a href={url} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}

// 职位结果表：匹配模式多一列「得分」和「命中信号」，查询模式只展示职位本身
function ResultsTable({ rows, showScore }) {
  const columns = [
    {
      title: '职位',
      dataIndex: 'title',
      render: (dom, entity) => <JobLink url={entity.job_url}>{dom || '(无标题)'}</JobLink>,
    },
    { title: '来源', dataIndex: 'source_name', render: (_, e) => e.source_name },
    {
      title: '招聘形式',
      dataIndex: 'portal',
      render: (_, e) => (PORTALS[e.portal] || e.recruitment_name || e.portal || '—'),
    },
    { title: '城市', dataIndex: 'city_name', render: (v) => v || '—' },
    { title: '公司', dataIndex: 'company', render: (v) => v || '—' },
    ...(showScore
      ? [
          {
            title: '得分',
            dataIndex: 'score',
            width: 80,
            sorter: (a, b) => (b.score || 0) - (a.score || 0),
            defaultSortOrder: 'descend',
            render: (v) => <Tag color="blue">{v}</Tag>,
          },
          {
            title: '命中信号',
            dataIndex: 'matched',
            render: (m) => {
              const skills = (m?.skills || []).slice(0, 4);
              return (
                <Space size={4} wrap>
                  {skills.map((s) => (
                    <Tag key={s} color="geekblue">
                      {s}
                    </Tag>
                  ))}
                  {(m?.skills?.length || 0) > 4 ? <Tag>+{m.skills.length - 4}</Tag> : null}
                </Space>
              );
            },
          },
        ]
      : []),
  ];
  return (
    <Table
      rowKey="seq"
      size="small"
      columns={columns}
      dataSource={rows}
      pagination={{ pageSize: 10, showSizeChanger: false }}
    />
  );
}

export default function Ai() {
  const { message } = App.useApp();
  const [resumeText, setResumeText] = useState('');
  const [fileName, setFileName] = useState('');
  const [matching, setMatching] = useState(false);
  const [matchResult, setMatchResult] = useState();

  const [query, setQuery] = useState('');
  const [querying, setQuerying] = useState(false);
  const [queryResult, setQueryResult] = useState();
  const fileInput = useRef(null);

  const runMatch = async () => {
    if (!resumeText.trim()) {
      message.warning('请先粘贴或上传简历内容');
      return;
    }
    setMatching(true);
    try {
      const result = await api('/api/ai/match', {
        method: 'POST',
        body: JSON.stringify({ text: resumeText, limit: 30 }),
      });
      if (result.success) setMatchResult(result);
      else message.error(result.errorMessage || '匹配失败');
    } catch {
      message.error('匹配失败，请重试');
    } finally {
      setMatching(false);
    }
  };

  const runQuery = async (text) => {
    if (!text.trim()) {
      message.warning('请输入查询问题');
      return;
    }
    setQuerying(true);
    try {
      const result = await api('/api/ai/query', {
        method: 'POST',
        body: JSON.stringify({ text }),
      });
      if (result.success) setQueryResult(result);
      else message.error(result.errorMessage || '查询失败');
    } catch {
      message.error('查询失败，请重试');
    } finally {
      setQuerying(false);
    }
  };

  const beforeUpload = (file) => {
    const reader = new FileReader();
    reader.onload = () => {
      setResumeText(String(reader.result || ''));
      setFileName(file.name);
    };
    reader.readAsText(file);
    return false; // 阻止自动上传，改为本地读取
  };

  return (
    <PageContainer title="AI 助手" extra={<Tag icon={<RobotOutlined />} color="purple">本地智能 · 可选大模型</Tag>}>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="两种用法"
        description="① 粘贴/上传简历，按技能与方向匹配库内职位；② 用自然语言提问，例如「哪些公司在招数据分析实习」。默认纯本地运行，无需联网；配置 OPENAI_API_KEY 后自然语言理解会走大模型。"
      />

      <Tabs
        defaultActiveKey="match"
        items={[
          {
            key: 'match',
            label: '简历匹配',
            children: (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Card size="small" title="简历内容">
                  <TextArea
                    rows={8}
                    value={resumeText}
                    onChange={(e) => setResumeText(e.target.value)}
                    placeholder="把简历正文粘贴到这里，或上传 .txt / .md 文件。例：熟悉 Python、SQL，做过用户行为分析与 A/B 测试，期望城市上海。"
                  />
                  <div style={{ marginTop: 12, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Upload beforeUpload={beforeUpload} showUploadList={false} accept=".txt,.md">
                      <Button icon={<FileTextOutlined />}>上传简历文件</Button>
                    </Upload>
                    {fileName ? <Text type="secondary">已读取：{fileName}</Text> : null}
                    <Button type="primary" loading={matching} onClick={runMatch}>
                      匹配职位
                    </Button>
                  </div>
                </Card>

                {matchResult ? (
                  <Card size="small" title={`匹配结果（命中 ${matchResult.matched} / 扫描 ${matchResult.total} 条）`}>
                    <Paragraph type="secondary" style={{ marginBottom: 12 }}>
                      从简历中识别到的信号：
                      <Space size={4} wrap style={{ marginLeft: 8 }}>
                        {(matchResult.signals?.skills || []).map((s) => (
                          <Tag key={s} color="geekblue">
                            {s}
                          </Tag>
                        ))}
                        {(matchResult.signals?.cities || []).map((c) => (
                          <Tag key={c} color="green">
                            {c}
                          </Tag>
                        ))}
                        {(matchResult.signals?.categories || []).map((c) => (
                          <Tag key={c}>{c}</Tag>
                        ))}
                      </Space>
                    </Paragraph>
                    <ResultsTable rows={matchResult.results} showScore />
                  </Card>
                ) : null}
              </Space>
            ),
          },
          {
            key: 'query',
            label: '自然语言查询',
            children: (
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Input.Search
                  size="large"
                  enterButton="查询"
                  loading={querying}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onSearch={runQuery}
                  placeholder="例如：哪些公司在招数据分析实习？腾讯的算法岗有哪些？上海的校招产品职位"
                />
                {queryResult ? (
                  <Card size="small">
                    <Alert
                      type="success"
                      showIcon
                      style={{ marginBottom: 16 }}
                      message={
                        <Space>
                          <span>我理解的查询：{queryResult.understanding}</span>
                          {queryResult.llm ? <Tag color="purple">大模型解析</Tag> : <Tag>本地解析</Tag>}
                        </Space>
                      }
                    />
                    <ResultsTable rows={queryResult.data} showScore={false} />
                  </Card>
                ) : null}
              </Space>
            ),
          },
        ]}
      />
    </PageContainer>
  );
}
