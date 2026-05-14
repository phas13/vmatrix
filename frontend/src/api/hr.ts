import type { HRStats } from '../types/domain'
import { apiClient } from './client'

export async function getHrStats(): Promise<HRStats> {
  const response = await apiClient.get<HRStats>('/hr/stats')
  return response.data
}
