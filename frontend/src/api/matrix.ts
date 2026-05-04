import { apiClient } from './client'
import type { MatrixData, SubItemData } from '../components/competency/CompetencyMatrix.types'

export async function getMatrix(specialistId: string): Promise<MatrixData> {
  const response = await apiClient.get<MatrixData>(`/matrix/${specialistId}`)
  return response.data
}

export async function generateMatrix(specialistId: string): Promise<MatrixData> {
  const response = await apiClient.post<MatrixData>(
    `/matrix/${specialistId}/actions/generate`
  )
  return response.data
}

export async function flagSubItem(
  specialistId: string,
  subItemId: string,
  note: string | null,
): Promise<SubItemData> {
  const response = await apiClient.post<SubItemData>(
    `/matrix/${specialistId}/sub-items/${subItemId}/actions/flag`,
    { note },
  )
  return response.data
}

export async function unflagSubItem(
  specialistId: string,
  subItemId: string,
): Promise<SubItemData> {
  const response = await apiClient.post<SubItemData>(
    `/matrix/${specialistId}/sub-items/${subItemId}/actions/unflag`,
  )
  return response.data
}

export async function submitMatrix(specialistId: string): Promise<MatrixData> {
  const response = await apiClient.post<MatrixData>(
    `/matrix/${specialistId}/actions/submit`,
  )
  return response.data
}

export interface SubItemEditPayload {
  id: string
  name: string
  description: string
}

export interface MatrixApprovePayload {
  sub_item_edits: SubItemEditPayload[]
  sub_items_to_remove: string[]
}

export async function approveMatrix(
  specialistId: string,
  payload: MatrixApprovePayload,
): Promise<MatrixData> {
  const response = await apiClient.post<MatrixData>(
    `/matrix/${specialistId}/actions/approve`,
    payload,
  )
  return response.data
}
