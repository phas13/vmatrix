import { apiClient } from './client';
import type { User } from '../types/domain';
import type { LoginRequest, TokenResponse } from '../types/api';

export async function refreshToken(): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/auth/refresh');
  return response.data;
}

export async function loginUser(email: string, password: string): Promise<TokenResponse> {
  const payload: LoginRequest = { email, password };
  const response = await apiClient.post<TokenResponse>('/auth/login', payload);
  return response.data;
}

export async function logoutUser(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function getMe(): Promise<User> {
  const response = await apiClient.get<User>('/users/me');
  return response.data;
}
