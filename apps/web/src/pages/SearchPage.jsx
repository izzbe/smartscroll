import { useEffect, useState } from 'react'
import { signOut } from 'firebase/auth'
import { auth } from '../firebase'
import { useAuth } from '../contexts/AuthContext'
import { listUsers, followUser, unfollowUser } from '../api/client'
import './SearchPage.css'

export default function SearchPage() {
  const currentUser = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    listUsers()
      .then(setUsers)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  async function toggleFollow(user) {
    const optimistic = users.map(u =>
      u.uid === user.uid ? { ...u, is_following: !u.is_following } : u
    )
    setUsers(optimistic)
    try {
      if (user.is_following) {
        await unfollowUser(user.uid)
      } else {
        await followUser(user.uid)
      }
    } catch (err) {
      // Revert on failure
      setUsers(users)
      setError(err.message)
    }
  }

  return (
    <div className="search-page">
      <div className="search-header">
        <h2 className="search-title">Discover People</h2>
        <button className="search-signout" onClick={() => signOut(auth)}>
          Sign out
        </button>
      </div>

      {currentUser && (
        <div className="search-me">
          <span className="search-me-label">Signed in as</span>
          <span className="search-me-email">{currentUser.email}</span>
        </div>
      )}

      {error && <p className="search-error">{error}</p>}

      {loading ? (
        <div className="search-loading">Loading…</div>
      ) : users.length === 0 ? (
        <div className="search-empty">No other users yet.</div>
      ) : (
        <ul className="search-list">
          {users.map(user => (
            <li key={user.uid} className="search-user">
              <div className="search-user-avatar">
                {(user.display_name || user.email)[0].toUpperCase()}
              </div>
              <div className="search-user-info">
                <span className="search-user-name">
                  {user.display_name || user.email.split('@')[0]}
                </span>
                <span className="search-user-email">{user.email}</span>
              </div>
              <button
                className={`search-follow-btn ${user.is_following ? 'search-follow-btn--following' : ''}`}
                onClick={() => toggleFollow(user)}
              >
                {user.is_following ? 'Following' : 'Follow'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
