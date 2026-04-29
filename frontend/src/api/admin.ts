import { apiClient } from './client';
import type { User } from '../types/domain';
import type { PaginatedResponse } from '../types/api';

export interface CreateUserPayload {
  email: string;
  fullName: string;
  role: string;
  password: string;
  specialistLevel?: string;
  cmId?: string;
}

export interface ListUsersParams {
  page?: number;
  perPage?: number;
  role?: string;
  active?: boolean;
}

export async function listUsers(params: ListUsersParams = {}): Promise<PaginatedResponse<User>> {
  const { page = 1, perPage = 20, role, active } = params;
  const query: Record<string, string | number | boolean> = { page, per_page: perPage };
  if (role !== undefined) query.role = role;
  if (active !== undefined) query.active = active;
  const response = await apiClient.get<PaginatedResponse<User>>('/admin/users', {
    params: query,
  });
  return response.data;
}

export async function createUser(payload: CreateUserPayload): Promise<User> {
  // Axios response interceptor only transforms RESPONSE keys (snake→camel).
  // Request body must be sent in snake_case manually.
  const body = {
    email: payload.email,
    full_name: payload.fullName,
    role: payload.role,
    password: payload.password,
    specialist_level: payload.specialistLevel ?? null,
    cm_id: payload.cmId ?? null,
  };
  const response = await apiClient.post<User>('/admin/users', body);
  return response.data;
}
