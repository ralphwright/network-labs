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
  updateDevice,
} from '../api/client'
import type { Lab, Topology, Device, Connection, Simulation, SimulationObjective } from '../types'

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

const DIFFICULTY_COLORS: Record<string, string> = {
  beginner: '#22c55e',
  intermediate: '#f59e0b',
  advanced: '#ef4444',
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

  // Selected device for config panel
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null)
  // Device configurations keyed by device label
  const [deviceConfigs, setDeviceConfigs] = useState<Record<string, Record<string, unknown>>>({})
  // Per-device JSON editor text (may be invalid JSON temporarily)
  const [configDraft, setConfigDraft] = useState<string>('')
  const [configSaving, setConfigSaving] = useState(false)
  const [configError, setConfigError] = useState<string | null>(null)

  // Collapsible sidebar sections
  const [showObjectives, setShowObjectives] = useState(true)
  const [showInstructions, setShowInstructions] = useState(true)
  const [showTheory, setShowTheory] = useState(false)

  const loadTopologyData = useCallback(async (topo: Topology) => {
    const [devs, conns] = await Promise.all([
      getDevices(topo.id),
      getConnections(topo.id),
    ])
    setDevices(devs)
    setConnections(conns)
    // Seed deviceConfigs from each device's stored configuration
    const configs: Record<string, Record<string, unknown>> = {}
    for (const d of devs) {
      if (d.configuration && Object.keys(d.configuration).length > 0) {
        configs[d.label] = d.configuration
      }
    }
    setDeviceConfigs(configs)
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

  // When a device is selected, populate the config draft textarea
  useEffect(() => {
    if (!selectedDeviceId) {
      setConfigDraft('')
      setConfigError(null)
      return
    }
    const device = devices.find((d) => d.id === selectedDeviceId)
    if (!device) return
    const existing = deviceConfigs[device.label] ?? device.configuration ?? {}
    setConfigDraft(JSON.stringify(existing, null, 2))
    setConfigError(null)
  }, [selectedDeviceId, devices, deviceConfigs])

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

  const handleDeviceClick = (deviceId: string) => {
    // Ignore click events that fire at the end of a drag operation
    if (dragging) return
    setSelectedDeviceId((prev) => (prev === deviceId ? null : deviceId))
  }

  const handleSaveConfig = async () => {
    if (!selectedDeviceId) return
    const device = devices.find((d) => d.id === selectedDeviceId)
    if (!device) return
    let parsed: Record<string, unknown>
    try {
      parsed = JSON.parse(configDraft) as Record<string, unknown>
    } catch (parseErr) {
      setConfigError(`Invalid JSON: ${parseErr instanceof Error ? parseErr.message : String(parseErr)}`)
      return
    }
    setConfigSaving(true)
    setConfigError(null)
    try {
      const updated = await updateDevice(device.id, { configuration: parsed })
      setDevices((prev) => prev.map((d) => (d.id === device.id ? updated : d)))
      setDeviceConfigs((prev) => ({ ...prev, [device.label]: parsed }))
    } catch (err) {
      setConfigError(err instanceof Error ? err.message : 'Failed to save config')
    } finally {
      setConfigSaving(false)
    }
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
        configuration: deviceConfigs,
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
  const selectedDevice = devices.find((d) => d.id === selectedDeviceId) ?? null

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
                onClick={() => handleDeviceClick(device.id)}
                style={{ cursor: 'grab' }}
              >
                <rect
                  width={60}
                  height={60}
                  rx={8}
                  className={`device-rect device-${device.device_type}`}
                  style={selectedDeviceId === device.id ? { stroke: '#f59e0b', strokeWidth: 2.5 } : undefined}
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

          {/* Device Config Panel — overlays bottom of canvas */}
          {selectedDevice && (
            <div className="device-config-panel">
              <div className="device-config-header">
                <span>{DEVICE_ICONS[selectedDevice.device_type] ?? '📦'} {selectedDevice.label}</span>
                <span className="device-type-badge">{selectedDevice.device_type}</span>
                <button
                  className="config-close-btn"
                  onClick={() => setSelectedDeviceId(null)}
                  title="Close"
                >✕</button>
              </div>
              <p className="config-hint">
                Enter device configuration as JSON (VLANs, IPs, interfaces, routing, etc.)
              </p>
              <textarea
                className="config-textarea"
                value={configDraft}
                onChange={(e) => setConfigDraft(e.target.value)}
                rows={8}
                spellCheck={false}
              />
              {configError && <p className="config-error">{configError}</p>}
              <div className="config-actions">
                <button
                  className="btn btn-primary"
                  onClick={handleSaveConfig}
                  disabled={configSaving}
                >
                  {configSaving ? 'Saving…' : 'Save Config'}
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => setSelectedDeviceId(null)}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <aside className="editor-sidebar">
          {/* Objectives */}
          {lab?.objectives && lab.objectives.length > 0 && (
            <section className="sidebar-section">
              <button
                className="sidebar-section-toggle"
                onClick={() => setShowObjectives((v) => !v)}
              >
                <h3>🎯 Objectives</h3>
                <span>{showObjectives ? '▲' : '▼'}</span>
              </button>
              {showObjectives && (
                <ul className="sidebar-objectives-list">
                  {lab.objectives.map((obj, i) => (
                    <li key={i} className="sidebar-objective-item">
                      <span className="sidebar-objective-num">{i + 1}</span>
                      <span>{obj}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* Instructions */}
          {lab?.instructions && lab.instructions.length > 0 && (
            <section className="sidebar-section">
              <button
                className="sidebar-section-toggle"
                onClick={() => setShowInstructions((v) => !v)}
              >
                <h3>📋 Instructions</h3>
                <span>{showInstructions ? '▲' : '▼'}</span>
              </button>
              {showInstructions && (
                <ol className="sidebar-instructions-list">
                  {lab.instructions.map((instr) => (
                    <li key={instr.step} className="sidebar-instruction-item">
                      <strong>{instr.title}</strong>
                      <p>{instr.description}</p>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          )}

          {/* Theory */}
          {lab?.theory_content && (
            <section className="sidebar-section">
              <button
                className="sidebar-section-toggle"
                onClick={() => setShowTheory((v) => !v)}
              >
                <h3>📖 Theory</h3>
                <span>{showTheory ? '▲' : '▼'}</span>
              </button>
              {showTheory && (
                <p className="sidebar-theory-text">{lab.theory_content}</p>
              )}
            </section>
          )}

          {/* Devices */}
          <section className="sidebar-section">
            <h3>Devices ({devices.length})</h3>
            <ul className="device-list">
              {devices.map((d) => (
                <li
                  key={d.id}
                  className={`device-list-item${selectedDeviceId === d.id ? ' device-list-item--selected' : ''}`}
                  onClick={() => setSelectedDeviceId((prev) => (prev === d.id ? null : d.id))}
                  style={{ cursor: 'pointer' }}
                >
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

          {/* Simulation */}
          <section className="sidebar-section">
            <h3>Simulation</h3>
            {lab && (
              <p className="sim-difficulty" style={{ color: DIFFICULTY_COLORS[lab.difficulty] ?? 'inherit' }}>
                Difficulty: <strong>{lab.difficulty}</strong> · ~{lab.estimated_minutes} min
              </p>
            )}
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
                {simulation.results && (
                  <>
                    {simulation.results.score !== undefined && (
                      <p>
                        <strong>Score:</strong>{' '}
                        {simulation.results.score as number}
                      </p>
                    )}
                    {simulation.results.success !== undefined && (
                      <p>
                        <strong>Passed:</strong>{' '}
                        {simulation.results.success ? '✅ Yes' : '❌ No'}
                      </p>
                    )}
                    {Array.isArray(simulation.results.objectives) &&
                      (simulation.results.objectives as SimulationObjective[]).map((obj, i) => (
                        <div key={i} className="check-item">
                          {obj.passed ? '✅' : '❌'} {obj.description}
                          {obj.message && obj.message.trim().toLowerCase() !== obj.description.trim().toLowerCase() && (
                            <span className="check-detail"> — {obj.message}</span>
                          )}
                        </div>
                      ))}
                    {Array.isArray(simulation.results.errors) &&
                      (simulation.results.errors as string[]).length > 0 && (
                        <div className="sim-errors">
                          {(simulation.results.errors as string[]).map((e, i) => (
                            <div key={i} className="check-item check-item--error">⚠ {e}</div>
                          ))}
                        </div>
                      )}
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
