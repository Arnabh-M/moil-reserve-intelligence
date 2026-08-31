import { useParams } from 'react-router-dom'
import PlaceholderPage from './PlaceholderPage'

export default function SiteDetail() {
  const { id } = useParams()
  return (
    <PlaceholderPage
      title={`Site Detail — ${id}`}
      description="Site detail view is under construction."
    />
  )
}
