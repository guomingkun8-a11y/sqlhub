import { request } from '@/utils/request'
export const AuthApi = {
  login: (credentials: { username: string; password: string }) => {
    const entryCredentials = {
      username: LicenseGenerator.sqlbotEncrypt(credentials.username),
      password: LicenseGenerator.sqlbotEncrypt(credentials.password),
    }
    return request.post<{
      data: any
      token: string
    }>('/login/access-token', entryCredentials, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })
  },
  changePwd: (data: { account: string; pwd: string; new_pwd: string }) => {
    const entry = {
      account: LicenseGenerator.sqlbotEncrypt(data.account),
      pwd: LicenseGenerator.sqlbotEncrypt(data.pwd),
      new_pwd: LicenseGenerator.sqlbotEncrypt(data.new_pwd),
    }
    return request.post('/login/change-pwd', entry)
  },
  register: (data: { username: string; password: string; name: string; email?: string }) => {
    const entry = {
      username: LicenseGenerator.sqlbotEncrypt(data.username),
      password: LicenseGenerator.sqlbotEncrypt(data.password),
      name: data.name,
      email: data.email || '',
    }
    return request.post<{ access_token: string; need_change_pwd: boolean }>(
      '/login/register',
      entry
    )
  },
  registerStatus: () =>
    request.get<{ enabled: boolean; pwd_pattern: string; pwd_hint: string }>(
      '/login/register-status',
      { requestOptions: { silent: true } }
    ),
  logout: (data: any) => request.post('/login/logout', data),
  info: () => request.get('/user/info'),
}
