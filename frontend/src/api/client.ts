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

let isRefreshing = false;

apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    response.data = transformKeys(response.data);
    return response;
  },
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry && !isRefreshing) {
      originalRequest._retry = true;
      isRefreshing = true;
      try {
        await apiClient.post('/auth/refresh');
        isRefreshing = false;
        return apiClient(originalRequest);
      } catch {
        isRefreshing = false;
        window.location.href = '/login';
        return Promise.reject(error);
      }
    }
    if (error.response?.status === 403) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
