import { request } from '@/utils/request'

export interface RobotConfig {
  platform: string
  app_id?: string
  app_secret_masked?: string
  configured: boolean
  auto_start: boolean
}

export interface RobotStatus {
  platform: string
  running: boolean
  configured: boolean
  auto_start: boolean
  message: string
}

export const robotApi = {
  getConfig: () => request.get<RobotConfig>('/system/robot/config'),
  saveConfig: (data: {
    platform: string
    app_id?: string
    app_secret?: string
    auto_start: boolean
  }) => request.put<RobotConfig>('/system/robot/config', data),
  start: () => request.post<RobotStatus>('/system/robot/start'),
  stop: () => request.post<RobotStatus>('/system/robot/stop'),
  status: () => request.get<RobotStatus>('/system/robot/status'),
}
