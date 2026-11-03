<template>
  <div class="robot-config no-padding">
    <div class="robot-container">
      <header class="page-head">
        <h1>{{ t('robot.title') }}</h1>
        <p>{{ t('robot.platform_tip') }}</p>
      </header>

      <div v-loading="loading" class="robot-content" :aria-busy="loading">
        <div v-if="configLoadFailed" class="load-notice" role="alert">
          <div>
            <strong>{{ t('robot.load_failed') }}</strong>
            <p>{{ t('robot.load_failed_tip') }}</p>
          </div>
          <el-button :icon="Refresh" :loading="loading" @click="loadConfig">
            {{ t('robot.retry') }}
          </el-button>
        </div>

        <div class="platform-bar">
          <el-radio-group
            v-model="activePlatform"
            class="platform-group"
            :aria-label="t('robot.platform')"
          >
            <el-radio-button v-for="item in platformList" :key="item.value" :value="item.value">
              <span class="platform-option">
                <img :src="item.icon" width="20" height="20" alt="" />
                <span>{{ item.label }}</span>
              </span>
            </el-radio-button>
          </el-radio-group>
          <span class="connection-note">{{ t('robot.connection_note') }}</span>
        </div>

        <div class="setup-grid">
          <section class="robot-card credentials-card" aria-labelledby="credentials-title">
            <div class="card-heading">
              <div>
                <h2 id="credentials-title">{{ t('robot.credentials') }}</h2>
                <p>{{ t('robot.credentials_desc', { platform: currentPlatform.label }) }}</p>
              </div>
              <span v-if="currentConfig.configured" class="saved-badge">
                <el-icon aria-hidden="true"><Check /></el-icon>
                {{ t('robot.configured') }}
              </span>
            </div>

            <el-form
              :key="activePlatform"
              :model="currentForm"
              :disabled="!configLoaded || saving"
              label-position="top"
              class="robot-form"
              @submit.prevent="save"
            >
              <el-form-item
                :label="platformMeta.idLabel"
                :for="`${activePlatform}-app-id`"
                required
              >
                <el-input
                  :id="`${activePlatform}-app-id`"
                  v-model="currentForm.app_id"
                  :placeholder="platformMeta.idPlaceholder"
                  autocomplete="off"
                  clearable
                />
              </el-form-item>
              <el-form-item
                :label="platformMeta.secretLabel"
                :for="`${activePlatform}-app-secret`"
                class="secret-field"
              >
                <el-input
                  :id="`${activePlatform}-app-secret`"
                  v-model="currentForm.app_secret"
                  type="password"
                  show-password
                  autocomplete="new-password"
                  :placeholder="appSecretPlaceholder"
                  :aria-describedby="`${activePlatform}-secret-hint`"
                />
                <p :id="`${activePlatform}-secret-hint`" class="field-hint">
                  {{ t('robot.secret_hint') }}
                </p>
              </el-form-item>

              <div class="auto-start-row">
                <div class="auto-start-copy">
                  <label :for="`${activePlatform}-auto-start`">{{ t('robot.auto_start') }}</label>
                  <p>{{ t('robot.auto_start_desc') }}</p>
                </div>
                <el-switch
                  :id="`${activePlatform}-auto-start`"
                  v-model="currentForm.auto_start"
                  :disabled="currentStatus.running"
                  :aria-label="t('robot.auto_start')"
                />
              </div>

              <div class="card-footer">
                <span>{{ t('robot.save_hint') }}</span>
                <el-button
                  type="primary"
                  native-type="submit"
                  :loading="saving"
                  class="save-button"
                >
                  {{ t('robot.save') }}
                </el-button>
              </div>
            </el-form>
          </section>

          <aside class="robot-card guide-card" aria-labelledby="guide-title">
            <div class="card-heading">
              <div>
                <h2 id="guide-title">{{ t('robot.setup_guide') }}</h2>
                <p>{{ t('robot.setup_guide_desc', { platform: currentPlatform.label }) }}</p>
              </div>
              <a
                class="doc-link"
                :href="platformMeta.doc"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ t('robot.doc_link') }}
                <el-icon aria-hidden="true"><TopRight /></el-icon>
              </a>
            </div>

            <ol class="setup-steps">
              <li v-for="(step, index) in platformMeta.steps" :key="index">
                <span class="step-number" aria-hidden="true">{{ index + 1 }}</span>
                <div class="step-copy">
                  <h3>{{ step.title }}</h3>
                  <p>{{ step.description }}</p>
                </div>
              </li>
            </ol>

            <div class="identity-note">
              <el-icon aria-hidden="true"><InfoFilled /></el-icon>
              <p>{{ t('robot.identity_tip') }}</p>
            </div>
          </aside>
        </div>

        <section class="robot-card runtime-card" aria-labelledby="runtime-title">
          <div class="card-heading">
            <div>
              <h2 id="runtime-title">{{ t('robot.run_status') }}</h2>
              <p>{{ t('robot.status_desc') }}</p>
            </div>
            <el-button
              :icon="Refresh"
              :loading="refreshingStatus"
              :disabled="loading || !!busyPlatform || saving"
              @click="refreshStatus"
            >
              {{ t('common.refresh') }}
            </el-button>
          </div>

          <p v-if="statusLoadFailed" class="status-notice" role="alert">
            {{ t('robot.status_load_failed') }}
          </p>

          <div class="status-grid" aria-live="polite">
            <article v-for="item in platformList" :key="item.value" class="platform-status">
              <div class="status-heading">
                <div class="status-platform">
                  <img :src="item.icon" width="24" height="24" alt="" />
                  <h3>{{ item.label }}</h3>
                </div>
                <span class="status-badge" :class="statusTone(item.value)">
                  <span class="status-dot" aria-hidden="true"></span>
                  {{ statusLabel(item.value) }}
                </span>
              </div>
              <p class="platform-description">{{ item.description }}</p>
              <p class="status-detail" :class="{ 'has-error': hasStatusError(item.value) }">
                {{ statusDescription(item.value) }}
              </p>
              <div class="status-actions">
                <span class="status-config-label">
                  {{
                    statuses[item.value] && !statusLoadFailed
                      ? statuses[item.value]?.configured
                        ? t('robot.configured')
                        : t('robot.awaiting_config')
                      : t('robot.status_unknown')
                  }}
                </span>
                <el-button
                  v-if="!statuses[item.value]?.running || statusLoadFailed"
                  :disabled="
                    !statuses[item.value]?.configured ||
                    statusLoadFailed ||
                    !statuses[item.value] ||
                    !!busyPlatform ||
                    saving ||
                    refreshingStatus
                  "
                  :loading="busyPlatform === item.value"
                  @click="start(item.value)"
                >
                  {{ t('robot.start') }}
                </el-button>
                <el-button
                  v-else
                  :disabled="!!busyPlatform || saving || refreshingStatus"
                  :loading="busyPlatform === item.value"
                  @click="stop(item.value)"
                >
                  {{ t('robot.stop') }}
                </el-button>
              </div>
            </article>
          </div>
          <p class="runtime-footnote">{{ t('robot.runtime_note') }}</p>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus-secondary'
