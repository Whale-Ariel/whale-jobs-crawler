export function safeRedirect(value) {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return '/welcome';
  return value;
}
