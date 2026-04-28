import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface SessionState {
  activeSessionId: string | null;
  currentQuestionIndex: number;
  answers: Record<string, string>;
  setAnswer: (questionId: string, text: string) => void;
  reset: () => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      activeSessionId: null,
      currentQuestionIndex: 0,
      answers: {},
      setAnswer: (questionId: string, text: string) =>
        set((state) => ({ answers: { ...state.answers, [questionId]: text } })),
      reset: () => set({ activeSessionId: null, currentQuestionIndex: 0, answers: {} }),
    }),
    { name: 'vmatrix-session', storage: createJSONStorage(() => sessionStorage) }
  )
);
