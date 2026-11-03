<script lang="ts" setup>
import { ref, computed, nextTick, onUnmounted, watch } from 'vue'
import Menu from './Menu.vue'
import custom_small from '@/assets/svg/logo-custom_small.svg'
import Workspace from './Workspace.vue'
import Person from './Person.vue'
import LOGO_fold from '@/assets/LOGO-fold.svg'
import icon_moments_categories_outlined from '@/assets/svg/icon_moments-categories_outlined.svg'
import icon_side_fold_outlined from '@/assets/svg/icon_side-fold_outlined.svg'
import icon_side_expand_outlined from '@/assets/svg/icon_side-expand_outlined.svg'
import { useRoute, useRouter } from 'vue-router'
import { useAppearanceStoreWithOut } from '@/stores/appearance'
import { useEmitt } from '@/utils/useEmitt'
import { Menu as MenuIcon } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()
const collapse = ref(false)
const collapseCopy = ref(false)
const mobileNavigationOpen = ref(false)
const mobileNavigation = ref<HTMLElement | null>(null)
const mobileNavigationTrigger = ref<HTMLButtonElement | null>(null)
const isCollapsed = computed(() => collapseCopy.value && !mobileNavigationOpen.value)
const appearanceStore = useAppearanceStoreWithOut()
let time: any
onUnmounted(() => {
  clearTimeout(time)
})
const loginBg = computed(() => {
  return appearanceStore.getLogin
})
const handleCollapseChange = (val: any = true) => {
  collapseCopy.value = val
  clearTimeout(time)
  time = setTimeout(() => {
    collapse.value = val
  }, 100)
}
useEmitt({
  name: 'collapse-change',
  callback: handleCollapseChange,
})
const handleFoldExpand = () => {
  handleCollapseChange(!collapse.value)
}

const toWorkspace = () => {
  router.push('/')
}

const toChatIndex = () => {
  router.push('/chat/index')
}

const toUserIndex = () => {
  router.push('/system/user')
}
const route = useRoute()
const showSysmenu = computed(() => {
  return route.path.includes('/system')
})
watch(
  () => route.fullPath,
  () => {
    mobileNavigationOpen.value = false
  }
)
const closeMobileNavigation = () => {
  mobileNavigationOpen.value = false
}
const toggleMobileNavigation = () => {
  mobileNavigationOpen.value = !mobileNavigationOpen.value
}
const handleMobileNavigationKeydown = (event: KeyboardEvent) => {
  if (!window.matchMedia('(max-width: 767px)').matches || event.key !== 'Tab') {
    return
  }

  const focusableItems = Array.from(
    mobileNavigation.value?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    ) || []
  ).filter((element) => element.getClientRects().length > 0)
  const firstItem = focusableItems[0]
  const lastItem = focusableItems[focusableItems.length - 1]

  if (!firstItem || !lastItem) {
    event.preventDefault()
    return
  }
  if (event.shiftKey && document.activeElement === firstItem) {
    event.preventDefault()
    lastItem.focus()
  } else if (!event.shiftKey && document.activeElement === lastItem) {
    event.preventDefault()
    firstItem.focus()
  }
}

watch(mobileNavigationOpen, async (isOpen) => {
  await nextTick()
  if (isOpen) {
    const firstItem = mobileNavigation.value?.querySelector<HTMLElement>(
      'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
    )
    firstItem?.focus()
  } else if (window.matchMedia('(max-width: 767px)').matches) {
    mobileNavigationTrigger.value?.focus()
  }
})
</script>

