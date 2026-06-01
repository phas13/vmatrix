import type { PaginatedResponse } from './api'

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

export interface SpecialistCard {
  id: string
  fullName: string
  specialistLevel: SpecialistLevel | null
  overallPercentage: number
  lastActivityAt: string | null
}

export interface SpecialistDetail {
  id: string
  fullName: string
  specialistLevel: SpecialistLevel | null
  overallPercentage: number
  categoryScores: CategoryScore[]
  sessions: PaginatedResponse<SessionListItem>
}

export type PendingActionType = 'dispute' | 'promotion' | 'matrix_approval' | 'update_proposal'

export interface PendingAction {
  id: string
  type: PendingActionType
  specialistId: string
  specialistName: string
  description: string
  date: string
}

export interface PendingActionsData {
  disputes: PendingAction[]
  promotions: PendingAction[]
  matrixApprovals: PendingAction[]
  updateProposals: PendingAction[]
  total: number
}

export type DisputeDecision = 'upheld' | 'overridden'

export interface DisputeTranscriptItem {
  questionId: string
  questionText: string
  questionType: 'theoretical' | 'practical'
  order: number
  responseText: string | null
  aiRationale: string | null
}

export interface DisputeDetailData {
  id: string
  sessionId: string
  specialistId: string
  specialistName: string
  categoryId: string
  categoryName: string | null
  status: 'open' | 'resolved'
  specialistExplanation: string
  submittedAt: string
  cmDecision: string | null
  cmNote: string | null
  aiScore: number | null
  transcript: DisputeTranscriptItem[]
}

export interface ResolveDisputeRequest {
  decision: DisputeDecision
  cmNote?: string
  overrideScore?: number
}

export interface ResolveDisputeResponse {
  id: string
  status: string
  cmDecision: string
  cmNote: string | null
  resolvedAt: string
  updatedScore: number | null
}

export interface PromotionDetailData {
  notificationId: string
  specialistId: string
  specialistName: string
  currentLevel: SpecialistLevel | null
  nextLevel: SpecialistLevel | null
  overallPercentage: number
  threshold: number
  categoryScores: CategoryScore[]
  sessions: PaginatedResponse<SessionListItem>
  isDecided: boolean
  decision: string | null
}

export interface PromotionDecideRequest {
  cmNote?: string
}

export interface PromotionDecideResponse {
  notificationId: string
  decision: string
  newLevel: SpecialistLevel | null
}

export interface MatrixProposalDetail {
  id: string
  proposedChange: string
  sourceName: string
  sourceUrl: string
  sourceDate: string | null
  status: string
  isDecided: boolean
  createdAt: string
}

export interface MatrixProposalDecideResponse {
  proposalId: string
  decision: string
}

export interface CompetencyAreaStat {
  categoryName: string
  avgScore: number
}

export interface HRStats {
  levelDistribution: Record<string, number>    // {"junior": 3, "middle": 5, ...}
  avgProgressPerLevel: Record<string, number>  // {"junior": 42, ...}
  strongestAreas: CompetencyAreaStat[]
  weakestAreas: CompetencyAreaStat[]
}
