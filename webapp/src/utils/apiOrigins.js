const LOCAL_API_ORIGIN = import.meta.env.VITE_LOCAL_API_ORIGIN || 'http://127.0.0.1:5003';
const CLOUD_API_ORIGIN = import.meta.env.VITE_CLOUD_API_ORIGIN || 'http://192.168.31.71:5002';

export const LOCAL_API_BASE = `${LOCAL_API_ORIGIN}/api`;
export const CLOUD_API_BASE = `${CLOUD_API_ORIGIN}/api`;
export const DIRECT_UPLOAD_SIGNED_URL = String(import.meta.env.VITE_DIRECT_UPLOAD_SIGNED_URL || 'false').toLowerCase() === 'true';

export { LOCAL_API_ORIGIN, CLOUD_API_ORIGIN };
