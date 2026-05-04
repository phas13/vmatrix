import { apiClient } from './client'

export interface SpecialistSummary {
  id: string
  email: string
  fullName: string
  role: string
  isActive: boolean
  cmId: string | null
}

export async function getCmTeam(): Promise<SpecialistSummary[]> {
  const response = await apiClient.get<SpecialistSummary[]>('/cm/team')
  return response.data
}
