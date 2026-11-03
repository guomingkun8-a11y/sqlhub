<template>
  <div
    v-if="showLoading"
    v-loading="true"
    :element-loading-text="t('qa.loading')"
    class="xpack-login-handler-mask"
    element-loading-background="#F5F6F7"
  ></div>

  <div
    ref="loginContainer"
    class="login-page"
    :class="{ 'is-ready': ready, 'hide-login-container': showLoading }"
    @mousemove="onMouseMove"
    @mouseleave="resetParallax"
  >
    <!-- ==================== 左：认证区 ==================== -->
    <section class="auth-pane">
      <div class="auth-inner">
        <header class="brand-row reveal" style="--d: 0ms">
          <span class="brand-glyph" aria-hidden="true">
            <LOGO_fold />
          </span>
          <span class="brand-name">{{ brandName }}</span>
          <span class="brand-badge">智能问数</span>
        </header>

        <div class="auth-body">
          <div class="auth-head">
            <h1 class="auth-title">
              <span class="title-rule" aria-hidden="true"></span>
              <span class="title-line">
                <Transition name="ttl">
                  <span :key="mode" class="title-text">
                    {{ mode === 'login' ? '欢迎回来' : '创建账号' }}<i class="title-dot">.</i>
                  </span>
                </Transition>
              </span>
            </h1>
            <div class="auth-sub-wrap">
              <Transition name="ttl">
                <p :key="mode" class="auth-sub">
                  {{ mode === 'login' ? subTitle : '30 秒完成注册，立刻开始向你的数据提问。' }}
                </p>
              </Transition>
            </div>
          </div>

          <!-- 登录 / 注册 分段控件 -->
          <div v-if="registerEnabled" class="seg" role="tablist" aria-label="登录或注册">
            <span class="seg-pill" :class="{ right: mode === 'register' }" aria-hidden="true"></span>
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'login'"
              :class="{ active: mode === 'login' }"
              @click="goMode('login')"
            >
              登录
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'register'"
              :class="{ active: mode === 'register' }"
              @click="goMode('register')"
            >
              注册
            </button>
          </div>

          <div class="form-wrap" :class="{ 'no-tabs': !registerEnabled }">
            <Transition name="swap">
              <!-- ---------------- 登录 ---------------- -->
              <div v-if="mode === 'login'" key="login" class="auth-block">
                <form class="auth-form" autocomplete="off" novalidate @submit.prevent="doLogin">
                  <div class="field" :class="{ invalid: !!errors.username }">
                    <input
                      id="lg-account"
                      v-model.trim="loginForm.username"
                      class="field-input"
                      type="text"
                      placeholder=" "
                      autocomplete="off"
                      spellcheck="false"
                      @input="clearError('username')"
                    />
                    <label class="field-label" for="lg-account">账号</label>
                    <span class="focus-line" aria-hidden="true"></span>
                    <Transition name="msg">
                      <span v-if="errors.username" class="field-msg">{{ errors.username }}</span>
                    </Transition>
                  </div>

                  <div class="field" :class="{ invalid: !!errors.password }">
                    <input
                      id="lg-pwd"
                      v-model="loginForm.password"
                      class="field-input has-trail"
                      :type="showPwd ? 'text' : 'password'"
                      placeholder=" "
                      autocomplete="off"
                      @input="clearError('password')"
                    />
                    <label class="field-label" for="lg-pwd">密码</label>
                    <button
                      type="button"
                      class="trail-btn"
                      :aria-label="showPwd ? '隐藏密码' : '显示密码'"
                      @click="showPwd = !showPwd"
                    >
                      <svg v-if="!showPwd" viewBox="0 0 24 24" fill="none">
                        <path
                          d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12Z"
                          stroke="currentColor"
                          stroke-width="1.6"
                          stroke-linejoin="round"
                        />
                        <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6" />
                      </svg>
                      <svg v-else viewBox="0 0 24 24" fill="none">
                        <path
                          d="M4 4l16 16M9.9 5.1A9.6 9.6 0 0 1 12 4.9c6 0 9.5 6.2 9.5 6.2a17 17 0 0 1-2.9 3.6M6.4 7.6A17.6 17.6 0 0 0 2.5 11.1S6 17.3 12 17.3c1.4 0 2.6-.3 3.7-.8"
                          stroke="currentColor"
                          stroke-width="1.6"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </svg>
                    </button>
                    <span class="focus-line" aria-hidden="true"></span>
                    <Transition name="msg">
                      <span v-if="errors.password" class="field-msg">{{ errors.password }}</span>
                    </Transition>
                  </div>

                  <button
                    class="primary-btn"
                    :class="{ ready: canLogin, done: loginDone }"
                    :disabled="!canLogin || submitting"
                    type="submit"
                    @click="onBtnRipple"
                  >
                    <span v-if="loginDone" class="done-mark" aria-label="登录成功">
                      <svg viewBox="0 0 24 24" fill="none">
                        <path
                          d="M5 12.6 9.6 17 19 7.4"
                          stroke="currentColor"
                          stroke-width="2.2"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </svg>
                    </span>
                    <template v-else-if="!submitting">
                      <span>继续</span>
                      <svg class="arrow" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          d="M5 12h13M12.5 6l6 6-6 6"
                          stroke="currentColor"
                          stroke-width="1.8"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </svg>
                    </template>
                    <span v-else class="loader" aria-label="登录中">
                      <i></i><i></i><i></i>
                    </span>
                  </button>
                </form>

                <Handler
                  v-model:loading="showLoading"
                  jsname="L2NvbXBvbmVudC9sb2dpbi9IYW5kbGVy"
                  @switch-tab="switchTab"
                />
              </div>

              <!-- ---------------- 注册 ---------------- -->
              <div v-else key="register" class="auth-block">
                <form class="auth-form register-form" novalidate @submit.prevent="doRegister">
                  <div class="form-row">
                    <div class="field" :class="{ invalid: !!errors.name }">
                      <input
                        id="rg-name"
                        v-model.trim="regForm.name"
                        class="field-input"
                        type="text"
                        placeholder=" "
                        autocomplete="name"
                        @input="clearError('name')"
                      />
                      <label class="field-label" for="rg-name">姓名</label>
                      <span class="focus-line" aria-hidden="true"></span>
                      <Transition name="msg">
                        <span v-if="errors.name" class="field-msg">{{ errors.name }}</span>
                      </Transition>
                    </div>

                    <div class="field" :class="{ invalid: !!errors.username }">
                      <input
                        id="rg-account"
                        v-model.trim="regForm.username"
                        class="field-input"
                        type="text"
                        placeholder=" "
                        autocomplete="username"
                        spellcheck="false"
                        @input="clearError('username')"
                      />
                      <label class="field-label" for="rg-account">登录账号</label>
                      <span class="focus-line" aria-hidden="true"></span>
                      <Transition name="msg">
                        <span v-if="errors.username" class="field-msg">{{ errors.username }}</span>
                      </Transition>
                    </div>
                  </div>

                  <div class="field" :class="{ invalid: !!errors.email }">
                    <input
                      id="rg-email"
                      v-model.trim="regForm.email"
                      class="field-input"
                      type="email"
                      placeholder=" "
                      autocomplete="email"
                      spellcheck="false"
                      @input="clearError('email')"
                    />
                    <label class="field-label" for="rg-email">邮箱（选填）</label>
                    <span class="focus-line" aria-hidden="true"></span>
                    <Transition name="msg">
                      <span v-if="errors.email" class="field-msg">{{ errors.email }}</span>
                    </Transition>
                  </div>

                  <div class="form-row">
                    <div class="field" :class="{ invalid: !!errors.password }">
                      <input
                        id="rg-pwd"
                        v-model="regForm.password"
                        class="field-input has-trail"
                        :type="showRegPwd ? 'text' : 'password'"
                        placeholder=" "
                        autocomplete="new-password"
                        @input="clearError('password')"
                      />
                      <label class="field-label" for="rg-pwd">密码</label>
                      <button
                        type="button"
                        class="trail-btn"
                        :aria-label="showRegPwd ? '隐藏密码' : '显示密码'"
                        @click="showRegPwd = !showRegPwd"
                      >
                        <svg v-if="!showRegPwd" viewBox="0 0 24 24" fill="none">
                          <path
                            d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12Z"
                            stroke="currentColor"
                            stroke-width="1.6"
                            stroke-linejoin="round"
                          />
                          <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6" />
                        </svg>
                        <svg v-else viewBox="0 0 24 24" fill="none">
                          <path
                            d="M4 4l16 16M9.9 5.1A9.6 9.6 0 0 1 12 4.9c6 0 9.5 6.2 9.5 6.2a17 17 0 0 1-2.9 3.6M6.4 7.6A17.6 17.6 0 0 0 2.5 11.1S6 17.3 12 17.3c1.4 0 2.6-.3 3.7-.8"
                            stroke="currentColor"
                            stroke-width="1.6"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                        </svg>
                      </button>
                      <span class="focus-line" aria-hidden="true"></span>
                      <Transition name="msg">
                        <span v-if="errors.password" class="field-msg">{{ errors.password }}</span>
                      </Transition>
                    </div>

                    <div class="field" :class="{ invalid: !!errors.confirm }">
                      <input
                        id="rg-pwd2"
                        v-model="regForm.confirm"
                        class="field-input"
                        :type="showRegPwd ? 'text' : 'password'"
                        placeholder=" "
                        autocomplete="new-password"
                        @input="clearError('confirm')"
                      />
                      <label class="field-label" for="rg-pwd2">确认密码</label>
                      <span class="focus-line" aria-hidden="true"></span>
                      <Transition name="msg">
                        <span v-if="errors.confirm" class="field-msg">{{ errors.confirm }}</span>
                      </Transition>
                    </div>

                    <Transition name="msg">
                      <div v-if="regForm.password" class="strength">
                        <span class="strength-bars">
                          <i
                            v-for="n in 4"
                            :key="n"
                            :class="{ on: strengthLevel >= n }"
                            :data-lv="strengthLevel"
                          ></i>
                        </span>
                        <span class="strength-text">{{ strengthText }}</span>
                        <span class="strength-hint">{{ pwdHint }}</span>
                      </div>
                    </Transition>
                  </div>

                  <button
                    class="primary-btn"
                    :class="{ ready: canRegister }"
                    :disabled="!canRegister || submitting"
                    type="submit"
                    @click="onBtnRipple"
                  >
                    <template v-if="!submitting">
                      <span>创建账号</span>
                      <svg class="arrow" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path
                          d="M5 12h13M12.5 6l6 6-6 6"
                          stroke="currentColor"
                          stroke-width="1.8"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        />
                      </svg>
                    </template>
                    <span v-else class="loader" aria-label="提交中">
                      <i></i><i></i><i></i>
                    </span>
                  </button>
                </form>
              </div>
            </Transition>
          </div>
        </div>

        <footer class="auth-foot">
          <span>© {{ year }} {{ brandName }}</span>
          <template v-if="footText">
            <span class="dot-sep">·</span>
            <span>{{ footText }}</span>
          </template>
        </footer>
      </div>
    </section>

    <!-- ==================== 右：品牌区 ==================== -->
    <section class="brand-pane" @mousemove="onPaneMove">
      <div v-if="customBg" class="brand-bg">
        <img :src="customBg" alt="" />
        <span class="brand-bg-mask"></span>
      </div>

      <template v-else>
        <span class="aurora a1" aria-hidden="true"></span>
        <span class="aurora a2" aria-hidden="true"></span>
        <span class="dotgrid" aria-hidden="true"></span>
        <span class="spotlight" aria-hidden="true"></span>

        <div class="shapes" :style="parallaxStyle" aria-hidden="true">
          <!-- 八芒星（主视觉） -->
          <svg class="shape s1" data-depth="16" viewBox="0 0 200 200" fill="none">
            <path
              d="M100 0l26 58 58-26-26 58 58 26-58 26 26 58-58-26-26 58-26-58-58 26 26-58L0 116l58-26L32 32l58 26L100 0Z"
              fill="url(#g1)"
            />
            <defs>
              <linearGradient id="g1" x1="30" y1="20" x2="170" y2="180">
                <stop stop-color="#3fd0a6" /><stop offset="1" stop-color="#0a8a6d" />
              </linearGradient>
            </defs>
          </svg>

          <!-- 细环 -->
          <span class="shape s2 ring" data-depth="9"></span>

          <!-- 橙色圆点 -->
          <svg class="shape s3" data-depth="22" viewBox="0 0 200 200" fill="none">
            <circle cx="100" cy="100" r="100" fill="#f2b134" />
          </svg>

          <!-- 黑色四角星 -->
          <svg class="shape s4" data-depth="12" viewBox="0 0 200 200" fill="none">
            <path
              d="M100 0c6 54 46 94 100 100-54 6-94 46-100 100-6-54-46-94-100-100C54 94 94 54 100 0Z"
              fill="var(--ink-900)"
            />
          </svg>
        </div>
      </template>

      <div class="brand-inner" :style="copyParallaxStyle">
        <p class="brand-eyebrow reveal" style="--d: 220ms">
          <span class="pulse-dot" aria-hidden="true"></span>
          数据问答工作台
        </p>

        <h2 class="brand-title">
          <span class="line"><span class="line-inner">让你的数据</span></span>
          <span class="line"><span class="line-inner"><em>自己说话</em></span></span>
        </h2>

        <p class="brand-lede reveal" style="--d: 560ms">
          不用记表名，也不用写 SQL。<br />
          一句人话提问，自动查表、核算，直接给出结论。
        </p>

        <ul class="metrics reveal" style="--d: 680ms">
          <li>
            <strong>自然语言 → SQL</strong>
            <span>不必了解表结构</span>
          </li>
          <li>
            <strong>多源统一</strong>
            <span>一个入口问所有库</span>
          </li>
          <li>
            <strong>结论优先</strong>
            <span>给答案，不只给列表</span>
          </li>
        </ul>
      </div>
    </section>
  </div>

  <InitialPwdDialog
    v-model="initPwdDialogVisible"
    :account="loginForm.username"
    :old-pwd="loginForm.password"
    @pwd-saved="onInitPwdSaved"
  />
