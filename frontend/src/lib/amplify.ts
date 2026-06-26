import { Amplify } from 'aws-amplify'
import { fetchAuthSession } from 'aws-amplify/auth'
import axios from 'axios'

// v2.3: OAuth config added for Google sign-in via Cognito Hosted UI.
// redirectSignIn / redirectSignOut accept multiple URLs - Amplify picks the
// one that matches window.location.origin at runtime, so the same build
// works correctly on CloudFront, GitHub Pages, and the custom domain.
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_USER_POOL_ID,
      userPoolClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID,
      loginWith: {
        oauth: {
          domain: 'applytic-auth.auth.us-east-1.amazoncognito.com',
          scopes: ['email', 'openid', 'profile'],
          redirectSignIn: [
            'https://d3jumje9o63lys.cloudfront.net/auth/callback',
            'https://hardikjp7.com/applytic/auth/callback',
            'https://hardikjp7.github.io/applytic/auth/callback',
          ],
          redirectSignOut: [
            'https://d3jumje9o63lys.cloudfront.net/',
            'https://hardikjp7.com/applytic/',
            'https://hardikjp7.github.io/applytic/',
          ],
          responseType: 'code',
        },
      },
    },
  },
})

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

// Attach Cognito JWT to every request
api.interceptors.request.use(async (config) => {
  const session = await fetchAuthSession()
  const token = session.tokens?.idToken?.toString()
  if (token) config.headers.Authorization = token
  return config
})
