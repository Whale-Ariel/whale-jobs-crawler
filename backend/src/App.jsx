import { LogoutOutlined } from '@ant-design/icons';
import { ProLayout } from '@ant-design/pro-components';
import { Dropdown } from 'antd';
import { useEffect, useState } from 'react';
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { api, clearToken, getToken } from './api';
import Charts from './pages/Charts';
import JobTable from './pages/JobTable';
import Login from './pages/Login';
import Welcome from './pages/Welcome';

function SourceHome() {
  const navigate = useNavigate();
  useEffect(() => {
    api('/api/sources').then((result) => {
      const first = result.data?.[0]?.source;
      navigate(first ? `/list/${first}` : '/welcome', { replace: true });
    });
  }, [navigate]);
  return null;
}

function Shell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [sources, setSources] = useState([]);
  useEffect(() => {
    if (!getToken()) return;
    api('/api/sources').then((result) => setSources(result.data || []));
  }, []);
  const menu = {
    path: '/',
    children: [
      { path: '/welcome', name: '欢迎' },
      {
        path: '/list',
        name: '查询表格',
        children: sources.map((item) => ({
          path: `/list/${item.source}`,
          name: item.name,
        })),
      },
      // 与「欢迎」「查询表格」同级。ProLayout 只认 children，这里不能改成 routes。
      { path: '/charts', name: '图表分析' },
    ],
  };
  if (!getToken()) {
    const redirect = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/user/login?redirect=${redirect}`} replace />;
  }
  return (
    <ProLayout
      title="思佳职位检索器"
      logo="/logo.svg"
      layout="mix"
      fixSiderbar
      location={{ pathname: location.pathname }}
      route={menu}
      menu={{ defaultOpenAll: true }}
      token={{ header: { colorBgHeader: '#fff' } }}
      menuItemRender={(item, dom) =>
        item.children?.length || item.routes?.length ? dom : <Link to={item.path || '/welcome'}>{dom}</Link>
      }
      avatarProps={{
        src: '/logo.svg',
        title: '管理员',
        render: (_props, dom) => (
          <Dropdown
            menu={{
              items: [
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: () => {
                    clearToken();
                    navigate('/user/login');
                  },
                },
              ],
            }}
          >
            {dom}
          </Dropdown>
        ),
      }}
    >
      <Routes>
        <Route path="/welcome" element={<Welcome />} />
        {/* 图表分析页，具体图表后续再接入 */}
        <Route path="/charts" element={<Charts />} />
        <Route path="/list/table-list" element={<SourceHome />} />
        <Route path="/list" element={<SourceHome />} />
        <Route path="/list/:source" element={<JobTable />} />
        <Route path="*" element={<Navigate to="/welcome" replace />} />
      </Routes>
    </ProLayout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/user/login" element={<Login />} />
      <Route path="/*" element={<Shell />} />
    </Routes>
  );
}
