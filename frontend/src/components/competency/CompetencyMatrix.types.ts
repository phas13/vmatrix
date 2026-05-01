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
}

export type CompetencyMatrixVariant = 'specialist' | 'cm-review'

export interface CompetencyMatrixProps {
  categories: CategoryData[]
  variant: CompetencyMatrixVariant
  // Story 3.2 will add: onFlag, onUnflag
}
