import type { SpecialistCard, SpecialistDetail } from '../types/domain'
import { apiClient } from './client'

export async function getCmTeam(): Promise<SpecialistCard[]> {
  const response = await apiClient.get<SpecialistCard[]>('/cm/team')
  return response.data
}

export async function getCmSpecialistDetail(
  specialistId: string,
  page = 1,
  perPage = 20,
): Promise<SpecialistDetail> {
  const response = await apiClient.get<SpecialistDetail>(
    `/cm/specialists/${specialistId}`,
    { params: { page, per_page: perPage } },
  )
  return response.data
}