</template>

<script lang="ts" setup>
import { ref, computed, onMounted, reactive, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus-secondary'
import { useUserStore } from '@/stores/user'
import { AuthApi } from '@/api/login'
import { useAppearanceStoreWithOut } from '@/stores/appearance'
import Handler from './xpack/Handler.vue'
import InitialPwdDialog from './InitialPwdDialog.vue'
import { toLoginSuccess } from '@/utils/utils'
import LOGO_fold from '@/assets/LOGO-fold.svg'

const showLoading = ref(true)
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const appearanceStore = useAppearanceStoreWithOut()
const loginContainer = ref()

const mode = ref<'login' | 'register'>('login')
const submitting = ref(false)
const loginDone = ref(false)
const ready = ref(false)
const showPwd = ref(false)
const showRegPwd = ref(false)
const activeName = ref('simple')
const registerEnabled = ref(false)

const brandName = computed(() => appearanceStore.name || 'SQLHub')
const year = new Date().getFullYear()
const footText = computed(() => {
  const raw = appearanceStore.getFootContent || appearanceStore.getFoot
  if (!raw || typeof raw !== 'string') return ''
  return raw === 'false' || raw === 'true' ? '' : raw
})
const customBg = computed(() => appearanceStore.getBg || '')
const subTitle = computed(
  () =>
    appearanceStore.slogan ||
    appearanceStore.pc_welcome_desc ||
    appearanceStore.getSlogan ||
    '登录后继续向你的数据提问。'
)

/* ----------------------------- 登录 ----------------------------- */
const loginForm = reactive({ username: '', password: '' })
const errors = reactive<Record<string, string>>({})
const initPwdDialogVisible = ref(false)

const canLogin = computed(() => !!loginForm.username && !!loginForm.password)

const clearError = (key: string) => {
  if (errors[key]) delete errors[key]
}

const doLogin = async () => {
  if (submitting.value || loginDone.value) return
  Object.keys(errors).forEach((k) => delete errors[k])

  if (!loginForm.username) {
    errors.username = '请输入账号'
    return
  }
  if (!loginForm.password) {
    errors.password = '请输入密码'
    return
  }

  submitting.value = true
  try {
    const res: any = await AuthApi.login({
      username: loginForm.username,
      password: loginForm.password,
    })
    if (res?.need_change_pwd) {
      initPwdDialogVisible.value = true
      return
    }
    if (res?.access_token) {
      userStore.setToken(res.access_token)
    }
    loginDone.value = true
    window.setTimeout(() => toLoginSuccess(router), 520)
  } catch (e: any) {
    errors.password = pickError(e) || '账号或密码不正确'
  } finally {
    submitting.value = false
  }
}

const onInitPwdSaved = (newPwd: string) => {
  loginForm.password = newPwd
}

const switchTab = (name: string) => {
  activeName.value = name || 'simple'
}

/* ----------------------------- 注册 ----------------------------- */
const regForm = reactive({ name: '', username: '', email: '', password: '', confirm: '' })
const EMAIL_RE = /^[a-zA-Z0-9]+([._-][a-zA-Z0-9]+)*@([a-zA-Z0-9]+(-[a-zA-Z0-9]+)*\.)+[a-zA-Z]{2,}$/
const PWD_RE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,20}$/

