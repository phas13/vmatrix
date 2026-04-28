import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import type { InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { toCamelCase, transformKeys, apiClient } from '../../src/api/client';

describe('toCamelCase', () => {
  it('converts snake_case to camelCase', () => {
    expect(toCamelCase('full_name')).toBe('fullName');
    expect(toCamelCase('created_at')).toBe('createdAt');
    expect(toCamelCase('access_token')).toBe('accessToken');
    expect(toCamelCase('is_active')).toBe('isActive');
  });

  it('leaves already camelCase strings unchanged', () => {
    expect(toCamelCase('fullName')).toBe('fullName');
    expect(toCamelCase('id')).toBe('id');
  });
});

describe('transformKeys', () => {
  it('recursively converts snake_case keys to camelCase', () => {
    const input = { full_name: 'Alice', created_at: '2024-01-01' };
    expect(transformKeys(input)).toEqual({ fullName: 'Alice', createdAt: '2024-01-01' });
  });

  it('handles nested objects', () => {
    const input = { user_data: { first_name: 'Bob', last_name: 'Smith' } };
    expect(transformKeys(input)).toEqual({ userData: { firstName: 'Bob', lastName: 'Smith' } });
  });

  it('handles arrays of objects', () => {
    const input = [{ access_token: 'abc' }, { refresh_token: 'xyz' }];
    expect(transformKeys(input)).toEqual([{ accessToken: 'abc' }, { refreshToken: 'xyz' }]);
  });

  it('passes through primitives unchanged', () => {
    expect(transformKeys('string')).toBe('string');
    expect(transformKeys(42)).toBe(42);
    expect(transformKeys(null)).toBeNull();
    expect(transformKeys(true)).toBe(true);
  });
});

// Simulates the settle() behavior that built-in axios adapters (xhr/http/fetch) perform.
// Custom adapter functions don't call settle() automatically — they must throw AxiosError
// for non-2xx responses, exactly as the built-in adapters do.
function makeAdapter(status: number, data: unknown = null) {
  return async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
    const response: AxiosResponse = {
      status,
      statusText: String(status),
      data,
      headers: {},
      config,
      request: null,
    };
    const validateStatus = config.validateStatus;
    if (!validateStatus || !validateStatus(status)) {
      throw new axios.AxiosError(
        `Request failed with status code ${status}`,
        String(status >= 500 ? axios.AxiosError.ERR_BAD_RESPONSE : axios.AxiosError.ERR_BAD_REQUEST),
        config,
        null,
        response,
      );
    }
    return response;
  };
}

describe('apiClient interceptors', () => {
  let locationHref = 'http://localhost/';

  beforeEach(() => {
    locationHref = 'http://localhost/';
    vi.stubGlobal('location', {
      get href() { return locationHref; },
      set href(v: string) { locationHref = v; },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('response interceptor converts snake_case keys to camelCase', async () => {
    const response = await apiClient.get('/test', {
      adapter: makeAdapter(200, { full_name: 'Alice', created_at: '2024-01-01' }),
    });
    expect(response.data).toEqual({ fullName: 'Alice', createdAt: '2024-01-01' });
  });

  it('403 response sets window.location.href to /login', async () => {
    try {
      await apiClient.get('/protected', { adapter: makeAdapter(403) });
    } catch {
      // expected rejection
    }
    expect(locationHref).toBe('/login');
  });

  it('401 response triggers token refresh and retries the original request', async () => {
    let callCount = 0;
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ data: {} } as never);

    const adapter = async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
      callCount++;
      if (callCount === 1) {
        // first call — 401 triggers interceptor
        const resp: AxiosResponse = { status: 401, statusText: 'Unauthorized', data: {}, headers: {}, config, request: null };
        throw new axios.AxiosError('Unauthorized', axios.AxiosError.ERR_BAD_REQUEST, config, null, resp);
      }
      // retry call — 200
      return { status: 200, statusText: 'OK', data: { result: 'ok' }, headers: {}, config, request: null };
    };

    const response = await apiClient.get('/secure', { adapter });
    expect(postSpy).toHaveBeenCalledWith('/auth/refresh');
    expect(response.data).toEqual({ result: 'ok' });

    postSpy.mockRestore();
  });
});
