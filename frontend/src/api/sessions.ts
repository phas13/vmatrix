import { apiClient, transformKeys, readCsrfCookie } from './client'
import type { AssessmentSession, AssessmentQuestion } from '../types/domain'
import type { SubmitAnswerResponse } from '../types/api'

export interface SessionStreamResult {
  sessionId: string
  categoryName: string
  level: string
  totalQuestions: number
  questions: AssessmentQuestion[]
}

export async function createSessionStream(
  categoryId: string,
  onQuestion?: (q: AssessmentQuestion, index: number, total: number) => void,
): Promise<SessionStreamResult> {
  const csrfToken = readCsrfCookie()
  const response = await fetch('/api/v1/sessions', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
    },
    body: JSON.stringify({ category_id: categoryId }),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw Object.assign(new Error('Session creation failed'), { response, data: err })
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let sessionId = ''
  let categoryName = ''
  let level = ''
  let totalQuestions = 0
  const questions: AssessmentQuestion[] = []

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = JSON.parse(line.slice(6)) as Record<string, unknown>
      const event = transformKeys(raw) as Record<string, unknown>
      if (event['type'] === 'session') {
        sessionId = event['sessionId'] as string
        categoryName = event['categoryName'] as string
        level = event['level'] as string
        totalQuestions = event['totalQuestions'] as number
      } else if (event['type'] === 'question') {
        const q = event as unknown as AssessmentQuestion
        questions.push(q)
        onQuestion?.(q, questions.length - 1, totalQuestions)
      }
    }
  }

  return { sessionId, categoryName, level, totalQuestions, questions }
}

export async function getSession(sessionId: string): Promise<AssessmentSession & { questions: AssessmentQuestion[] }> {
  const res = await apiClient.get<AssessmentSession & { questions: AssessmentQuestion[] }>(
    `/sessions/${sessionId}`
  )
  return res.data
}

export interface SubmitAnswerPayload {
  question_id: string
  response_text: string
}

export async function submitAnswer(
  sessionId: string,
  payload: SubmitAnswerPayload,
): Promise<SubmitAnswerResponse> {
  const res = await apiClient.post<SubmitAnswerResponse>(
    `/sessions/${sessionId}/actions/submit-answer`,
    payload,
  )
  return res.data
}
