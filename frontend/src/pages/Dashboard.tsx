import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getLabs } from '../api/client'
import type { LabSummary } from '../types'

const DIFFICULTY_COLOR: Record<string, string> = {
  beginner: '#22c55e',
  intermediate: '#f59e0b',
  advanced: '#ef4444',
}

export default function Dashboard() {
  const [labs, setLabs] = useState<LabSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getLabs()
      .then(setLabs)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : 'Failed to load labs'),
      )
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page">
      <header className="page-header">
        <h1 className="brand">🌐 Network Labs</h1>
        <p className="subtitle">
          Interactive network topology labs for hands-on learning
        </p>
      </header>

      <main className="content">
        {loading && <p className="status-msg">Loading labs…</p>}
        {error && <p className="status-msg error">{error}</p>}
        {!loading && !error && labs.length === 0 && (
          <p className="status-msg">No labs available yet.</p>
        )}

        <div className="lab-grid">
          {labs
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((lab) => (
              <Link key={lab.id} to={`/labs/${lab.slug}`} className="lab-card">
                <div className="lab-card-header">
                  <span className="lab-category">{lab.category}</span>
                  <span
                    className="lab-difficulty"
                    style={{ color: DIFFICULTY_COLOR[lab.difficulty] ?? '#64748b' }}
                  >
                    {lab.difficulty}
                  </span>
                </div>
                <h2 className="lab-title">{lab.title}</h2>
                <p className="lab-description">{lab.description}</p>
                <div className="lab-meta">
                  <span>⏱ {lab.estimated_minutes} min</span>
                  {lab.prerequisites.length > 0 && (
                    <span>🔗 {lab.prerequisites.length} prerequisite(s)</span>
                  )}
                </div>
              </Link>
            ))}
        </div>
      </main>
    </div>
  )
}
