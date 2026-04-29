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

export async function listUsers(page = 1, perPage = 20): Promise<PaginatedResponse<User>> {
  const response = await apiClient.get<PaginatedResponse<User>>('/admin/users', {
    params: { page, per_page: perPage },
  });
  return response.data;
}

export async function createUser(payload: CreateUserPayload): Promise<User> {
  // Axios interceptor only transforms RESPONSE keys (snake→camel).
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