import { Check, InfoFilled, Refresh, TopRight } from '@element-plus/icons-vue'
import { robotApi, type RobotConfig, type RobotStatus } from '@/api/robot'
import feishuIcon from '@/assets/svg/logo_lark.svg?url'
import dingtalkIcon from '@/assets/svg/logo_dingtalk.svg?url'
import wecomIcon from '@/assets/svg/logo_wechat-work.svg?url'

const { t } = useI18n()

type Platform = 'feishu' | 'dingtalk' | 'wecom'
interface RobotForm {
  app_id: string
  app_secret: string
  auto_start: boolean
}

const loading = ref(false)
const saving = ref(false)
const busyPlatform = ref<Platform | ''>('')
const configLoaded = ref(false)
const configLoadFailed = ref(false)
const statusLoadFailed = ref(false)
const refreshingStatus = ref(false)
const activePlatform = ref<Platform>('feishu')

const forms = reactive<Record<Platform, RobotForm>>({
  feishu: { app_id: '', app_secret: '', auto_start: false },
  dingtalk: { app_id: '', app_secret: '', auto_start: false },
  wecom: { app_id: '', app_secret: '', auto_start: false },
})

const configs = reactive<Partial<Record<Platform, RobotConfig>>>({})
const statuses = reactive<Partial<Record<Platform, RobotStatus>>>({})

