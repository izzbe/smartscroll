import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'

const apiKey = import.meta.env.VITE_FIREBASE_API_KEY
const authDomain = import.meta.env.VITE_FIREBASE_AUTH_DOMAIN
const projectId = import.meta.env.VITE_FIREBASE_PROJECT_ID

if (!apiKey || !projectId) {
  console.error(
    '[SmartScroll] Firebase is not configured.\n' +
    'Create apps/web/.env with:\n' +
    '  VITE_FIREBASE_API_KEY=...\n' +
    '  VITE_FIREBASE_AUTH_DOMAIN=...\n' +
    '  VITE_FIREBASE_PROJECT_ID=...'
  )
}

export const firebaseApp = initializeApp({ apiKey, authDomain, projectId })
export const auth = getAuth(firebaseApp)
