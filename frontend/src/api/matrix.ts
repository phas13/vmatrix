import { apiClient } from './client'
import type { MatrixData } from '../components/competency/CompetencyMatrix.types'

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
