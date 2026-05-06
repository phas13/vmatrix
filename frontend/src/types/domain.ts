export type UserRole = 'admin' | 'specialist' | 'cm' | 'hr'

export type SpecialistLevel = 'junior' | 'middle' | 'senior'

export interface User {
  id: string
  email: string
  fullName: string
  role: UserRole
  specialistLevel: SpecialistLevel | null
  cmId: string | null
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface CompetencyCategory {
  id: string
  name: string
  description: string
}

export interface CompetencyItem {
  id: string
  categoryId: string
  title: string
  description: string
  level: number
}

export interface CompetencyMatrix {
  id: string
  specialistId: string
  items: CompetencyItem[]
  status: string
  createdAt: string
  updatedAt: string
}

export interface AssessmentSession {
  id: string
  specialistId: string
  categoryId: string
  status: 'IN_PROGRESS' | 'EVALUATION_PENDING' | 'COMPLETED' | 'ABANDONED'
  responses: AssessmentResponse[]
  createdAt: string
  updatedAt: string
}

export interface AssessmentQuestion {
  id: string
  sessionId: string
  text: string
  questionType: 'theoretical' | 'practical'
  order: number
  createdAt: string
  updatedAt: string
}

export interface AssessmentResponse {
  id: string
  sessionId: string
  questionId: string
  response_text: string
  createdAt: string
  updatedAt: string
}
