import { Bar, Column } from '@ant-design/charts';
import { PageContainer } from '@ant-design/pro-components';
import { Alert, Card, Col, Row, Spin } from 'antd';
import { useEffect, useState } from 'react';
import { api } from '../api';

const percentBarAxis = { x: { size: 88 }, y: { labelFormatter: '.0%' } };
const percentColumnAxis = { y: { labelFormatter: '.0%' } };
const countAxis = (title) => ({ x: { size: 88 }, y: { title } });

function ChartCard({ title, note, height, children }) {
  return (
    <Card title={title} style={{ marginBottom: 16 }}>
      <p style={{ marginTop: 0, color: 'rgba(0,0,0,0.45)' }}>{note}</p>
      <div style={{ height }}>{children}</div>
    </Card>
  );
}

export default function Charts() {
  const [data, setData] = useState();
  const [error, setError] = useState('');
  useEffect(() => {
    api('/api/charts')
      .then((result) => setData(result))
      .catch((reason) => setError(reason.message || '图表数据加载失败'));
  }, []);
  return (
    <PageContainer title="图表分析">
      {error ? <Alert type="error" title={error} /> : null}
      {!data && !error ? <Spin /> : null}
      {data ? (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            title="读图口径"
            description={
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {data.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            }
          />
          <Row gutter={16}>
            <Col xs={24} xl={12}>
              {/* 类别名是公司中文名，Ant Design Charts 用条形图做这类排名比较。 */}
              <ChartCard title="各公司职位数" note="条形图。横轴是职位条数，条上的占比是该公司占全部职位的比例。" height={520}>
                <Bar
                  data={data.companies}
                  xField="company"
                  yField="jobs"
                  height={520}
                  style={{ maxWidth: 28 }}
                  label={{ text: (item) => `${(item.share * 100).toFixed(1)}%`, position: 'right', style: { dx: 4 } }}
                  axis={countAxis('职位条数')}
                  tooltip={{ title: 'company', items: [{ channel: 'y', name: '职位条数' }] }}
                />
              </ChartCard>
            </Col>
            <Col xs={24} xl={12}>
              <ChartCard title="城市覆盖" note="条形图。覆盖率的分母是全部职位，各城市可以重复计算同一职位。" height={520}>
                <Bar
                  data={data.cities}
                  xField="city"
                  yField="jobs"
                  height={520}
                  style={{ maxWidth: 28 }}
                  label={{ text: (item) => `${(item.coverage * 100).toFixed(1)}%`, position: 'right', style: { dx: 4 } }}
                  axis={countAxis('覆盖职位数')}
                  tooltip={{ title: 'city', items: [{ channel: 'y', name: '覆盖职位数' }] }}
                />
              </ChartCard>
            </Col>
          </Row>
          {/* 16 家公司比的是构成，百分比堆叠条形图是这类占比比较的推荐图。 */}
          <ChartCard title="各公司招聘类型构成" note="百分比堆叠条形图。每家公司内部相加为 100%，用来比较结构，不比较绝对数量。" height={560}>
            <Bar
              data={data.recruitment}
              xField="company"
              yField="jobs"
              colorField="type"
              stack
              percent
              height={560}
              axis={percentBarAxis}
              legend={{ color: { position: 'bottom' } }}
              tooltip={{ title: 'company' }}
            />
          </ChartCard>
          <Row gutter={16}>
            <Col xs={24} xl={12}>
              {/* 公司只有少数几家，短标签用百分比堆叠柱状图。 */}
              <ChartCard title="学历构成" note="百分比堆叠柱状图。只包含结构化学历有值率不低于 30% 的公司。" height={420}>
                <Column
                  data={data.degrees}
                  xField="company"
                  yField="jobs"
                  colorField="degree"
                  stack
                  percent
                  height={420}
                  axis={percentColumnAxis}
                  legend={{ color: { position: 'bottom' } }}
                />
              </ChartCard>
            </Col>
            <Col xs={24} xl={12}>
              <ChartCard title="岗位类别" note="条形图。只展示数量最多的 12 类，未分类留在图里，不从分母中剔除。" height={420}>
                <Bar
                  data={data.categories}
                  xField="category"
                  yField="jobs"
                  height={420}
                  style={{ maxWidth: 24 }}
                  label={{ text: (item) => `${(item.share * 100).toFixed(1)}%`, position: 'right', style: { dx: 4 } }}
                  axis={countAxis('职位条数')}
                />
              </ChartCard>
            </Col>
          </Row>
          <ChartCard
            title="数据相关岗位的技能提及"
            note={`条形图。分母是 ${data.skillSubset.toLocaleString('zh-CN')} 条标题命中的数据相关岗位，柱高是职责或要求中的提及率。`}
            height={560}
          >
            <Bar
              data={data.skills}
              xField="skill"
              yField="rate"
              height={560}
              style={{ maxWidth: 24 }}
              axis={{ x: { size: 120 }, y: { labelFormatter: '.0%', title: '提及率' } }}
              label={{ text: (item) => `${(item.rate * 100).toFixed(1)}%`, position: 'right', style: { dx: 4 } }}
              tooltip={{ title: 'skill', items: [{ channel: 'y', name: '提及率', valueFormatter: '.1%' }] }}
            />
          </ChartCard>
        </>
      ) : null}
    </PageContainer>
  );
}