const platformList = computed(() => [
  {
    value: 'feishu' as const,
    label: t('robot.feishu'),
    icon: feishuIcon,
    description: t('robot.feishu_description'),
  },
  {
    value: 'dingtalk' as const,
    label: t('robot.dingtalk'),
    icon: dingtalkIcon,
    description: t('robot.dingtalk_description'),
  },
  {
    value: 'wecom' as const,
    label: t('robot.wecom'),
    icon: wecomIcon,
    description: t('robot.wecom_description'),
  },
])

const currentPlatform = computed(() =>
  platformList.value.find((item) => item.value === activePlatform.value)!
)
const currentForm = computed(() => forms[activePlatform.value])
const currentConfig = computed<Partial<RobotConfig>>(() => configs[activePlatform.value] || {})
const currentStatus = computed<Partial<RobotStatus>>(() => statuses[activePlatform.value] || {})

const platformMeta = computed(() => {
  const steps = [1, 2, 3].map((step) => ({
    title: t(`robot.${activePlatform.value}_step_${step}_title`),
    description: t(`robot.${activePlatform.value}_step_${step}_desc`),
  }))
  if (activePlatform.value === 'dingtalk') {
    return {
      idLabel: t('robot.client_id'),
      idPlaceholder: t('robot.client_id_placeholder'),
      secretLabel: t('robot.client_secret'),
      secretPlaceholder: t('robot.client_secret_placeholder'),
      doc: 'https://open-dev.dingtalk.com/',
      steps,
    }
  }
  if (activePlatform.value === 'wecom') {
    return {
      idLabel: t('robot.wecom_bot_id'),
      idPlaceholder: t('robot.wecom_bot_id_placeholder'),
      secretLabel: t('robot.wecom_secret'),
      secretPlaceholder: t('robot.wecom_secret_placeholder'),
      doc: 'https://work.weixin.qq.com/wework_admin/frame#/aiBot',
      steps,
    }
  }
  return {
    idLabel: t('robot.app_id'),
    idPlaceholder: t('robot.app_id_placeholder'),
    secretLabel: t('robot.app_secret'),
    secretPlaceholder: t('robot.app_secret_placeholder'),
    doc: 'https://open.feishu.cn/app',
    steps,
  }
})

const appSecretPlaceholder = computed(() =>
  currentConfig.value.configured
    ? t('robot.app_secret_placeholder_saved')
    : platformMeta.value.secretPlaceholder
)

const isPlatform = (value: string): value is Platform =>
  value === 'feishu' || value === 'dingtalk' || value === 'wecom'

const applyConfigs = (list: RobotConfig[], resetPlatform?: Platform) => {
  ;(list || []).forEach((cfg) => {
    if (!isPlatform(cfg.platform)) return
    configs[cfg.platform] = cfg
    // 刷新其他平台的已存配置，不覆盖其尚未保存的表单草稿。
    if (resetPlatform && cfg.platform !== resetPlatform) return
    const form = forms[cfg.platform]
    form.app_id = cfg.app_id || ''
    form.auto_start = !!cfg.auto_start
    // secret 不回填明文，仅显示占位。
    form.app_secret = ''
  })
}

const applyStatuses = (list: RobotStatus[]) => {
  platformList.value.forEach(({ value }) => delete statuses[value])
  ;(list || []).forEach((item) => {
    if (isPlatform(item.platform)) statuses[item.platform] = item
  })
}

const loadStatus = async () => {
  try {
    applyStatuses(await robotApi.listStatus())
    statusLoadFailed.value = false
  } catch {
    statusLoadFailed.value = true
  }
}

const loadConfig = async () => {
  loading.value = true
  configLoadFailed.value = false
  try {
    applyConfigs(await robotApi.listConfigs())
    configLoaded.value = true
  } catch {
    configLoadFailed.value = true
    configLoaded.value = false
  } finally {
    await loadStatus()
    loading.value = false
  }
}

