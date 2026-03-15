export interface Lab {
  id: string
  slug: string
  title: string
  description: string
  category: string
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  estimated_minutes: number
  objectives: string[]
  theory_content: string
  instructions: Instruction[]
  initial_topology: InitialTopology
  verification_rules: VerificationRule[]
  prerequisites: string[]
  sort_order: number
  created_at: string
}

export interface LabSummary {
  id: string
  slug: string
  title: string
  description: string
  category: string
  difficulty: string
  estimated_minutes: number
  prerequisites: string[]
  sort_order: number
}

export interface Instruction {
  step: number
  title: string
  content: string
}

export interface InitialTopology {
  devices?: DeviceInit[]
  connections?: ConnectionInit[]
}

export interface DeviceInit {
  id?: string
  device_type: string
  label: string
  x: number
  y: number
  configuration?: Record<string, unknown>
}

export interface ConnectionInit {
  source_device_id: string
  target_device_id: string
  source_interface: string
  target_interface: string
  link_type?: string
}

export interface VerificationRule {
  id: string
  type: string
  description: string
  params: Record<string, unknown>
}

export interface Topology {
  id: string
  user_id: string
  lab_id: string
  name: string
  description: string | null
  is_template: boolean
  devices: Device[]
  connections: Connection[]
  created_at: string
  updated_at: string
}

export interface Device {
  id: string
  topology_id: string
  device_type: string
  label: string
  x: number
  y: number
  configuration: Record<string, unknown>
  created_at: string
}

export interface Connection {
  id: string
  topology_id: string
  source_device_id: string
  target_device_id: string
  source_interface: string
  target_interface: string
  link_type: string
  bandwidth_mbps: number | null
  configuration: Record<string, unknown>
  created_at: string
}

export interface SimulationCheck {
  passed: boolean
  message: string
}

export interface Simulation {
  id: string
  topology_id: string
  lab_id: string
  user_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  configuration: Record<string, unknown> | null
  results: Record<string, unknown> | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface Progress {
  id: string
  user_id: string
  lab_id: string
  status: 'not_started' | 'in_progress' | 'completed'
  score: number
  attempts: number
  last_simulation_id: string | null
  completed_at: string | null
  updated_at: string
}
