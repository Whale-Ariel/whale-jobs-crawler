import { PageContainer } from '@ant-design/pro-components';
import { Card } from 'antd';
import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../api';
import './welcome.css';

const cards = [
  ['1', '本地队列', '抓取结果先写入 state/pending_queue.db 的 pending_jobs。'],
  ['2', '项目说明', '左侧是仓库 README，包含 16 家公司的入口和运行规则。'],
  ['3', '查询表格', '左侧按来源分开，点进某一家后每页 20 条查看该公司的职位。'],
];

export default function Welcome() {
  const [content, setContent] = useState('');
  useEffect(() => {
    api('/api/readme').then((result) => setContent(result.content || ''));
  }, []);
  return (
    <PageContainer title="欢迎使用思佳职位检索器">
      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <Card style={{ flex: '2 1 640px', minWidth: 0 }} className="readme">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </Card>
        <div style={{ flex: '1 1 260px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {cards.map(([index, title, desc]) => (
            <Card key={index} hoverable size="small">
              <div style={{ display: 'flex', gap: 12 }}>
                <div
                  style={{
                    width: 40,
                    height: 40,
                    borderRadius: 8,
                    background: '#1677ff',
                    color: '#fff',
                    fontWeight: 700,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {index}
                </div>
                <div>
                  <h4 style={{ margin: '0 0 4px' }}>{title}</h4>
                  <p style={{ margin: 0, color: 'rgba(0,0,0,0.45)' }}>{desc}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </PageContainer>
  );
}
