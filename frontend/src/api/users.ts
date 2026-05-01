import { apiClient } from './client';

export interface Notification {
  id: string;
  type: string;
  content: string;
  isRead: boolean;
  createdAt: string;
}

export async function getUnreadNotifications(): Promise<Notification[]> {
  const response = await apiClient.get<Notification[]>('/users/me/notifications/unread');
  return response.data;
}
