import { useEffect, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { getLabBySlug } from '../api/client'
import type { Lab } from '../types'

export default function LabDetail() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [lab, setLab] = useState<Lab | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'theory' | 'objectives' | 'instructions'>(
    'theory',
  )

  useEffect(() => {
    if (!slug) return
    getLabBySlug(slug)
      .then(setLab)
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : 'Failed to load lab'),
      )
      .finally(() => setLoading(false))
  }, [slug])

  if (loading) return <div className="page"><p className="status-msg">Loading…</p></div>
  if (error) return <div className="page"><p className="status-msg error">{error}</p></div>
  if (!lab) return null

  return (
    <div className="page">
      <header className="page-header">
        <div className="breadcrumb">
          <Link to="/">← Back to Labs</Link>
        </div>
        <h1>{lab.title}</h1>
        <div className="lab-meta">
          <span className="lab-category">{lab.category}</span>
          <span className="lab-difficulty">{lab.difficulty}</span>
          <span>⏱ {lab.estimated_minutes} min</span>
        </div>
        <p className="subtitle">{lab.description}</p>
      </header>

      <main className="content">
        <div className="tab-bar">
          {(['theory', 'objectives', 'instructions'] as const).map((tab) => (
            <button
              key={tab}
              className={`tab-btn${activeTab === tab ? ' active' : ''}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        <div className="tab-content">
          {activeTab === 'theory' && (
            <div className="prose">
              <pre className="theory-text">{lab.theory_content}</pre>
            </div>
          )}

          {activeTab === 'objectives' && (
            <ul className="objectives-list">
              {lab.objectives.map((obj, i) => (
                <li key={i} className="objective-item">
                  <span className="objective-num">{i + 1}</span>
                  {obj}
                </li>
              ))}
            </ul>
          )}

          {activeTab === 'instructions' && (
            <ol className="instructions-list">
              {lab.instructions.map((step) => (
                <li key={step.step} className="instruction-item">
                  <h3>{step.title}</h3>
                  <p>{step.content}</p>
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="action-bar">
          <button
            className="btn btn-primary"
            onClick={() => navigate(`/labs/${slug}/editor`)}
          >
            Open Topology Editor →
          </button>
        </div>
      </main>
    </div>
  )
}
