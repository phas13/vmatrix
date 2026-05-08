import { apiClient } from './client';
import type { PaginatedResponse } from '../types/api';
import type { SpecialistDashboard } from '../types/domain';

export interface Notification {
  id: string;
  type: string;
  content: string;
  isRead: boolean;
  createdAt: string;
}

export async function getUnreadNotifications(): Promise<Notification[]> {
  const response = await apiClient.get<PaginatedResponse<Notification>>('/users/me/notifications/unread');
  return response.data.items;
}

export async function markNotificationRead(notificationId: string): Promise<void> {
  await apiClient.post(`/users/me/notifications/${notificationId}/read`);
}

export async function getSpecialistDashboard(): Promise<SpecialistDashboard> {
  const res = await apiClient.get<SpecialistDashboard>('/users/me/dashboard');
  return res.data;
}
