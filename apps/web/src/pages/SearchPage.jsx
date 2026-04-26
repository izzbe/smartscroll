import { useEffect, useState } from 'react'
import { signOut } from 'firebase/auth'
import { auth } from '../firebase'
import { useAuth } from '../contexts/AuthContext'
import { listUsers, followUser, unfollowUser } from '../api/client'
import SmartFeed from '../components/SmartFeed'
import './SearchPage.css'

export default function SearchPage() {
  const currentUser = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [profileUid, setProfileUid] = useState(null) // uid of user whose profile is open

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
      setUsers(users) // revert
      setError(err.message)
    }
  }

  const profileUser = users.find(u => u.uid === profileUid)

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
          <span className="search-me-email">{currentUser.displayName || currentUser.email}</span>
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
              <button
                className="search-user-clickable"
                onClick={() => setProfileUid(user.uid)}
              >
                <div className="search-user-avatar">
                  {(user.display_name || user.email)[0].toUpperCase()}
                </div>
                <div className="search-user-info">
                  <span className="search-user-name">
                    {user.display_name || user.email.split('@')[0]}
                  </span>
                  <span className="search-user-email">{user.email}</span>
                </div>
              </button>
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

      {/* Profile overlay */}
      {profileUid && (
        <div className="search-profile-overlay">
          <div className="search-profile-header">
            <button className="search-profile-back" onClick={() => setProfileUid(null)}>
              <BackIcon />
            </button>
            <div className="search-profile-title">
              <div className="search-profile-avatar">
                {profileUser ? (profileUser.display_name || profileUser.email)[0].toUpperCase() : '?'}
              </div>
              <span>{profileUser?.display_name || profileUser?.email?.split('@')[0]}</span>
            </div>
          </div>
          <div className="search-profile-feed">
            <SmartFeed creatorUid={profileUid} />
          </div>
        </div>
      )}
    </div>
  )
}

function BackIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 5l-7 7 7 7" />
    </svg>
  )
}
