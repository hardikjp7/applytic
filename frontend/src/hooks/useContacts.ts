import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getContacts, createContact, deleteContact } from '../lib/api'
import type { Contact } from '../types'
import toast from 'react-hot-toast'

export const contactsKey = (appId: string) => ['contacts', appId] as const

export interface NewContactInput {
  name: string
  email?: string
  linkedinUrl?: string
  role?: string
}

export function useContacts(appId: string) {
  const qc = useQueryClient()

  const { data: contacts = [], isLoading: loading } = useQuery({
    queryKey: contactsKey(appId),
    queryFn: () => getContacts(appId),
    enabled: !!appId,
  })

  const addMutation = useMutation({
    mutationFn: (data: NewContactInput) => createContact(appId, data),
    onSuccess: (contact) => {
      qc.setQueryData<Contact[]>(contactsKey(appId), prev => [...(prev ?? []), contact])
      toast.success('Contact added')
    },
    onError: () => toast.error('Failed to add contact'),
  })

  const removeMutation = useMutation({
    mutationFn: (contactId: string) => deleteContact(appId, contactId),
    onSuccess: (_, contactId) => {
      qc.setQueryData<Contact[]>(contactsKey(appId), prev =>
        prev?.filter(c => c.contactId !== contactId) ?? []
      )
      toast.success('Contact deleted')
    },
    onError: () => toast.error('Failed to delete contact'),
  })

  return {
    contacts,
    loading,
    submitting: addMutation.isPending,
    addContact: (data: NewContactInput) => addMutation.mutateAsync(data),
    removeContact: (contactId: string) => removeMutation.mutate(contactId),
    reload: () => qc.invalidateQueries({ queryKey: contactsKey(appId) }),
  }
}