<template>
  <div class="system-layout" @keydown.esc="closeMobileNavigation">
    <aside
      id="primary-navigation"
      ref="mobileNavigation"
      :role="mobileNavigationOpen ? 'dialog' : 'navigation'"
      :aria-label="t('common.navigation_menu')"
      :aria-modal="mobileNavigationOpen ? 'true' : undefined"
      class="left-side"
      :class="{ 'left-side-collapse': isCollapsed, 'mobile-nav-open': mobileNavigationOpen }"
      @keydown="handleMobileNavigationKeydown"
    >
      <template v-if="showSysmenu">
        <button
          type="button"
          class="sys-management"
          :aria-label="$t('training.system_management')"
          @click="toUserIndex"
        >
          <img
            v-if="loginBg"
            :style="{ marginLeft: isCollapsed ? '5px' : 0 }"
            height="30"
            width="30"
            :src="loginBg"
            :class="!isCollapsed && 'collapse-icon'"
            alt=""
          />
          <custom_small
            v-else-if="appearanceStore.themeColor !== 'default'"
            :style="{ marginLeft: isCollapsed ? '5px' : 0 }"
            :class="!isCollapsed && 'collapse-icon'"
          ></custom_small>
          <LOGO_fold
            v-else
            :style="{ marginLeft: isCollapsed ? '5px' : 0 }"
            :class="!isCollapsed && 'collapse-icon'"
          ></LOGO_fold>
          <span v-if="!isCollapsed">{{ $t('training.system_management') }}</span>
        </button>
      </template>
      <template v-else>
        <button
          type="button"
          class="default-sqlbot"
          :aria-label="appearanceStore.name || t('common.open_chat')"
          :title="appearanceStore.name || t('common.open_chat')"
          @click="toChatIndex"
        >
          <img v-if="loginBg" :src="loginBg" class="brand-icon" alt="" />
          <custom_small
            v-else-if="appearanceStore.themeColor !== 'default'"
            class="brand-icon"
          ></custom_small>
          <LOGO_fold v-else class="brand-icon"></LOGO_fold>
          <span
            v-if="!isCollapsed"
            :style="{ maxWidth: '150px' }"
            :title="appearanceStore.name"
            class="ellipsis"
            >{{ appearanceStore.name }}</span
          >
        </button>
      </template>
      <Workspace v-if="!showSysmenu" :collapse="isCollapsed"></Workspace>
      <Menu :collapse="isCollapsed"></Menu>
      <div class="bottom">
        <button
          type="button"
          v-if="showSysmenu"
          class="back-to_workspace"
          :class="isCollapsed && 'collapse'"
          :aria-label="$t('workspace.return_to_workspace')"
          @click="toWorkspace"
        >
          <el-icon size="18">
            <icon_moments_categories_outlined></icon_moments_categories_outlined>
          </el-icon>
          {{ isCollapsed ? '' : $t('workspace.return_to_workspace') }}
        </button>
        <div class="personal-info">
          <Person :collapse="isCollapsed" :in-sysmenu="showSysmenu"></Person>
          <el-button
            text
            circle
            size="large"
            class="fold"
            :aria-label="t(collapse ? 'common.expand_navigation' : 'common.collapse_navigation')"
            :title="t(collapse ? 'common.expand_navigation' : 'common.collapse_navigation')"
            :aria-expanded="!collapse"
            @click="handleFoldExpand"
          >
            <icon_side_expand_outlined v-if="collapse"></icon_side_expand_outlined>
            <icon_side_fold_outlined v-else></icon_side_fold_outlined>
          </el-button>
        </div>
      </div>
    </aside>
    <button
      v-if="mobileNavigationOpen"
      class="mobile-navigation-backdrop"
      type="button"
      :aria-label="t('common.close_navigation')"
      @click="closeMobileNavigation"
    />
    <div class="right-main" :class="isCollapsed && 'right-side-collapse'">
      <div class="mobile-topbar">
        <button
          class="mobile-nav-trigger"
          ref="mobileNavigationTrigger"
          type="button"
          :aria-label="t('common.toggle_navigation')"
          :title="t('common.toggle_navigation')"
          :aria-expanded="mobileNavigationOpen"
          aria-controls="primary-navigation"
          @click="toggleMobileNavigation"
        >
          <el-icon size="20"><MenuIcon /></el-icon>
        </button>
      </div>
      <div class="content">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </div>
  </div>
</template>

