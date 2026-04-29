import axios from 'axios';
import type { AxiosResponse } from 'axios';

export const toCamelCase = (str: string): string =>
  str.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());

export function transformKeys(data: unknown): unknown {
  if (Array.isArray(data)) return data.map(transformKeys);
  if (data !== null && typeof data === 'object') {
    return Object.fromEntries(
      Object.entries(data as Record<string, unknown>).map(([k, v]) => [toCamelCase(k), transformKeys(v)])
    );
  }
  return data;
}

export const apiClient = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

const CSRF_METHODS = new Set(['post', 'put', 'patch', 'delete']);

function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

apiClient.interceptors.request.use((config) => {
  const method = (config.method ?? 'get').toLowerCase();
  if (CSRF_METHODS.has(method)) {
    const token = readCsrfCookie();
    if (token) {
      config.headers = config.headers ?? {};
      (config.headers as Record<string, string>)['X-CSRF-Token'] = token;
    }
  }
  return config;
});

let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    response.data = transformKeys(response.data);
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (originalRequest.url === '/auth/refresh') {
        isRefreshing = false;
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => apiClient(originalRequest))
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        await apiClient.post('/auth/refresh');
        isRefreshing = false;
        processQueue(null, 'refreshed');
        return apiClient(originalRequest);
      } catch (refreshError) {
        isRefreshing = false;
        processQueue(refreshError, null);
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    if (error.response?.status === 403) {
      return Promise.reject(error);
    }

    return Promise.reject(error);
  }
);