const canRegister = computed(
  () =>
    !!regForm.name &&
    !!regForm.username &&
    !!regForm.password &&
    !!regForm.confirm &&
    regForm.password === regForm.confirm
)

const strengthLevel = computed(() => {
  const p = regForm.password
  if (!p) return 0
  let lv = 0
  if (p.length >= 8) lv++
  if (/[a-z]/.test(p) && /[A-Z]/.test(p)) lv++
  if (/\d/.test(p)) lv++
  if (/[^A-Za-z0-9]/.test(p)) lv++
  if (p.length > 20) lv = Math.min(lv, 3)
  return Math.min(lv, 4)
})

const strengthText = computed(() => {
  return ['太短了', '偏弱', '一般', '不错', '很强'][strengthLevel.value] || ''
})

const pwdHint = computed(() =>
  strengthLevel.value >= 4 ? '' : '需含大小写、数字和符号'
)

const pickError = (e: any): string => {
  const detail =
    e?.response?.data?.detail ?? e?.detail ?? e?.response?.data?.message ?? e?.message ?? ''
  if (typeof detail === 'string' && detail && !/^Invalid request/.test(detail)) return detail
  if (Array.isArray(detail) && detail.length) return detail[0]?.msg || ''
  return ''
}

const doRegister = async () => {
  if (submitting.value) return
  Object.keys(errors).forEach((k) => delete errors[k])

  if (!regForm.name) {
    errors.name = '请输入姓名'
    return
  }
  if (!regForm.username) {
    errors.username = '请输入登录账号'
    return
  }
  if (!/^[A-Za-z0-9_.@-]{3,50}$/.test(regForm.username)) {
    errors.username = '3-50 位字母、数字或 _ . @ -'
    return
  }
  if (regForm.email && !EMAIL_RE.test(regForm.email)) {
    errors.email = '邮箱格式不正确'
    return
  }
  if (!PWD_RE.test(regForm.password)) {
    errors.password = '8-20 位，需含大写、小写、数字和特殊字符'
    return
  }
  if (regForm.password !== regForm.confirm) {
    errors.confirm = '两次输入的密码不一致'
    return
  }

  submitting.value = true
  try {
    const res: any = await AuthApi.register({
      username: regForm.username,
      password: regForm.password,
      name: regForm.name,
      email: regForm.email,
    })
    if (res?.access_token) {
      userStore.setToken(res.access_token)
      ElMessage.success('账号创建成功，正在进入系统…')
      toLoginSuccess(router)
    } else {
      ElMessage.success('账号创建成功，请登录')
      goMode('login', regForm.username)
    }
  } catch (e: any) {
    const msg = pickError(e) || '注册失败，请稍后重试'
    if (/已存在/.test(msg)) errors.username = msg
    else ElMessage.error(msg)
  } finally {
    submitting.value = false
  }
}

