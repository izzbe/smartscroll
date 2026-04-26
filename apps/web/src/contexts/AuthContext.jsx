import { createContext, useContext, useEffect, useState } from 'react'
import { onAuthStateChanged } from 'firebase/auth'
import { auth } from '../firebase'
import { upsertMe } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(undefined) // undefined = loading, null = logged out

  useEffect(() => {
    return onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        // Ensure Firestore profile exists on every login
        try {
          await upsertMe(firebaseUser.email, firebaseUser.displayName || '')
        } catch (_) {
          // Non-fatal: profile upsert fails if backend is unreachable
        }
      }
      setUser(firebaseUser)
    })
  }, [])

  return <AuthContext.Provider value={user}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
