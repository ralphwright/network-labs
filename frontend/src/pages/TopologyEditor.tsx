import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  getLabBySlug,
  getTopologies,
  createTopology,
  getDevices,
  getConnections,
  createSimulation,
  getSimulation,
} from '../api/client'
import type { Lab, Topology, Device, Connection, Simulation } from '../types'

const DEVICE_ICONS: Record<string, string> = {
  router: '🔷',
  switch: '🔶',
  host: '💻',
  firewall: '🛡️',
  server: '🖥️',
}

interface Position {
  x: number
  y: number
}

export default function TopologyEditor() {
  const { slug } = useParams<{ slug: string }>()
  const [lab, setLab] = useState<Lab | null>(null)
  const [topology, setTopology] = useState<Topology | null>(null)
  const [devices, setDevices] = useState<Device[]>([])
  const [connections, setConnections] = useState<Connection[]>([])
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [simRunning, setSimRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [dragging, setDragging] = useState<string | null>(null)
  const [dragOffset, setDragOffset] = useState<Position>({ x: 0, y: 0 })
  const canvasRef = useRef<SVGSVGElement>(null)

  const loadTopologyData = useCallback(async (topo: Topology) => {
    const [devs, conns] = await Promise.all([
      getDevices(topo.id),
      getConnections(topo.id),
    ])
    setDevices(devs)
    setConnections(conns)
  }, [])

  useEffect(() => {
    if (!slug) return
    ;(async () => {
      try {
        const labData = await getLabBySlug(slug)
        setLab(labData)

        // Try to fetch existing topologies for this lab
        const topos = await getTopologies(labData.id)
        let topo: Topology
        if (topos.length > 0) {
          topo = topos[0]
        } else {
          // Create a new topology with initial topology data
          topo = await createTopology({
            lab_id: labData.id,
            name: 'My Topology',
            initial_topology: labData.initial_topology,
          })
        }
        setTopology(topo)
        await loadTopologyData(topo)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load topology')
      } finally {
        setLoading(false)
      }
    })()
  }, [slug, loadTopologyData])

  const handleMouseDown = (e: React.MouseEvent, deviceId: string) => {
    e.preventDefault()
    const device = devices.find((d) => d.id === deviceId)
    if (!device || !canvasRef.current) return
    const rect = canvasRef.current.getBoundingClientRect()
    setDragging(deviceId)
    setDragOffset({
      x: e.clientX - rect.left - device.x,
      y: e.clientY - rect.top - device.y,
    })
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragging || !canvasRef.current) return
    const rect = canvasRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left - dragOffset.x
    const y = e.clientY - rect.top - dragOffset.y
    setDevices((prev) =>
      prev.map((d) => (d.id === dragging ? { ...d, x, y } : d)),
    )
  }

  const handleMouseUp = () => {
    setDragging(null)
  }

  const runSimulation = async () => {
    if (!topology || !lab) return
    setSimRunning(true)
    setSimulation(null)
    setError(null)
    try {
      const sim = await createSimulation({
        topology_id: topology.id,
        lab_id: lab.id,
      })
      setSimulation(sim)

      // Poll for completion
      let current = sim
      while (current.status === 'pending' || current.status === 'running') {
        await new Promise((r) => setTimeout(r, 2000))
        current = await getSimulation(sim.id)
        setSimulation(current)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed')
    } finally {
      setSimRunning(false)
    }
  }

  const getDeviceById = (id: string) => devices.find((d) => d.id === id)

  if (loading) return <div className="page"><p className="status-msg">Loading topology…</p></div>
  if (error && !topology) return <div className="page"><p className="status-msg error">{error}</p></div>

  return (
    <div className="page editor-page">
      <header className="page-header editor-header">
        <div className="breadcrumb">
          <Link to="/">← Labs</Link>
          {lab && <> / <Link to={`/labs/${slug}`}>{lab.title}</Link></>}
          <> / Editor</>
        </div>
        <h1>{lab?.title} — Topology Editor</h1>
      </header>

      <div className="editor-layout">
        {/* Canvas */}
        <div className="canvas-container">
          <svg
            ref={canvasRef}
            className="topology-canvas"
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            {/* Connection lines */}
            {connections.map((conn) => {
              const src = getDeviceById(conn.source_device_id)
              const tgt = getDeviceById(conn.target_device_id)
              if (!src || !tgt) return null
              return (
                <g key={conn.id}>
                  <line
                    x1={src.x + 30}
                    y1={src.y + 30}
                    x2={tgt.x + 30}
                    y2={tgt.y + 30}
                    className="conn-line"
                  />
                  <text
                    x={(src.x + tgt.x) / 2 + 30}
                    y={(src.y + tgt.y) / 2 + 30}
                    className="conn-label"
                  >
                    {conn.link_type}
                  </text>
                </g>
              )
            })}

            {/* Device nodes */}
            {devices.map((device) => (
              <g
                key={device.id}
                transform={`translate(${device.x}, ${device.y})`}
                className="device-node"
                onMouseDown={(e) => handleMouseDown(e, device.id)}
                style={{ cursor: 'grab' }}
              >
                <rect
                  width={60}
                  height={60}
                  rx={8}
                  className={`device-rect device-${device.device_type}`}
                />
                <text x={30} y={35} className="device-icon" textAnchor="middle">
                  {DEVICE_ICONS[device.device_type] ?? '📦'}
                </text>
                <text x={30} y={78} className="device-label" textAnchor="middle">
                  {device.label}
                </text>
              </g>
            ))}
          </svg>

          {devices.length === 0 && (
            <div className="canvas-empty">
              No devices in this topology yet.
            </div>
          )}
        </div>

        {/* Sidebar */}
        <aside className="editor-sidebar">
          <section className="sidebar-section">
            <h3>Devices ({devices.length})</h3>
            <ul className="device-list">
              {devices.map((d) => (
                <li key={d.id} className="device-list-item">
                  <span>{DEVICE_ICONS[d.device_type] ?? '📦'}</span>
                  <span>{d.label}</span>
                  <span className="device-type-badge">{d.device_type}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="sidebar-section">
            <h3>Connections ({connections.length})</h3>
            <ul className="device-list">
              {connections.map((c) => {
                const src = getDeviceById(c.source_device_id)
                const tgt = getDeviceById(c.target_device_id)
                return (
                  <li key={c.id} className="device-list-item">
                    <span>{src?.label ?? '?'}</span>
                    <span>↔</span>
                    <span>{tgt?.label ?? '?'}</span>
                  </li>
                )
              })}
            </ul>
          </section>

          <section className="sidebar-section">
            <h3>Simulation</h3>
            <button
              className="btn btn-primary w-full"
              onClick={runSimulation}
              disabled={simRunning || !topology}
            >
              {simRunning ? '⏳ Running…' : '▶ Run Simulation'}
            </button>

            {error && <p className="status-msg error small">{error}</p>}

            {simulation && (
              <div className={`sim-result sim-${simulation.status}`}>
                <p>
                  <strong>Status:</strong> {simulation.status}
                </p>
                {simulation.verification_results && (
                  <>
                    <p>
                      <strong>Score:</strong>{' '}
                      {simulation.verification_results.score}
                    </p>
                    <p>
                      <strong>Passed:</strong>{' '}
                      {simulation.verification_results.passed ? '✅ Yes' : '❌ No'}
                    </p>
                    {simulation.verification_results.checks.map((check, i) => (
                      <div key={i} className="check-item">
                        {check.passed ? '✅' : '❌'} {check.message}
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  )
}