const refreshStatus = async () => {
  if (refreshingStatus.value || busyPlatform.value || saving.value) return
  refreshingStatus.value = true
  try {
    await loadStatus()
  } finally {
    refreshingStatus.value = false
  }
}

const hasStatusError = (platform: Platform) =>
  !statusLoadFailed.value && !!statuses[platform]?.message

const statusTone = (platform: Platform) => {
  const status = statuses[platform]
  if (!status || statusLoadFailed.value) return 'is-unknown'
  if (status.message) return 'is-warning'
  if (status.running) return 'is-running'
  return 'is-stopped'
}

const statusLabel = (platform: Platform) => {
  const status = statuses[platform]
  if (!status || statusLoadFailed.value) return t('robot.status_unknown')
  if (status.message) return t('robot.status_attention')
  return status.running ? t('robot.running') : t('robot.stopped')
}

const statusDescription = (platform: Platform) => {
  const status = statuses[platform]
  if (!status || statusLoadFailed.value) return t('robot.status_unknown_tip')
  if (status.message) return status.message
  if (!status.configured) return t('robot.not_configured')
  return status.running ? t('robot.worker_running_hint') : t('robot.ready_hint')
}

const save = async () => {
  if (!configLoaded.value || saving.value) return
  const platform = activePlatform.value
  const form = forms[platform]
  if (!form.app_id) {
    ElMessage.warning(t('robot.app_id_required'))
    return
  }
  saving.value = true
  try {
    await robotApi.saveConfig({
      platform,
      app_id: form.app_id,
      app_secret: form.app_secret || undefined,
      auto_start: form.auto_start,
    })
    ElMessage.success(t('robot.save_success'))
    form.app_secret = ''
    applyConfigs(await robotApi.listConfigs(), platform)
    await loadStatus()
  } catch {
    // 请求封装统一展示错误，保留未提交成功的输入以便重试。
  } finally {
    saving.value = false
  }
}

const start = async (platform: Platform) => {
  if (busyPlatform.value || statusLoadFailed.value || !statuses[platform]?.configured) return
  busyPlatform.value = platform
  try {
    const res = await robotApi.start(platform)
    if (res.running) {
      ElMessage.success(res.message || t('robot.start_success'))
    } else {
      ElMessage.warning(res.message || t('robot.start_failed'))
    }
  } catch {
    // 请求封装统一展示错误；请求结束后重新读取状态。
  } finally {
    await loadStatus()
    busyPlatform.value = ''
  }
}

const stop = async (platform: Platform) => {
  if (busyPlatform.value || statusLoadFailed.value || !statuses[platform]?.running) return
  busyPlatform.value = platform
  try {
    const res = await robotApi.stop(platform)
    if (res.running) {
      ElMessage.warning(res.message || t('robot.stop_failed'))
    } else {
      ElMessage.success(res.message || t('robot.stop_success'))
    }
  } catch {
    // 请求封装统一展示错误；请求结束后重新读取状态。
  } finally {
    await loadStatus()
    busyPlatform.value = ''
  }
}

onMounted(loadConfig)
</script>

