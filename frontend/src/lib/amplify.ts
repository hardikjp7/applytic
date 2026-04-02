import { Amplify } from 'aws-amplify'
import { fetchAuthSession } from 'aws-amplify/auth'
import axios from 'axios'

Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_USER_POOL_ID,
      userPoolClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID,
    },
  },
})

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

// attach Cognito JWT to every request
api.interceptors.request.use(async (config) => {
  const session = await fetchAuthSession()
  const token = session.tokens?.idToken?.toString()
  if (token) config.headers.Authorization = token
  return config
})
