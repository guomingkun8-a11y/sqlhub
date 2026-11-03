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
  listConfigs: () => request.get<RobotConfig[]>('/system/robot/config'),
  saveConfig: (data: {
    platform: string
    app_id?: string
    app_secret?: string
    auto_start: boolean
  }) => request.put<RobotConfig>('/system/robot/config', data),
  listStatus: () => request.get<RobotStatus[]>('/system/robot/status'),
  start: (platform: string) =>
    request.post<RobotStatus>('/system/robot/start', null, { params: { platform } }),
  stop: (platform: string) =>
    request.post<RobotStatus>('/system/robot/stop', null, { params: { platform } }),
}