<style lang="less" scoped>
.robot-config {
  --robot-bg: #f8f9fb;
  --robot-surface: #ffffff;
  --robot-text: #171717;
  --robot-secondary: #858b98;
  --robot-body: #626975;
  --robot-border: #e8eaee;
  --robot-accent: #1f2329;

  min-height: 100%;
  padding: 36px 40px 40px;
  background: var(--robot-bg);
  color: var(--robot-text);

  .robot-container {
    width: 100%;
    max-width: 1200px;
    margin: 0 auto;
  }

  h1,
  h2,
  h3,
  p {
    margin: 0;
  }

  .page-head {
    margin-bottom: 28px;

    h1 {
      font-size: 24px;
      font-weight: 600;
      line-height: 1.4;
      letter-spacing: -0.5px;
    }

    p {
      margin-top: 8px;
      color: var(--robot-body);
      font-size: 14px;
      line-height: 1.7;
    }
  }

  .robot-content {
    min-width: 0;
  }

  .platform-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 20px;
  }

  .platform-group {
    display: inline-flex;
    max-width: 100%;
    padding: 4px;
    border: 1px solid var(--robot-border);
    border-radius: 10px;
    background: #eff1f4;

    :deep(.ed-radio-button) {
      min-width: 0;
      flex: 1 1 auto;
    }

    :deep(.ed-radio-button__inner) {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 8px 20px;
      border: 1px solid transparent;
      border-radius: 6px;
      background: transparent;
      box-shadow: none;
      color: var(--robot-body);
      font-size: 14px;
      line-height: 20px;
      letter-spacing: normal;
      white-space: nowrap;
      transition:
        background-color 150ms ease-out,
        color 150ms ease-out;
    }

    :deep(.ed-radio-button:not(.is-active) .ed-radio-button__inner:hover) {
      background: #e8ebef;
      color: var(--robot-text);
    }

    :deep(.ed-radio-button.is-active .ed-radio-button__inner) {
      border-color: #dee1e6;
      background: var(--robot-surface);
      box-shadow: 0 1px 2px #17171706;
      color: var(--robot-text);
      font-weight: 600;
    }

    :deep(.ed-radio-button__original-radio:focus-visible + .ed-radio-button__inner) {
      outline: 2px solid var(--robot-accent);
      outline-offset: -2px;
    }
  }

  .platform-option {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;

    img {
      display: block;
      flex-shrink: 0;
    }
  }

  .connection-note {
    color: var(--robot-secondary);
    font-size: 13px;
    line-height: 20px;
  }

  .setup-grid {
    display: grid;
    grid-template-columns: minmax(0, 58fr) minmax(0, 42fr);
    gap: 20px;
    align-items: stretch;
    margin-bottom: 28px;
  }

  .robot-card {
    min-width: 0;
    padding: 24px;
    border: 1px solid var(--robot-border);
    border-radius: 10px;
    background: var(--robot-surface);
  }

  .card-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 24px;

    > div {
      min-width: 0;
    }

    h2 {
      font-size: 16px;
      font-weight: 600;
      line-height: 24px;
    }

    p {
      margin-top: 4px;
      color: var(--robot-body);
      font-size: 13px;
      line-height: 21px;
    }
  }

  .saved-badge {
    display: inline-flex;
    align-items: center;
    flex-shrink: 0;
    gap: 4px;
    margin-top: 2px;
    color: #48715a;
    font-size: 12px;
    line-height: 20px;

    .ed-icon {
      font-size: 14px;
    }
  }

  .robot-form {
    :deep(.ed-form-item) {
      margin-bottom: 20px;
    }

    :deep(.ed-form-item__label) {
      height: auto;
      margin-bottom: 8px;
      padding: 0;
      color: var(--robot-text);
      font-size: 13px;
      font-weight: 500;
      line-height: 20px;
    }

    :deep(.ed-input) {
      --ed-input-height: 40px;
      --ed-input-border-radius: 6px;
      --ed-input-border-color: #dfe2e8;
      --ed-input-hover-border-color: #aeb4bf;
      --ed-input-focus-border-color: #525b69;
      --ed-input-text-color: var(--robot-text);
      --ed-input-placeholder-color: var(--robot-secondary);
    }

    :deep(.ed-input__wrapper) {
      min-height: 40px;
      padding: 0 12px;
    }

    :deep(.ed-input__inner) {
      height: 40px;
      line-height: 40px;
      font-size: 14px;
    }

    .field-hint {
      margin-top: 8px;
      color: var(--robot-body);
      font-size: 12px;
      line-height: 20px;
    }
  }

  .auto-start-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 20px 0;
    border-top: 1px solid var(--robot-border);

    label {
      font-size: 14px;
      font-weight: 500;
      line-height: 22px;
      cursor: pointer;
    }

    p {
      margin-top: 4px;
      color: var(--robot-body);
      font-size: 12px;
      line-height: 20px;
    }

    :deep(.ed-switch) {
      --ed-switch-on-color: var(--robot-accent);
      flex-shrink: 0;
    }
  }

  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding-top: 20px;
    border-top: 1px solid var(--robot-border);

    > span {
      color: var(--robot-secondary);
      font-size: 12px;
      line-height: 20px;
    }
  }

  :deep(.ed-button) {
    --ed-button-border-color: #dfe2e8;
    --ed-button-hover-border-color: #b8bec8;
    --ed-button-hover-bg-color: #f5f6f8;
    --ed-button-hover-text-color: var(--robot-text);
    --ed-button-text-color: var(--robot-text);
    height: 36px;
    padding: 0 14px;
    border-radius: 6px;
    font-size: 13px;
    transition:
      background-color 150ms ease-out,
      border-color 150ms ease-out;

    &:focus-visible {
      outline: 2px solid #525b69;
      outline-offset: 3px;
    }
  }

  :deep(.ed-button--primary) {
    --ed-button-text-color: #ffffff;
    --ed-button-bg-color: var(--robot-accent);
    --ed-button-border-color: var(--robot-accent);
    --ed-button-hover-bg-color: #363c45;
    --ed-button-hover-border-color: #363c45;
    --ed-button-hover-text-color: #ffffff;
    --ed-button-active-bg-color: #171717;
    --ed-button-active-border-color: #171717;
    --ed-button-disabled-bg-color: #b7bdc6;
    --ed-button-disabled-border-color: #b7bdc6;
    --ed-button-disabled-text-color: #ffffff;
  }

  :deep(.save-button) {
    flex-shrink: 0;
    height: 40px;
    padding: 0 20px;
    font-weight: 500;
  }

  .guide-card {
    display: flex;
    flex-direction: column;

    .card-heading {
      flex-wrap: wrap;
      row-gap: 8px;
      margin-bottom: 20px;
    }
  }

  .doc-link {
    display: inline-flex;
    align-items: center;
    flex-shrink: 0;
    gap: 4px;
    padding: 2px 0;
    color: var(--robot-body);
    font-size: 12px;
    line-height: 20px;
    text-decoration: none;

    &:hover {
      color: var(--robot-text);
      text-decoration: underline;
      text-underline-offset: 3px;
    }

    &:focus-visible {
      border-radius: 2px;
      outline: 2px solid #525b69;
      outline-offset: 4px;
    }

    .ed-icon {
      font-size: 14px;
    }
  }

  .setup-steps {
    margin: 0 0 24px;
    padding: 0;
    list-style: none;

    li {
      position: relative;
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding-bottom: 20px;

      &:not(:last-child)::after {
        position: absolute;
        top: 30px;
        bottom: 6px;
        left: 13px;
        width: 1px;
        background: var(--robot-border);
        content: '';
      }

      &:last-child {
        padding-bottom: 0;
      }
    }
  }

  .step-number {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 28px;
    height: 28px;
    border: 1px solid var(--robot-border);
    border-radius: 50%;
    background: #f8f9fb;
    color: var(--robot-body);
    font-size: 12px;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }

  .step-copy {
    min-width: 0;
    padding-top: 3px;

    h3 {
      font-size: 13px;
      font-weight: 600;
      line-height: 22px;
    }

    p {
      margin-top: 4px;
      color: var(--robot-body);
      font-size: 13px;
      line-height: 21px;
      overflow-wrap: break-word;
    }
  }

  .identity-note {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-top: auto;
    padding-top: 16px;
    border-top: 1px solid var(--robot-border);
    color: var(--robot-body);

    .ed-icon {
      flex-shrink: 0;
      margin-top: 3px;
      color: var(--robot-secondary);
      font-size: 14px;
    }

    p {
      font-size: 12px;
      line-height: 21px;
    }
  }

  .runtime-card {
    .card-heading {
      align-items: center;
      margin-bottom: 20px;
    }
  }

  .status-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .platform-status {
    display: flex;
    flex-direction: column;
    min-width: 0;
    padding: 0 24px;

    &:first-child {
      padding-left: 0;
    }

    &:last-child {
      padding-right: 0;
    }

    & + .platform-status {
      border-left: 1px solid var(--robot-border);
    }
  }

  .status-heading,
  .status-platform {
    display: flex;
    align-items: center;
  }

  .status-heading {
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 8px;
  }

  .status-platform {
    gap: 8px;

    img {
      display: block;
      flex-shrink: 0;
    }

    h3 {
      font-size: 14px;
      font-weight: 600;
      line-height: 24px;
    }
  }

  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 2px 8px;
    border-radius: 5px;
    background: #f2f3f5;
    color: var(--robot-body);
    font-size: 12px;
    line-height: 20px;
    white-space: nowrap;

    &.is-running {
      background: #edf6f0;
      color: #3c6b4f;
    }

    &.is-warning {
      background: #fff7e8;
      color: #916518;
    }
  }

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
  }

  .platform-description {
    color: var(--robot-body);
    font-size: 12px;
    line-height: 20px;
  }

  .status-detail {
    margin: 12px 0 20px;
    color: var(--robot-body);
    font-size: 13px;
    line-height: 21px;
    white-space: pre-line;
    overflow-wrap: anywhere;

    &.has-error {
      color: #916518;
    }
  }

  .status-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-top: auto;
  }

  .status-config-label {
    color: var(--robot-secondary);
    font-size: 12px;
    line-height: 20px;
  }

  .runtime-footnote {
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--robot-border);
    color: var(--robot-secondary);
    font-size: 12px;
    line-height: 20px;
  }

  .load-notice {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 20px;
    padding: 16px 20px;
    border: 1px solid #eddfbe;
    border-radius: 10px;
    background: #fffbf2;
    color: #825d20;

    strong {
      font-size: 14px;
      font-weight: 500;
      line-height: 22px;
    }

    p {
      margin-top: 4px;
      font-size: 13px;
      line-height: 21px;
    }

    .ed-button {
      flex-shrink: 0;
    }
  }

  .status-notice {
    margin: -4px 0 20px;
    color: #825d20;
    font-size: 13px;
    line-height: 21px;
  }
}

