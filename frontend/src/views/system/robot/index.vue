<template>
  <div class="robot-config">
    <p class="router-title">{{ t('robot.title') }}</p>

    <div v-loading="loading" class="robot-content">
      <!-- 平台选择 -->
      <div class="robot-card">
        <div class="card-header">
          <span class="card-title">{{ t('robot.platform') }}</span>
        </div>
        <el-radio-group v-model="form.platform" :disabled="status.running">
          <el-radio-button value="feishu">{{ t('robot.feishu') }}</el-radio-button>
        </el-radio-group>
        <p class="card-tip">{{ t('robot.platform_tip') }}</p>
        <p class="card-tip">{{ t('robot.identity_tip') }}</p>
      </div>

      <!-- 凭据配置 -->
      <div class="robot-card">
        <div class="card-header">
          <span class="card-title">{{ t('robot.credentials') }}</span>
        </div>
        <el-form :model="form" label-position="top" class="robot-form">
          <el-form-item :label="t('robot.app_id')">
            <el-input
              v-model="form.app_id"
              :placeholder="t('robot.app_id_placeholder')"
              clearable
            />
          </el-form-item>
          <el-form-item :label="t('robot.app_secret')">
            <el-input
              v-model="form.app_secret"
              type="password"
              show-password
              :placeholder="appSecretPlaceholder"
            />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="form.auto_start" :disabled="status.running">
              {{ t('robot.auto_start') }}
            </el-checkbox>
          </el-form-item>
        </el-form>

        <div class="card-actions">
          <el-button type="primary" :loading="saving" @click="save">{{ t('robot.save') }}</el-button>
        </div>
      </div>

      <!-- 运行状态 -->
      <div class="robot-card">
        <div class="card-header">
          <span class="card-title">{{ t('robot.run_status') }}</span>
          <span class="status-dot" :class="{ running: status.running }"></span>
          <span class="status-text">{{ status.running ? t('robot.running') : t('robot.stopped') }}</span>
        </div>

        <p v-if="!status.configured" class="card-tip warn">{{ t('robot.not_configured') }}</p>

        <div class="card-actions">
          <el-button
            v-if="!status.running"
            type="primary"
            :loading="starting"
            :disabled="!status.configured"
            @click="start"
          >
            {{ t('robot.start') }}
          </el-button>
          <el-button v-else type="danger" :loading="stopping" @click="stop">
            {{ t('robot.stop') }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus-secondary'
import { robotApi } from '@/api/robot'

const { t } = useI18n()

const loading = ref(false)
const saving = ref(false)
const starting = ref(false)
const stopping = ref(false)

const form = reactive({
  platform: 'feishu',
  app_id: '',
  app_secret: '',
  auto_start: false,
})

const status = reactive({
  running: false,
  configured: false,
  message: '',
})

const appSecretPlaceholder = computed(() =>
  status.configured ? t('robot.app_secret_placeholder_saved') : t('robot.app_secret_placeholder'),
)

const loadConfig = async () => {
  loading.value = true
  try {
    const cfg: any = await robotApi.getConfig()
    form.platform = cfg.platform || 'feishu'
    form.app_id = cfg.app_id || ''
    form.auto_start = !!cfg.auto_start
    status.configured = !!cfg.configured
    // secret 不回填明文，仅显示占位
    form.app_secret = ''
  } finally {
    loading.value = false
  }
}

const loadStatus = async () => {
  const st: any = await robotApi.status()
  status.running = !!st.running
  status.configured = !!st.configured
  status.message = st.message || ''
}

const save = async () => {
  if (!form.app_id) {
    ElMessage.warning(t('robot.app_id_required'))
    return
  }
  saving.value = true
  try {
    await robotApi.saveConfig({
      platform: form.platform,
      app_id: form.app_id,
      app_secret: form.app_secret || undefined,
      auto_start: form.auto_start,
    })
    ElMessage.success(t('robot.save_success'))
    form.app_secret = ''
    await loadConfig()
    await loadStatus()
  } finally {
    saving.value = false
  }
}

const start = async () => {
  starting.value = true
  try {
    const res: any = await robotApi.start()
    ElMessage.success(res.message || t('robot.start_success'))
    await loadStatus()
  } finally {
    starting.value = false
  }
}

const stop = async () => {
  stopping.value = true
  try {
    const res: any = await robotApi.stop()
    ElMessage.success(res.message || t('robot.stop_success'))
    await loadStatus()
  } finally {
    stopping.value = false
  }
}

onMounted(() => {
  loadConfig()
  loadStatus()
})
</script>

<style lang="less" scoped>
.robot-config {
  padding: 24px;

  .router-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 20px;
  }

  .robot-content {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 720px;
  }

  .robot-card {
    background: var(--ed-color-bg-container, #fff);
    border: 1px solid var(--ed-color-border, #e5e6eb);
    border-radius: 8px;
    padding: 20px;

    .card-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;

      .card-title {
        font-size: 14px;
        font-weight: 600;
      }

      .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #c0c4cc;
        margin-left: auto;

        &.running {
          background: #67c23a;
        }
      }

      .status-text {
        font-size: 13px;
        color: #606266;
      }
    }

    .card-tip {
      font-size: 13px;
      color: #909399;
      margin: 8px 0;

      &.warn {
        color: #e6a23c;
      }
    }

    .card-actions {
      display: flex;
      gap: 12px;
      margin-top: 8px;
    }
  }

  .robot-form {
    max-width: 480px;
  }
}
</style>
