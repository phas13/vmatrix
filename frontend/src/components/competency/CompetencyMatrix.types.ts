export interface SubItemData {
  id: string
  categoryId: string
  name: string
  description: string
  order: number
  isFlagged: boolean
  flagNote: string | null
}

export interface CategoryData {
  id: string
  matrixId: string
  name: string
  description: string
  order: number
  subItems: SubItemData[]
}

export interface MatrixData {
  id: string
  specialistId: string
  domain: string
  status: 'PENDING_REVIEW' | 'PENDING_APPROVAL' | 'APPROVED'
  createdAt: string
  updatedAt: string
  categories: CategoryData[]
  approvedById: string | null
  approvedAt: string | null
  cmChanges: Record<string, unknown> | null
}

export type CompetencyMatrixVariant = 'specialist' | 'cm-review'

export interface CompetencyMatrixProps {
  categories: CategoryData[]
  variant: CompetencyMatrixVariant
  // specialist variant
  onFlag?: (subItemId: string, note: string) => void
  onUnflag?: (subItemId: string) => void
  onStartAssessment?: (categoryId: string, categoryName: string) => void
  disabled?: boolean
  // cm-review variant
  onEditSubItem?: (subItemId: string, name: string, description: string) => void
  onRemoveSubItem?: (subItemId: string) => void
  localEdits?: Record<string, { name: string; description: string }>
  localRemovals?: string[]
}