@media (max-width: 1200px) {
  .robot-config {
    padding: 28px 24px 32px;

    .robot-card {
      padding: 20px;
    }

    .platform-status {
      padding-right: 16px;
      padding-left: 16px;
    }
  }
}

@media (max-width: 1100px) {
  .robot-config {
    .setup-grid {
      grid-template-columns: minmax(0, 1fr);
    }

    .status-grid {
      grid-template-columns: minmax(0, 1fr);
    }

    .platform-status {
      padding: 20px 0;

      &:first-child {
        padding-top: 0;
      }

      &:last-child {
        padding-bottom: 0;
      }

      & + .platform-status {
        border-top: 1px solid var(--robot-border);
        border-left: 0;
      }
    }

    .status-detail {
      margin: 8px 0 12px;
    }
  }
}

@media (max-width: 600px) {
  .robot-config {
    padding: 24px 16px;

    .page-head {
      margin-bottom: 24px;

      h1 {
        font-size: 22px;
      }
    }

    .platform-bar {
      display: block;
    }

    .platform-group {
      display: flex;
      width: 100%;

      :deep(.ed-radio-button__inner) {
        min-height: 44px;
        padding: 8px 6px;
        font-size: 13px;
      }
    }

    .platform-option {
      gap: 6px;

      img {
        width: 18px;
        height: 18px;
      }
    }

    .connection-note {
      display: block;
      margin-top: 12px;
      font-size: 12px;
    }

    .robot-card {
      padding: 20px 16px;
    }

    .card-heading {
      gap: 8px;

      p {
        font-size: 14px;
        line-height: 22px;
      }
    }

    .card-footer,
    .load-notice {
      align-items: flex-start;
      flex-direction: column;
    }

    .card-footer .ed-button {
      width: 100%;
    }

    :deep(.ed-button) {
      min-height: 44px;
      font-size: 14px;
    }

    :deep(.ed-input__inner) {
      font-size: 16px;
    }

    .step-copy h3,
    .step-copy p,
    .identity-note p,
    .platform-description,
    .status-detail {
      font-size: 14px;
      line-height: 23px;
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .robot-config {
    :deep(.ed-button),
    :deep(.ed-radio-button__inner) {
      transition: none;
    }
  }
}
</style>
