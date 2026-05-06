import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface SessionState {
  activeSessionId: string | null;
  currentQuestionIndex: number;
  answers: Record<string, string>;
  setActiveSessionId: (id: string) => void;
  setCurrentQuestionIndex: (index: number) => void;
  setAnswer: (questionId: string, text: string) => void;
  reset: () => void;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      activeSessionId: null,
      currentQuestionIndex: 0,
      answers: {},
      setActiveSessionId: (id) => set({ activeSessionId: id }),
      setCurrentQuestionIndex: (index) => set({ currentQuestionIndex: index }),
      setAnswer: (questionId, text) =>
        set((state) => ({ answers: { ...state.answers, [questionId]: text } })),
      reset: () => set({ activeSessionId: null, currentQuestionIndex: 0, answers: {} }),
    }),
    { name: 'vmatrix-session', storage: createJSONStorage(() => sessionStorage) }
  )
);