<style lang="less" scoped>
.system-layout {
  width: 100%;
  height: 100vh;
  background-color: var(--ink-50);
  display: flex;
  overflow: hidden;

  @keyframes rotate {
    0% {
      width: 240px;
    }
    100% {
      width: 64px;
    }
  }

  .left-side {
    width: 240px;
    flex: 0 0 240px;
    height: 100%;
    padding: 16px;
    position: relative;
    min-width: 240px;

    > button {
      border: 0;
      padding: 0;
      color: inherit;
      background: transparent;
      text-align: left;
      cursor: pointer;
    }

    .default-sqlbot {
      display: flex;
      width: 100%;
      align-items: center;
      font-weight: 600;
      font-size: 16px;
      letter-spacing: var(--tracking-tight);
      cursor: pointer;
      margin-bottom: 14px;
      .collapse-icon {
        margin-right: 8px;
      }

      .brand-icon {
        width: 30px;
        height: 30px;
        flex-shrink: 0;
        margin-right: 8px;
      }
    }

    .sys-management {
      display: flex;
      width: 100%;
      align-items: center;
      font-weight: 600;
      font-size: 16px;
      letter-spacing: var(--tracking-tight);
      cursor: pointer;
      margin-bottom: 14px;
      .collapse-icon {
        margin-right: 8px;
      }
    }

    .bottom {
      position: absolute;
      bottom: 20px;
      left: 16px;
      font-weight: 400;
      font-size: 14px;
      line-height: 22px;
      width: calc(100% - 32px);
      .back-to_workspace {
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        height: 40px;
        width: 100%;
        padding: 0 8px;
        color: inherit;
        font: inherit;
        cursor: pointer;

        &:not(.collapse) {
          background: var(--ink-50);
          border: 1px solid var(--ink-200);
        }
        &:hover {
          background-color: var(--ink-100);
        }
        &:active {
          background-color: var(--ink-150);
        }
        .ed-icon {
          margin-right: 4.95px;
        }
      }

      .personal-info {
        display: flex;
        align-items: center;
        margin-top: 16px;

        .fold {
          cursor: pointer;
          margin-left: auto;
          border-radius: 6px;
          width: 40px;
          height: 40px;
          padding: 0;
          color: inherit;
          border: 0;
          &:hover,
          &:focus {
            background: var(--ink-100);
          }

          &:active {
            background: var(--ink-150);
          }
        }
      }
    }

    &.left-side-collapse {
      width: 64px;
      flex-basis: 64px;
      min-width: 64px;
      padding: 16px 12px;
      // animation: rotate 0.1s ease-in-out;

      .default-sqlbot {
        justify-content: center;

        .brand-icon {
          margin-right: 0;
        }
      }

      .ed-menu--collapse {
        --ed-menu-icon-width: 32px;
        width: 40px;
      }

      .bottom {
        left: 12px;
        width: calc(100% - 24px);
        .ed-icon {
          margin-right: 0;
        }
      }

      .personal-info {
        flex-wrap: wrap;

        .default-avatar {
          margin: 0 0 26px 4px;
        }

        .fold {
          margin: 0 auto;
        }
      }

      .sys-management {
        justify-content: flex-start;
      }
    }
  }

  .right-main {
    width: calc(100% - 240px);
    flex: 1 1 auto;
    min-width: 0;
    padding: 12px 12px 12px 0;
    max-height: 100vh;

    &.right-side-collapse {
      width: calc(100% - 64px);
    }

    .content {
      width: 100%;
      height: 100%;
      padding: 20px 28px;
      background-color: var(--paper);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-sm);
      overflow-x: auto;

      &:has(.no-padding) {
        padding: 0;
      }
    }
  }

  .mobile-topbar {
    display: none;
  }
}

.mobile-navigation-backdrop {
  display: none;
}

@media (max-width: 767px) {
  .system-layout {
    height: 100vh;
    height: 100dvh;

    .left-side,
    .left-side.left-side-collapse {
      position: fixed;
      z-index: 31;
      inset: 0 auto 0 0;
      width: min(280px, calc(100vw - 48px));
      min-width: 0;
      height: 100vh;
      height: 100dvh;
      padding: 16px;
      background: var(--ink-50);
      transform: translateX(-100%);
      visibility: hidden;
      transition:
        transform var(--dur-base) var(--ease-out-quart),
        visibility var(--dur-base) linear;

      &.mobile-nav-open {
        transform: translateX(0);
        visibility: visible;
        box-shadow: var(--shadow-md);
      }

      .default-sqlbot,
      .sys-management {
        justify-content: flex-start;
      }

      .workspace {
        width: 100%;
      }

      .ed-menu--collapse {
        width: 100%;
      }

      .bottom {
        left: 16px;
        width: calc(100% - 32px);
      }

      .personal-info {
        flex-wrap: nowrap;

        .default-avatar {
          margin: 0;
        }

        .fold {
          display: none;
        }
      }
    }

    .mobile-navigation-backdrop {
      display: block;
      position: fixed;
      inset: 0;
      z-index: 30;
      border: 0;
      background: rgba(11, 11, 13, 0.32);
    }

    .right-main,
    .right-main.right-side-collapse {
      width: 100%;
      max-height: 100vh;
      max-height: 100dvh;
      padding: 0;

      .mobile-topbar {
        display: flex;
        align-items: center;
        height: 48px;
        padding: 0 12px;
        background: var(--ink-50);
      }

      .mobile-nav-trigger {
        width: 40px;
        height: 40px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 1px solid var(--ink-200);
        border-radius: var(--radius-sm);
        color: var(--ink-800);
        background: var(--paper);
        cursor: pointer;

        &:focus-visible {
          outline: 2px solid var(--ed-color-primary);
          outline-offset: 2px;
        }
      }

      .content {
        height: calc(100% - 48px);
        padding: 12px;
        border-radius: 0;
        box-shadow: none;

        &:has(.no-padding) {
          padding: 0;
        }
      }
    }
  }
}

@media (prefers-reduced-motion: reduce) {
  .system-layout,
  .system-layout * {
    transition-duration: 0.01ms !important;
  }
}
</style>
