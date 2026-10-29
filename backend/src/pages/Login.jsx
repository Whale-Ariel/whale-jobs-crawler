import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { LoginForm, ProFormCheckbox, ProFormText } from '@ant-design/pro-components';
import { Alert, App } from 'antd';
import { useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { api, getToken, setToken } from '../api';
import { safeRedirect } from '../redirect';

export default function Login() {
  const [failed, setFailed] = useState(false);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { message } = App.useApp();
  if (getToken()) {
    return <Navigate to={safeRedirect(params.get('redirect'))} replace />;
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'auto',
        backgroundImage:
          "url('https://mdn.alipayobjects.com/yuyan_qk0oxh/afts/img/V-_oS6r-i7wAAAAAAAAAAAAAFl94AQBr')",
        backgroundSize: '100% 100%',
      }}
    >
      <div style={{ flex: 1, padding: '32px 0' }}>
        <LoginForm
          logo={<img alt="logo" src="/logo.svg" />}
          title="鲸鱼职位检索助手"
          subTitle="用 AI 帮助你找到更适合你的好职位"
          contentStyle={{ minWidth: 280, maxWidth: '75vw' }}
          initialValues={{ autoLogin: true }}
          onFinish={async (values) => {
            const result = await api('/api/login', {
              method: 'POST',
              body: JSON.stringify(values),
            });
            if (result.status === 'ok') {
              setToken(result.token);
              message.success('登录成功！');
              navigate(safeRedirect(params.get('redirect')), { replace: true });
              return;
            }
            setFailed(true);
          }}
        >
          {failed ? (
            <Alert
              style={{ marginBottom: 24 }}
              title="账户或密码错误(admin/ant.design)"
              type="error"
              showIcon
            />
          ) : null}
          <ProFormText
            name="username"
            fieldProps={{ size: 'large', prefix: <UserOutlined /> }}
            placeholder="用户名: admin"
            rules={[{ required: true, message: '请输入用户名!' }]}
          />
          <ProFormText.Password
            name="password"
            fieldProps={{ size: 'large', prefix: <LockOutlined /> }}
            placeholder="密码: ant.design"
            rules={[{ required: true, message: '请输入密码！' }]}
          />
          <div style={{ marginBottom: 24 }}>
            <ProFormCheckbox noStyle name="autoLogin">
              自动登录
            </ProFormCheckbox>
            <a style={{ float: 'right' }}>忘记密码</a>
          </div>
        </LoginForm>
      </div>
      <div style={{ padding: 16, textAlign: 'center', color: 'rgba(0,0,0,0.45)' }}>
        鲸鱼职位检索助手
      </div>
    </div>
  );
}