const goMode = (next: 'login' | 'register', prefillAccount?: string) => {
  if (submitting.value) return
  Object.keys(errors).forEach((k) => delete errors[k])
  if (next === 'login' && prefillAccount) loginForm.username = prefillAccount
  mode.value = next
}

/* ----------------------------- 交互：视差 + 光斑 ----------------------------- */
const px = ref(0)
const py = ref(0)

const onMouseMove = (e: MouseEvent) => {
  const w = window.innerWidth || 1
  const h = window.innerHeight || 1
  px.value = (e.clientX / w - 0.5) * 2
  py.value = (e.clientY / h - 0.5) * 2
}

const resetParallax = () => {
  px.value = 0
  py.value = 0
}

const parallaxStyle = computed(() => ({
  '--px': px.value.toFixed(3),
  '--py': py.value.toFixed(3),
}))

/* 文案跟随的轻微反向位移，制造层次 */
const copyParallaxStyle = computed(() => ({
  '--cpx': `${(-px.value * 3.5).toFixed(2)}px`,
  '--cpy': `${(-py.value * 2.5).toFixed(2)}px`,
}))

/* 右栏跟随光标的光斑 */
const onPaneMove = (e: MouseEvent) => {
  const el = e.currentTarget as HTMLElement
  if (!el) return
  const r = el.getBoundingClientRect()
  el.style.setProperty('--mx', `${((e.clientX - r.left) / r.width) * 100}%`)
  el.style.setProperty('--my', `${((e.clientY - r.top) / r.height) * 100}%`)
  el.classList.add('has-pointer')
}

/* 按钮点击水波 */
const onBtnRipple = (e: MouseEvent) => {
  const el = e.currentTarget as HTMLElement
  if (!el || el.classList.contains('done')) return
  const r = el.getBoundingClientRect()
  const span = document.createElement('span')
  span.className = 'btn-ripple'
  span.style.left = `${e.clientX - r.left}px`
  span.style.top = `${e.clientY - r.top}px`
  el.appendChild(span)
  window.setTimeout(() => span.remove(), 640)
}

/* ----------------------------- 初始化 ----------------------------- */
onMounted(async () => {
  try {
    const status: any = await AuthApi.registerStatus()
    registerEnabled.value = !!status?.enabled
  } catch {
    registerEnabled.value = false
  }
  // 等遮罩消失后再播放入场编排
  window.setTimeout(() => {
    ready.value = true
  }, 120)
})

watch(
  () => showLoading.value,
  (v) => {
    if (!v) nextTick(() => (ready.value = true))
  }
)
</script>

<style lang="less" scoped>
/* ==========================================================
   登录 / 注册页 · 墨黑极简
   ========================================================== */
.login-page {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--paper);
  color: var(--ink-900);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
}

/* ==================== 左侧认证区 ==================== */
.auth-pane {
  position: relative;
  flex: 0 0 46%;
  max-width: 660px;
  min-width: 400px;
  height: 100%;
  display: flex;
  justify-content: center;
  padding: 40px 44px 30px;
  background: var(--paper);
  z-index: 2;
}

.auth-inner {
  width: 100%;
  max-width: 388px;
  display: flex;
  flex-direction: column;
}

/* ---------- 品牌行 ---------- */
.brand-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
  height: 34px;

  .brand-glyph {
    width: 30px;
    height: 30px;
    display: block;
    flex: 0 0 auto;

    svg {
      width: 100%;
      height: 100%;
      display: block;
    }
  }

  .brand-name {
    font-size: 16px;
    font-weight: 650;
    letter-spacing: -0.012em;
    color: var(--ink-900);
  }

  .brand-badge {
    margin-left: 2px;
    padding: 3px 8px;
    font-size: 10.5px;
    font-weight: 500;
    letter-spacing: 0.02em;
    color: var(--ink-500);
    background: var(--ink-100);
    border-radius: var(--radius-pill);
    line-height: 1.2;
  }
}

