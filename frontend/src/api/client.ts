import type {
  Lab,
  LabSummary,
  Topology,
  Device,
  Connection,
  Simulation,
  Progress,
} from '../types'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// Labs
export const getLabs = (): Promise<LabSummary[]> =>
  request<LabSummary[]>('/api/labs')

export const getLabBySlug = (slug: string): Promise<Lab> =>
  request<Lab>(`/api/labs/${slug}`)

export const getLabById = (id: string): Promise<Lab> =>
  request<Lab>(`/api/labs/id/${id}`)

// Topologies
export const getTopologies = (labId: string): Promise<Topology[]> =>
  request<Topology[]>(`/api/topologies?lab_id=${labId}`)

export const createTopology = (
  data: Partial<Topology> & { initial_topology?: unknown },
): Promise<Topology> =>
  request<Topology>('/api/topologies', {
    method: 'POST',
    body: JSON.stringify(data),
  })

// Devices
export const getDevices = (topologyId: string): Promise<Device[]> =>
  request<Device[]>(`/api/devices?topology_id=${topologyId}`)

export const createDevice = (data: Partial<Device>): Promise<Device> =>
  request<Device>('/api/devices', { method: 'POST', body: JSON.stringify(data) })

export const updateDevice = (id: string, data: Partial<Device>): Promise<Device> =>
  request<Device>(`/api/devices/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deleteDevice = (id: string): Promise<void> =>
  request<void>(`/api/devices/${id}`, { method: 'DELETE' })

// Connections
export const getConnections = (topologyId: string): Promise<Connection[]> =>
  request<Connection[]>(`/api/connections?topology_id=${topologyId}`)

export const createConnection = (data: Partial<Connection>): Promise<Connection> =>
  request<Connection>('/api/connections', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const updateConnection = (
  id: string,
  data: Partial<Connection>,
): Promise<Connection> =>
  request<Connection>(`/api/connections/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deleteConnection = (id: string): Promise<void> =>
  request<void>(`/api/connections/${id}`, { method: 'DELETE' })

// Simulations
export const createSimulation = (data: {
  topology_id: string
  lab_id: string
  user_id?: string
  configuration?: Record<string, Record<string, unknown>>
}): Promise<Simulation> =>
  request<Simulation>('/api/simulations', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const getSimulation = (id: string): Promise<Simulation> =>
  request<Simulation>(`/api/simulations/${id}`)

// Progress
export const getProgress = (userId: string): Promise<Progress[]> =>
  request<Progress[]>(`/api/progress?user_id=${userId}`)

export const getLabProgress = (labId: string, userId: string): Promise<Progress> =>
  request<Progress>(`/api/progress/${labId}?user_id=${userId}`)

export const createProgress = (data: Partial<Progress>): Promise<Progress> =>
  request<Progress>('/api/progress', { method: 'POST', body: JSON.stringify(data) })

export const updateProgress = (
  labId: string,
  userId: string,
  data: Partial<Progress>,
): Promise<Progress> =>
  request<Progress>(`/api/progress/${labId}?user_id=${userId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
