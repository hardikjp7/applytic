import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getInterviewPrep, generateInterviewPrep, updateInterviewQuestion } from '../lib/api'
import type { InterviewPrep, InterviewQuestion } from '../types'
import toast from 'react-hot-toast'

export const interviewPrepKey = (appId: string) => ['interview-prep', appId] as const

export function useInterviewPrep(appId: string) {
  const qc = useQueryClient()

  const { data: prep, isLoading: loading } = useQuery({
    queryKey: interviewPrepKey(appId),
    queryFn: () => getInterviewPrep(appId),
    enabled: !!appId,
  })

  const generateMutation = useMutation({
    mutationFn: () => generateInterviewPrep(appId),
    onSuccess: (newPrep) => {
      qc.setQueryData<InterviewPrep | null>(interviewPrepKey(appId), newPrep)
      toast.success('Interview questions generated')
    },
    onError: () => toast.error('Failed to generate questions'),
  })

  const updateQuestionMutation = useMutation({
    mutationFn: ({ questionId, data }: { questionId: string; data: Partial<Pick<InterviewQuestion, 'practiced' | 'answer'>> }) =>
      updateInterviewQuestion(appId, questionId, data),
    // Optimistic update so checkbox toggles and answer saves feel instant
    onMutate: async ({ questionId, data }) => {
      await qc.cancelQueries({ queryKey: interviewPrepKey(appId) })
      const previous = qc.getQueryData<InterviewPrep | null>(interviewPrepKey(appId))
      qc.setQueryData<InterviewPrep | null>(interviewPrepKey(appId), prev => {
        if (!prev) return prev
        return {
          ...prev,
          questions: prev.questions.map(q => q.id === questionId ? { ...q, ...data } : q),
        }
      })
      return { previous }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous !== undefined) {
        qc.setQueryData(interviewPrepKey(appId), context.previous)
      }
      toast.error('Failed to save')
    },
  })

  return {
    prep: prep ?? null,
    loading,
    generating: generateMutation.isPending,
    generate: () => generateMutation.mutateAsync(),
    updateQuestion: (questionId: string, data: Partial<Pick<InterviewQuestion, 'practiced' | 'answer'>>) =>
      updateQuestionMutation.mutate({ questionId, data }),
    reload: () => qc.invalidateQueries({ queryKey: interviewPrepKey(appId) }),
  }
}