/* ---------- 中央表单区 ---------- */
.auth-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  padding: clamp(34px, 9vh, 100px) 0 20px;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: none;

  &::-webkit-scrollbar {
    display: none;
  }
}

.auth-head {
  .auth-title {
    position: relative;
    margin: 0;
    padding-left: 0;
    font-size: 37px;
    line-height: 1.14;
    font-weight: 800;
    letter-spacing: -0.035em;
    color: var(--ink-950);

    .title-rule {
      display: block;
      width: 26px;
      height: 3px;
      margin-bottom: 18px;
      border-radius: 2px;
      background: var(--accent-500);
    }

    .title-line {
      display: block;
      overflow: hidden;
      padding-bottom: 2px;
    }

    .title-text {
      display: inline-block;
      white-space: nowrap;
    }

    .title-dot {
      font-style: normal;
      color: var(--accent-500);
    }
  }

  .auth-sub-wrap {
    min-height: 23px;
    margin-top: 16px;
  }

  .auth-sub {
    margin: 0;
    font-size: 14px;
    line-height: 1.62;
    color: var(--ink-500);
    letter-spacing: 0.002em;
  }
}

/* 标题 / 副标题文字切换（叠层交叉淡入，避免出现空白断层） */
.title-line,
.auth-sub-wrap {
  position: relative;
  display: block;
}

.ttl-enter-active {
  transition:
    opacity 300ms var(--ease-out-quart),
    transform 400ms var(--ease-out-expo),
    filter 260ms linear;
}

.ttl-leave-active {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  transition:
    opacity 180ms linear,
    transform 240ms var(--ease-out-quart),
    filter 180ms linear;
}

.ttl-enter-from {
  opacity: 0;
  transform: translateY(9px);
  filter: blur(2px);
}

.ttl-leave-to {
  opacity: 0;
  transform: translateY(-7px);
  filter: blur(2px);
}

/* ---------- 分段控件 ---------- */
.seg {
  position: relative;
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin-top: 28px;
  padding: 4px;
  background: var(--ink-100);
  border-radius: var(--radius-pill);

  .seg-pill {
    position: absolute;
    top: 4px;
    left: 4px;
    width: calc(50% - 4px);
    height: calc(100% - 8px);
    background: #fff;
    border-radius: var(--radius-pill);
    box-shadow:
      0 1px 2px rgba(12, 12, 14, 0.08),
      0 2px 6px rgba(12, 12, 14, 0.06),
      0 0 0 0.5px rgba(12, 12, 14, 0.05);
    transition: transform 420ms cubic-bezier(0.34, 1.42, 0.5, 1);

    &.right {
      transform: translateX(100%);
    }
  }

  button {
    position: relative;
    z-index: 1;
    height: 34px;
    border: 0;
    background: none;
    font-family: inherit;
    font-size: 13.5px;
    font-weight: 600;
    letter-spacing: 0.01em;
    color: var(--ink-500);
    cursor: pointer;
    border-radius: var(--radius-pill);
    transition: color 240ms var(--ease-out-quart);

    &:hover:not(.active) {
      color: var(--ink-800);
    }

    &.active {
      color: var(--ink-900);
    }
  }
}

.form-wrap {
  position: relative;
  margin-top: 26px;

  &.no-tabs {
    margin-top: 34px;
  }
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 19px;
}

/* 注册：两列成组，版面更有结构 */
.register-form {
  .form-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 12px;
  }

  .form-row .strength {
    grid-column: 1 / -1;
    margin: -2px 2px 0;
  }
}

/* ---------- 浮动标签输入框 ---------- */
.field {
  position: relative;
  padding-top: 9px;

  .field-input {
    display: block;
    width: 100%;
    height: 54px;
    padding: 0 16px;
    font-size: 15px;
    font-family: inherit;
    letter-spacing: 0.005em;
    color: var(--ink-900);
    background: #fff;
    border: 1px solid var(--ink-200);
    border-radius: var(--radius-md);
    outline: none;
    transition:
      border-color 240ms var(--ease-out-quart),
      box-shadow 320ms var(--ease-out-quart),
      background 200ms linear;

    &.has-trail {
      padding-right: 48px;
    }

    &::placeholder {
      color: transparent;
    }

    &:hover {
      border-color: var(--ink-300);
    }

    &:focus {
      border-color: var(--ink-900);
      background: #fff;
      box-shadow:
        0 0 0 4px rgba(23, 23, 26, 0.055),
        0 8px 20px -14px rgba(12, 12, 14, 0.4);
    }

    /* 浏览器自动填充样式修正 */
    &:-webkit-autofill {
      -webkit-text-fill-color: var(--ink-900);
      transition: background-color 9999s ease-out;
    }
  }

  .field-label {
    position: absolute;
    left: 13px;
    top: 39px;
    transform: translateY(-50%);
    padding: 0 4px;
    font-size: 15px;
    line-height: 1;
    color: var(--ink-400);
    background: #fff;
    pointer-events: none;
    border-radius: 3px;
    transition:
      top 300ms cubic-bezier(0.34, 1.32, 0.5, 1),
      font-size 240ms var(--ease-out-quart),
      color 240ms linear;
  }

  .field-input:focus ~ .field-label,
  .field-input:not(:placeholder-shown) ~ .field-label {
    top: 9px;
    font-size: 11.5px;
    letter-spacing: 0.01em;
    color: var(--ink-500);
  }

  .field-input:focus ~ .field-label {
    color: var(--accent-700);
  }

  /* 聚焦时的底部行进线 */
  .focus-line {
    position: absolute;
    left: 16px;
    right: 16px;
    bottom: 0;
    height: 2px;
    border-radius: 2px;
    background: var(--accent-500);
    transform: scaleX(0);
    transform-origin: left center;
    opacity: 0;
    transition:
      transform 420ms var(--ease-out-expo),
      opacity 200ms linear;
    pointer-events: none;
  }

  .field-input:focus ~ .focus-line {
    transform: scaleX(1);
    opacity: 1;
  }

  .trail-btn {
    position: absolute;
    right: 9px;
    top: 24px;
    width: 34px;
    height: 34px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--ink-400);
    cursor: pointer;
    transition:
      color 180ms linear,
      background 180ms linear,
      transform 180ms var(--ease-out-quart);

    svg {
      width: 18px;
      height: 18px;
    }

    &:hover {
      color: var(--ink-800);
      background: var(--ink-100);
    }

    &:active {
      transform: scale(0.9);
    }
  }

  .field-msg {
    display: block;
    margin: 7px 2px 0;
    font-size: 12px;
    line-height: 1.4;
    color: var(--danger);
  }

  /* 校验失败 */
  &.invalid {
    .field-input {
      border-color: var(--danger);
      box-shadow: 0 0 0 4px rgba(229, 72, 77, 0.07);
      animation: fieldShake 420ms var(--ease-out-quart);
    }

    .field-input:focus ~ .field-label,
    .field-input:not(:placeholder-shown) ~ .field-label {
      color: var(--danger);
    }

    .focus-line {
      background: var(--danger);
    }
  }
}

