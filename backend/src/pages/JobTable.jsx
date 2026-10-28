import { PageContainer, ProDescriptions, ProTable } from '@ant-design/pro-components';
import { Button, Drawer } from 'antd';
import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';

const sources = {
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

const portals = {
  society: '社招',
  campus: '校招',
  internship: '实习',
  dispatch: '派遣',
  graduate: '应届',
  research_intern: '研究型实习',
  regular_intern: '日常实习',
};

export default function JobTable() {
  const { source } = useParams();
  const [current, setCurrent] = useState();
  const columns = [
    {
      title: '职位名称',
      dataIndex: 'title',
      render: (dom, entity) => (
        <Button type="link" onClick={() => setCurrent(entity)}>
          {dom}
        </Button>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      search: false,
      render: (_, entity) => entity.source_name,
    },
    {
      title: '招聘形式',
      dataIndex: 'portal',
      valueType: 'select',
      valueEnum: Object.fromEntries(Object.entries(portals).map(([key, text]) => [key, { text }])),
      render: (_, entity) => portals[entity.portal] || entity.recruitment_name || entity.portal,
    },
    { title: '城市', dataIndex: 'city_name' },
    { title: '公司', dataIndex: 'company', search: false },
    { title: '发布时间', dataIndex: 'publish_time', search: false },
    {
      title: '链接',
      dataIndex: 'job_url',
      search: false,
      render: (_, entity) =>
        entity.job_url ? (
          <a href={entity.job_url} target="_blank" rel="noreferrer">
            打开
          </a>
        ) : null,
    },
    { title: '入队时间', dataIndex: 'enqueued_at', search: false },
  ];

  return (
    <PageContainer>
      <ProTable
        key={source}
        headerTitle={sources[source] || source}
        rowKey="seq"
        columns={columns}
        search={{ labelWidth: 120 }}
        pagination={{ pageSize: 20, showSizeChanger: false }}
        request={async (params) => {
          const query = new URLSearchParams({
            current: String(params.current || 1),
            title: params.title || '',
            source,
            portal: params.portal || '',
            city_name: params.city_name || '',
          });
          const result = await api(`/api/jobs?${query}`);
          return { data: result.data, success: result.success, total: result.total };
        }}
      />
      <Drawer
        size={640}
        open={!!current}
        title={current?.title}
        onClose={() => setCurrent(undefined)}
      >
        {current ? (
          <ProDescriptions
            column={1}
            dataSource={current}
            columns={[
              { title: '来源', dataIndex: 'source_name' },
              { title: '招聘形式', dataIndex: 'recruitment_name' },
              { title: '城市', dataIndex: 'city_name' },
              { title: '公司', dataIndex: 'company' },
              { title: '发布时间', dataIndex: 'publish_time' },
              { title: '职责', dataIndex: 'description', valueType: 'textarea' },
              { title: '要求', dataIndex: 'requirement', valueType: 'textarea' },
              { title: '链接', dataIndex: 'job_url' },
            ]}
          />
        ) : null}
      </Drawer>
    </PageContainer>
  );
}
