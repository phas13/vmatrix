import type { DisputeDetailData, PendingActionsData, ResolveDisputeRequest, ResolveDisputeResponse, SpecialistCard, SpecialistDetail } from '../types/domain'
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

export async function getCmPending(): Promise<PendingActionsData> {
  const response = await apiClient.get<PendingActionsData>('/cm/pending')
  return response.data
}

export async function getCmDisputeDetail(disputeId: string): Promise<DisputeDetailData> {
  const response = await apiClient.get<DisputeDetailData>(`/cm/disputes/${disputeId}`)
  return response.data
}

export async function resolveCmDispute(
  disputeId: string,
  data: ResolveDisputeRequest,
): Promise<ResolveDisputeResponse> {
  const response = await apiClient.post<ResolveDisputeResponse>(
    `/cm/disputes/${disputeId}/actions/resolve`,
    {
      decision: data.decision,
      cm_note: data.cmNote ?? null,
      override_score: data.overrideScore ?? null,
    },
  )
  return response.data
}