/* ---------- 密码强度 ---------- */
.strength {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 10px 2px 1px;

  .strength-bars {
    display: flex;
    gap: 4px;

    i {
      display: block;
      width: 32px;
      height: 3px;
      border-radius: 2px;
      background: var(--ink-200);
      transform-origin: left center;
      transition:
        background 280ms var(--ease-out-quart),
        transform 320ms cubic-bezier(0.34, 1.4, 0.5, 1);
    }

    i.on[data-lv='1'] {
      background: var(--danger);
    }
    i.on[data-lv='2'] {
      background: var(--warning);
    }
    i.on[data-lv='3'] {
      background: var(--accent-400);
    }
    i.on[data-lv='4'] {
      background: var(--accent-600);
    }
  }

  .strength-text {
    font-size: 11.5px;
    color: var(--ink-500);
    transition: color 240ms linear;
  }

  .strength-hint {
    margin-left: auto;
    font-size: 11px;
    letter-spacing: 0.01em;
    color: var(--ink-400);
  }
}

/* ---------- 主按钮 ---------- */
.primary-btn {
  position: relative;
  width: 100%;
  height: 54px;
  margin-top: 6px;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--ink-100);
  color: var(--ink-400);
  font-family: inherit;
  font-size: 15.5px;
  font-weight: 600;
  letter-spacing: 0.01em;
  cursor: not-allowed;
  transition:
    background 260ms var(--ease-out-quart),
    color 260ms var(--ease-out-quart),
    box-shadow 360ms var(--ease-out-quart),
    transform 180ms var(--ease-out-quart);

  .arrow {
    width: 17px;
    height: 17px;
    opacity: 0;
    transform: translateX(-6px);
    transition:
      opacity 260ms var(--ease-out-quart),
      transform 340ms var(--ease-out-expo);
  }

  &.ready {
    background: var(--ink-900);
    color: #fff;
    cursor: pointer;
    box-shadow:
      0 1px 2px rgba(12, 12, 14, 0.2),
      0 10px 24px -14px rgba(12, 12, 14, 0.6);

    .arrow {
      opacity: 1;
      transform: translateX(0);
    }

    /* 就绪时扫过一次高光 */
    &::before {
      content: '';
      position: absolute;
      top: 0;
      bottom: 0;
      left: -40%;
      width: 35%;
      background: linear-gradient(
        100deg,
        rgba(255, 255, 255, 0) 0%,
        rgba(255, 255, 255, 0.22) 50%,
        rgba(255, 255, 255, 0) 100%
      );
      transform: skewX(-18deg);
      animation: btnShine 900ms var(--ease-out-quart) 180ms 1;
      pointer-events: none;
    }

    &:hover {
      background: var(--ink-800);
      transform: translateY(-1.5px);
      box-shadow:
        0 2px 4px rgba(12, 12, 14, 0.22),
        0 16px 32px -16px rgba(12, 12, 14, 0.65);

      .arrow {
        transform: translateX(4px);
      }
    }

    &:active {
      transform: translateY(0) scale(0.985);
      box-shadow:
        0 1px 2px rgba(12, 12, 14, 0.24),
        0 6px 14px -10px rgba(12, 12, 14, 0.6);
    }
  }

  &.done {
    background: var(--accent-600);
    color: #fff;
    cursor: default;

    .done-mark {
      display: inline-flex;

      svg {
        width: 24px;
        height: 24px;

        path {
          stroke-dasharray: 26;
          stroke-dashoffset: 26;
          animation: checkDraw 420ms var(--ease-out-quart) forwards;
        }
      }
    }
  }

  .btn-ripple {
    position: absolute;
    width: 14px;
    height: 14px;
    margin: -7px 0 0 -7px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.34);
    pointer-events: none;
    animation: ripple 620ms var(--ease-out-expo) forwards;
  }
}

.loader {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;

  i {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.4;
    animation: dotPulse 1.05s var(--ease-out-quart) infinite;

    &:nth-child(2) {
      animation-delay: 0.14s;
    }
    &:nth-child(3) {
      animation-delay: 0.28s;
    }
  }
}

/* ---------- 页脚 ---------- */
.auth-foot {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--ink-400);
  letter-spacing: 0.015em;

  .dot-sep {
    opacity: 0.55;
  }
}

