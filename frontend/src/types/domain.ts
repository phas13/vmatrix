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

export interface SessionDispute {
  id: string
  sessionId: string
  status: 'open' | 'resolved'
  specialistExplanation: string
  submittedAt: string
  cmDecision: string | null
  cmNote: string | null
  resolvedAt: string | null
  cmId: string | null
  createdAt: string
  updatedAt: string
}

export interface AssessmentSession {
  id: string
  specialistId: string
  categoryId: string
  categoryName: string | null
  status: 'IN_PROGRESS' | 'EVALUATION_PENDING' | 'COMPLETED' | 'ABANDONED'
  finalScore: number | null
  previousScore: number | null
  levelPercentage: number
  strengths: string | null
  areasForGrowth: string | null
  questions: AssessmentQuestion[]
  responses: AssessmentResponse[]
  dispute: SessionDispute | null
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
  responseText: string
  aiRationale: string | null
  createdAt: string
  updatedAt: string
}

export interface CategoryScore {
  categoryId: string
  categoryName: string
  score: number | null
  previousScore: number | null
  lastAssessedAt: string | null
}

export interface SpecialistDashboard {
  specialistLevel: SpecialistLevel | null
  overallPercentage: number
  categoryScores: CategoryScore[]
}

export type SessionListItemStatus =
  | 'in_progress'
  | 'evaluation_pending'
  | 'completed'
  | 'abandoned'

export interface SessionListItem {
  id: string
  categoryId: string
  categoryName: string | null
  status: SessionListItemStatus
  finalScore: number | null
  previousScore: number | null
  createdAt: string
  updatedAt: string
  dispute: SessionDispute | null
}
