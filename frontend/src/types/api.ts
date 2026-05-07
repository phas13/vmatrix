export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  perPage: number
  pages: number
}

export interface ApiError {
  detail: string
  type?: string
  status?: number
}

export interface HealthResponse {
  status: string
  db: string
}

export interface TokenResponse {
  accessToken: string
  refreshToken: string
  tokenType: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface SubmitAnswerResponse {
  id: string
  sessionId: string
  questionId: string
  createdAt: string
  updatedAt: string
}

export interface EvaluateSessionResponse {
  sessionId: string
  status: 'COMPLETED' | 'EVALUATION_PENDING'
  finalScore: number
  previousScore: number | null
  levelPercentage: number
}