/* ==================== 右侧品牌区 ==================== */
.brand-pane {
  --mx: 50%;
  --my: 45%;
  position: relative;
  flex: 1;
  height: 100%;
  overflow: hidden;
  display: flex;
  align-items: center;
  padding: clamp(56px, 6vw, 88px) clamp(48px, 6.5vw, 104px);
  background: linear-gradient(148deg, #fcfdfc 0%, #f4f7f5 44%, #eef2f0 100%);

  .brand-bg {
    position: absolute;
    inset: 0;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    .brand-bg-mask {
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(12, 12, 14, 0.1), rgba(12, 12, 14, 0.45));
    }
  }

  /* 柔光斑 */
  .aurora {
    position: absolute;
    border-radius: 50%;
    filter: blur(70px);
    pointer-events: none;
    opacity: 0.55;
  }

  .a1 {
    width: 46vw;
    height: 46vw;
    max-width: 640px;
    max-height: 640px;
    top: -18%;
    right: -14%;
    background: radial-gradient(circle, rgba(47, 191, 151, 0.24), rgba(47, 191, 151, 0));
    animation: drift 26s ease-in-out infinite;
  }

  .a2 {
    width: 40vw;
    height: 40vw;
    max-width: 520px;
    max-height: 520px;
    bottom: -20%;
    left: -12%;
    background: radial-gradient(circle, rgba(242, 177, 52, 0.14), rgba(242, 177, 52, 0));
    animation: drift 32s ease-in-out infinite reverse;
  }

  /* 点阵纹理 */
  .dotgrid {
    position: absolute;
    inset: 0;
    background-image: radial-gradient(rgba(23, 23, 26, 0.085) 1px, transparent 1px);
    background-size: 22px 22px;
    mask-image: radial-gradient(72% 62% at 24% 26%, #000 0%, transparent 78%);
    -webkit-mask-image: radial-gradient(72% 62% at 24% 26%, #000 0%, transparent 78%);
    opacity: 0.5;
    pointer-events: none;
  }

  /* 跟随光标的光 */
  .spotlight {
    position: absolute;
    inset: 0;
    background: radial-gradient(
      460px circle at var(--mx) var(--my),
      rgba(18, 168, 130, 0.11),
      rgba(18, 168, 130, 0) 68%
    );
    opacity: 0;
    transition: opacity 500ms var(--ease-out-quart);
    pointer-events: none;
  }

  &.has-pointer .spotlight {
    opacity: 1;
  }

  .shapes {
    position: absolute;
    inset: 0;
    transform: translate3d(calc(var(--px, 0) * 10px), calc(var(--py, 0) * 8px), 0);
    transition: transform 720ms var(--ease-out-expo);
    will-change: transform;
    pointer-events: none;
  }

  .shape {
    position: absolute;
    display: block;
    animation: floatSoft 18s ease-in-out infinite;
    will-change: transform;
  }

  .s1 {
    width: 214px;
    height: 214px;
    top: -54px;
    right: -30px;
    opacity: 0.95;
    animation-delay: -2s;
  }

  .s2 {
    width: 230px;
    height: 230px;
    border: 1.5px solid rgba(11, 146, 116, 0.2);
    border-radius: 50%;
    left: -60px;
    bottom: -46px;
    animation-delay: -6s;
    animation-duration: 24s;
  }

  .s3 {
    width: 96px;
    height: 96px;
    right: 9%;
    bottom: -26px;
    opacity: 0.95;
    animation-delay: -9s;
    animation-duration: 21s;
  }

  .s4 {
    width: 54px;
    height: 54px;
    right: 11%;
    top: 27%;
    opacity: 0.82;
    animation-delay: -13s;
    animation-duration: 25s;
  }
}

/* ---------- 右栏文案 ---------- */
.brand-inner {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 560px;
  transform: translate3d(var(--cpx, 0px), var(--cpy, 0px), 0);
  transition: transform 760ms var(--ease-out-expo);
  will-change: transform;
}

.brand-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  margin: 0 0 26px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.16em;
  color: var(--ink-500);

  .pulse-dot {
    position: relative;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-500);

    &::after {
      content: '';
      position: absolute;
      inset: -4px;
      border-radius: 50%;
      border: 1px solid var(--accent-500);
      opacity: 0;
      animation: pulseRing 2.6s var(--ease-out-quart) infinite;
    }
  }
}

.brand-title {
  margin: 0;
  font-size: clamp(42px, 4.5vw, 74px);
  line-height: 1.06;
  font-weight: 750;
  letter-spacing: -0.035em;
  color: var(--ink-950);

  .line {
    display: block;
    overflow: hidden;
    padding-bottom: 0.06em;

    &:last-child {
      margin-top: 0.04em;
    }
  }

  .line-inner {
    display: inline-block;
    transform: translateY(105%);
  }

  .is-ready & .line:nth-child(1) .line-inner {
    animation: lineUp 900ms var(--ease-out-expo) 240ms both;
  }

  .is-ready & .line:nth-child(2) .line-inner {
    animation: lineUp 900ms var(--ease-out-expo) 370ms both;
  }

  em {
    position: relative;
    display: inline-block;
    font-style: normal;
    z-index: 0;

    &::before {
      content: '';
      position: absolute;
      left: -0.06em;
      right: -0.06em;
      bottom: 0.1em;
      height: 0.34em;
      background: linear-gradient(90deg, #b8ecdc 0%, #d7f4ea 100%);
      border-radius: 3px;
      z-index: -1;
      transform: scaleX(0);
      transform-origin: left center;
    }

    .is-ready .brand-title &::before {
      animation: markerDraw 780ms var(--ease-out-expo) 880ms forwards;
    }
  }
}

.brand-lede {
  margin: 30px 0 0;
  max-width: 452px;
  font-size: 14.5px;
  line-height: 1.78;
  letter-spacing: 0.004em;
  text-wrap: pretty;
  color: var(--ink-600);
}

.metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 22px;
  margin: 44px 0 0;
  padding: 22px 0 0;
  list-style: none;
  border-top: 1px solid rgba(23, 23, 26, 0.1);
  max-width: 470px;

  li {
    display: flex;
    flex-direction: column;
    gap: 6px;
    transition: transform 320ms var(--ease-out-quart);

    &:hover {
      transform: translateY(-2px);

      strong {
        color: var(--accent-700);
      }
    }

    strong {
      font-size: 13.5px;
      font-weight: 600;
      letter-spacing: -0.005em;
      color: var(--ink-900);
      transition: color 240ms var(--ease-out-quart);
    }

    span {
      font-size: 12px;
      line-height: 1.5;
      color: var(--ink-500);
    }
  }
}

/* ==================== 入场编排 ==================== */
.login-page:not(.is-ready) .reveal {
  opacity: 0;
}

