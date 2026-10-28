export function getToken() {
  return localStorage.getItem('sijia-token') || '';
}

export function setToken(token) {
  localStorage.setItem('sijia-token', token);
}

export function clearToken() {
  localStorage.removeItem('sijia-token');
}

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers['Content-Type'] = 'application/json';
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && path !== '/api/login') {
    clearToken();
    const redirect = encodeURIComponent(`${window.location.pathname}${window.location.search}`);
    window.location.href = `/user/login?redirect=${redirect}`;
    throw new Error('请先登录');
  }
  return response.json();
}
