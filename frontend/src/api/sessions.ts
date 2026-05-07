import { apiClient, transformKeys, readCsrfCookie } from './client'
import type { AssessmentSession, AssessmentQuestion } from '../types/domain'
import type { EvaluateSessionResponse, SubmitAnswerResponse, SubmitDisputeResponse } from '../types/api'

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

  if (!response.body) {
    throw new Error('Response body is empty')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let sessionId = ''
  let categoryName = ''
  let level = ''
  let totalQuestions = 0
  const questions: AssessmentQuestion[] = []
  let isDone = false

  try {
    while (!isDone) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue
        
        try {
          const raw = JSON.parse(trimmed.slice(6)) as Record<string, unknown>
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
          } else if (event['type'] === 'done') {
            isDone = true
            break
          }
        } catch (e) {
          console.warn('Failed to parse SSE event:', e, trimmed)
          // Continue to next line
        }
      }
    }
  } finally {
    reader.releaseLock()
  }

  return { sessionId, categoryName, level, totalQuestions, questions }
}

export async function getSession(sessionId: string): Promise<AssessmentSession> {
  const res = await apiClient.get<AssessmentSession>(`/sessions/${sessionId}`)
  return res.data
}

export async function evaluateSession(sessionId: string): Promise<EvaluateSessionResponse> {
  const csrfToken = readCsrfCookie()
  const res = await apiClient.post<EvaluateSessionResponse>(
    `/sessions/${sessionId}/actions/evaluate`,
    null,
    { headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {} },
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

export async function submitDispute(
  sessionId: string,
  specialistExplanation: string,
): Promise<SubmitDisputeResponse> {
  const csrfToken = readCsrfCookie()
  const res = await apiClient.post<SubmitDisputeResponse>(
    `/sessions/${sessionId}/actions/submit-dispute`,
    { specialist_explanation: specialistExplanation },
    { headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {} },
  )
  return res.data
}