.is-ready .reveal {
  animation: riseIn 760ms var(--ease-out-expo) both;
  animation-delay: var(--d, 0ms);
}

.login-page:not(.is-ready) .auth-head,
.login-page:not(.is-ready) .seg,
.login-page:not(.is-ready) .form-wrap,
.login-page:not(.is-ready) .auth-foot {
  opacity: 0;
}

.is-ready .auth-head,
.is-ready .seg,
.is-ready .form-wrap,
.is-ready .auth-foot {
  animation: riseIn 700ms var(--ease-out-expo) both;
}

.is-ready .auth-head {
  animation-delay: 80ms;
}
.is-ready .seg {
  animation-delay: 150ms;
}
.is-ready .form-wrap {
  animation-delay: 210ms;
}
.is-ready .auth-foot {
  animation-delay: 380ms;
}

/* 切换时表单内部逐项上浮 */
.is-ready .auth-block > .auth-form > .field,
.is-ready .auth-block > .auth-form > .form-row,
.is-ready .auth-block > .auth-form > .primary-btn {
  animation: riseIn 520ms var(--ease-out-expo) both;
}

.is-ready .auth-block > .auth-form > *:nth-child(1) {
  animation-delay: 40ms;
}
.is-ready .auth-block > .auth-form > *:nth-child(2) {
  animation-delay: 90ms;
}
.is-ready .auth-block > .auth-form > *:nth-child(3) {
  animation-delay: 140ms;
}
.is-ready .auth-block > .auth-form > *:nth-child(4) {
  animation-delay: 190ms;
}
.is-ready .auth-block > .auth-form > *:nth-child(5) {
  animation-delay: 240ms;
}

/* ==================== 过渡 ==================== */
.swap-enter-active {
  transition:
    opacity 300ms var(--ease-out-quart),
    transform 400ms var(--ease-out-expo),
    filter 280ms linear;
}

.swap-leave-active {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  pointer-events: none;
  transition:
    opacity 180ms linear,
    transform 240ms var(--ease-out-quart),
    filter 180ms linear;
}

.swap-enter-from {
  opacity: 0;
  transform: translateY(10px);
  filter: blur(3px);
}

.swap-leave-to {
  opacity: 0;
  transform: translateY(-6px);
  filter: blur(3px);
}

.msg-enter-active {
  transition:
    opacity 220ms var(--ease-out-quart),
    transform 260ms var(--ease-out-expo);
}

.msg-leave-active {
  transition:
    opacity 120ms linear,
    transform 140ms linear;
}

.msg-enter-from {
  opacity: 0;
  transform: translateY(-4px);
}

.msg-leave-to {
  opacity: 0;
  transform: translateY(-3px);
}

/* ==================== 关键帧 ==================== */
@keyframes riseIn {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes lineUp {
  from {
    transform: translateY(105%);
  }
  to {
    transform: translateY(0);
  }
}

@keyframes markerDraw {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

@keyframes floatSoft {
  0%,
  100% {
    transform: translate3d(0, 0, 0) rotate(0deg);
  }
  50% {
    transform: translate3d(0, -18px, 0) rotate(4deg);
  }
}

@keyframes drift {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(-4%, 5%, 0) scale(1.08);
  }
}

@keyframes pulseRing {
  0% {
    opacity: 0.8;
    transform: scale(0.6);
  }
  70% {
    opacity: 0;
    transform: scale(1.5);
  }
  100% {
    opacity: 0;
    transform: scale(1.5);
  }
}

@keyframes btnShine {
  from {
    left: -40%;
  }
  to {
    left: 120%;
  }
}

@keyframes ripple {
  from {
    opacity: 1;
    transform: scale(0.4);
  }
  to {
    opacity: 0;
    transform: scale(22);
  }
}

@keyframes dotPulse {
  0%,
  100% {
    opacity: 0.25;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

@keyframes checkDraw {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes fieldShake {
  0%,
  100% {
    transform: translateX(0);
  }
  18% {
    transform: translateX(-5px);
  }
  38% {
    transform: translateX(4px);
  }
  58% {
    transform: translateX(-3px);
  }
  78% {
    transform: translateX(2px);
  }
}

/* ==================== 第三方登录适配 ==================== */
:deep(.de-other-login-divider) {
  margin: 26px 0 16px;
  border-color: var(--ink-150);
  color: var(--ink-400);
  font-size: 11.5px;
}

:deep(.login-list) {
  justify-content: center;
  gap: 12px;
}

/* ==================== 响应式 ==================== */
@media (max-width: 1220px) {
  .brand-title {
    font-size: clamp(38px, 4.2vw, 58px);
  }

  .metrics {
    grid-template-columns: 1fr 1fr;
    max-width: 380px;

    li:last-child {
      display: none;
    }
  }
}

@media (max-width: 1080px) {
  .brand-pane {
    display: none;
  }

  .auth-pane {
    flex: 1;
    max-width: none;
    min-width: 0;
    padding: 32px 40px 24px;
  }

  .auth-inner {
    max-width: 400px;
  }
}

@media (max-width: 480px) {
  .auth-pane {
    padding: 24px 22px 18px;
  }

  .register-form .form-row {
    grid-template-columns: 1fr;
  }

  .register-form .form-row .strength {
    order: 2;
  }

  .register-form .form-row .field:nth-child(2) {
    order: 3;
  }

  .auth-body {
    padding: 24px 0 48px;
  }

  .auth-head .auth-title {
    font-size: 29px;
  }

  .brand-row .brand-badge {
    display: none;
  }
}

/* 尊重「减少动态效果」偏好 */
@media (prefers-reduced-motion: reduce) {
  .login-page *,
  .login-page *::before,
  .login-page *::after {
    animation-duration: 0.001ms !important;
    animation-delay: 0ms !important;
    transition-duration: 0.001ms !important;
  }
}

.hide-login-container {
  display: none;
}

.xpack-login-handler-mask {
  position: fixed;
  width: 100vw;
  height: 100vh;
  left: 0;
  top: 0;
  z-index: 999;
}
</style>
