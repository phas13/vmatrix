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
  matrixId: string
  status: string
  score: number | null
  createdAt: string
  updatedAt: string
}
