import FeedCard from './FeedCard'
import { MOCK_FEED } from '../data/mockFeed'
import './SmartFeed.css'

export default function SmartFeed({ onGoUpload }) {
  return (
    <div className="sf-scroll">
      {MOCK_FEED.map((item) => (
        <FeedCard key={item.id} item={item} />
      ))}
    </div>
  )
}
