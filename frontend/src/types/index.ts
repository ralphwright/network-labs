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
  topology_data: Record<string, unknown>
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

export interface Simulation {
  id: string
  topology_id: string
  lab_id: string
  user_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  results: SimulationResults | null
  verification_results: VerificationResults | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface SimulationResults {
  [key: string]: unknown
}

export interface VerificationResults {
  passed: boolean
  score: number
  checks: VerificationCheck[]
}

export interface VerificationCheck {
  rule_id: string
  passed: boolean
  message: string
}

export interface Progress {
  id: string
  user_id: string
  lab_id: string
  status: 'not_started' | 'in_progress' | 'completed'
  current_step: number
  objectives_completed: string[]
  score: number
  attempts: number
  best_score: number
  time_spent_seconds: number
  completed_at: string | null
  updated_at: string
}
