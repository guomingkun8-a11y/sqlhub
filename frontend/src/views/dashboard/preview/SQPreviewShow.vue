<script setup lang="ts">
import icon_add_outlined from '@/assets/svg/icon_add_outlined.svg'
import {
  reactive,
  ref,
  toRefs,
  onBeforeMount,
  onMounted,
  onBeforeUnmount,
  computed,
  nextTick,
  watch,
  type ComponentPublicInstance,
} from 'vue'
import { load_resource_prepare } from '@/views/dashboard/utils/canvasUtils'
import { Icon } from '@/components/icon-custom'
import ResourceTree from '@/views/dashboard/common/ResourceTree.vue'
import SQPreview from '@/views/dashboard/preview/SQPreview.vue'
import SQPreviewHead from '@/views/dashboard/preview/SQPreviewHead.vue'
import EmptyBackground from '@/views/dashboard/common/EmptyBackground.vue'
import EmptyBackgroundSvg from '@/views/dashboard/common/EmptyBackgroundSvg.vue'
import { dashboardStoreWithOut } from '@/stores/dashboard/dashboard.ts'
import { Menu as MenuIcon } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
const dashboardStore = dashboardStoreWithOut()
const previewCanvasContainer = ref(null)
const dashboardPreview = ref(null)
const mobileViewport = window.matchMedia('(max-width: 767px)')
const slideShow = ref(!mobileViewport.matches)
const resourceTree = ref<ComponentPublicInstance | null>(null)
const resourceTreeToggle = ref<HTMLButtonElement | null>(null)
const resourceTreeElement = () => resourceTree.value?.$el as HTMLElement | undefined
const dataInitState = ref(true)
const state = reactive({
  canvasDataPreview: [],
  canvasStylePreview: {},
  canvasViewInfoPreview: {},
  dashboardInfo: {} as { name?: string },
})

const props = defineProps({
  showPosition: {
    required: false,
    type: String,
    default: 'preview',
  },
  noClose: {
    required: false,
    type: Boolean,
    default: false,
  },
})

const { showPosition } = toRefs(props)

const resourceTreeRef = ref()

const hasTreeData = computed(() => {
  return resourceTreeRef.value?.hasData
})
const mounted = computed(() => {
  return resourceTreeRef.value?.mounted
})
function createNew() {
  resourceTreeRef.value?.createNewObject()
}

const stateInit = () => {
  state.canvasDataPreview = []
  state.canvasStylePreview = {}
  state.canvasViewInfoPreview = {}
  state.dashboardInfo = {}
}
const loadCanvasData = (params: any) => {
  dataInitState.value = false
  load_resource_prepare(
    { id: params.id },
    function ({ dashboardInfo, canvasDataResult, canvasStyleResult, canvasViewInfoPreview }) {
      state.canvasDataPreview = canvasDataResult
      state.canvasStylePreview = canvasStyleResult
      state.canvasViewInfoPreview = canvasViewInfoPreview
      state.dashboardInfo = dashboardInfo
      dataInitState.value = true
    }
  )
}
const getPreviewStateInfo = () => {
  return state
}

const reload = (params: any) => {
  loadCanvasData(params)
}

const resourceNodeClick = (prams: any) => {
  loadCanvasData(prams)
  if (mobileViewport.matches) {
    slideShow.value = false
  }
}

const previewShowFlag = computed(() => !!state.dashboardInfo?.name)

onBeforeMount(() => {
  if (showPosition.value === 'preview') {
    dashboardStore.canvasDataInit()
  }
})
const sideTreeStatus = ref(true)
const toggleResourceTree = () => {
  slideShow.value = !slideShow.value
}
const closeResourceTree = () => {
  if (mobileViewport.matches) {
    slideShow.value = false
  }
}
const handleResourceTreeKeydown = (event: KeyboardEvent) => {
  if (!mobileViewport.matches || event.key !== 'Tab') {
    return
  }

  const focusableItems = Array.from(
    resourceTreeElement()?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    ) || []
  ).filter((element) => element.getClientRects().length > 0)
  const firstItem = focusableItems[0]
  const lastItem = focusableItems[focusableItems.length - 1]

  if (!firstItem || !lastItem) {
    event.preventDefault()
  } else if (event.shiftKey && document.activeElement === firstItem) {
    event.preventDefault()
    lastItem.focus()
  } else if (!event.shiftKey && document.activeElement === lastItem) {
    event.preventDefault()
    firstItem.focus()
  }
}
const syncResourceTreeVisibility = (event: MediaQueryListEvent) => {
  slideShow.value = !event.matches
}

watch(slideShow, async (isOpen) => {
  if (!mobileViewport.matches) {
    return
  }
  await nextTick()
  if (isOpen) {
    const firstItem = resourceTreeElement()?.querySelector<HTMLElement>(
      'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
    )
    firstItem?.focus()
  } else {
    resourceTreeToggle.value?.focus()
  }
})

onMounted(() => {
  mobileViewport.addListener(syncResourceTreeVisibility)
})
onBeforeUnmount(() => {
  mobileViewport.removeListener(syncResourceTreeVisibility)
})
const resourceTreeAction = computed(() =>
  slideShow.value ? 'dashboard.close_resource_tree' : 'dashboard.open_resource_tree'
)
const closeResourceTreeLabel = computed(() => t('dashboard.close_resource_tree'))
const handleEscape = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    closeResourceTree()
  }
}
defineExpose({
  getPreviewStateInfo,
})
</script>

<template>
  <div class="dashboard-workspace no-padding" @keydown="handleEscape">
    <div class="dashboard-mobile-toolbar">
      <button
        ref="resourceTreeToggle"
        type="button"
        :aria-label="t(resourceTreeAction)"
        :title="t(resourceTreeAction)"
        :aria-expanded="slideShow"
        aria-controls="dashboard-resource-tree"
        @click="toggleResourceTree"
      >
        <el-icon size="18"><MenuIcon /></el-icon>
      </button>
      <span class="dashboard-mobile-title ellipsis">
        {{ state.dashboardInfo.name || t('menu.Dashboard') }}
      </span>
    </div>
    <div class="dv-preview dv-teleport-query no-padding">
      <el-aside
        id="dashboard-resource-tree"
        ref="resourceTree"
        :role="slideShow && mobileViewport.matches ? 'dialog' : 'complementary'"
        :aria-modal="slideShow && mobileViewport.matches ? 'true' : undefined"
        :aria-label="t('dashboard.resource_tree')"
        class="resource-area"
        :class="{ 'close-side': !slideShow, retract: !sideTreeStatus }"
        @keydown="handleResourceTreeKeydown"
      >
        <resource-tree
          v-show="slideShow"
          ref="resourceTreeRef"
          :cur-canvas-type="'dashboard'"
          :show-position="showPosition"
          @node-click="resourceNodeClick"
          @delete-cur-resource="stateInit"
        />
      </el-aside>
      <button
        v-if="slideShow"
        class="dashboard-tree-backdrop"
        type="button"
        :aria-label="closeResourceTreeLabel"
        @click="closeResourceTree"
      />
      <el-container
        v-loading="!dataInitState"
        class="preview-area"
        :class="{ 'no-data': !state.dashboardInfo }"
      >
        <template v-if="previewShowFlag">
          <SQPreviewHead :dashboard-info="state.dashboardInfo" @reload="reload" />
          <div id="sq-preview-content" ref="previewCanvasContainer" class="content">
            <SQPreview
              v-if="state.canvasStylePreview && dataInitState"
              ref="dashboardPreview"
              :dashboard-info="state.dashboardInfo"
              :component-data="state.canvasDataPreview"
              :canvas-style-data="state.canvasStylePreview"
              :canvas-view-info="state.canvasViewInfoPreview"
              :show-position="showPosition"
            ></SQPreview>
          </div>
        </template>
        <template v-else-if="hasTreeData && mounted">
          <EmptyBackgroundSvg :description="t('dashboard.select_dashboard_tips')" />
        </template>
        <template v-else-if="mounted">
          <EmptyBackground :description="t('dashboard.no_dashboard_info')" img-type="none">
            <el-button type="primary" @click="createNew">
              <template #icon>
                <Icon name="icon_add_outlined">
                  <icon_add_outlined class="svg-icon" />
                </Icon>
              </template>
              {{ t('dashboard.new_dashboard') }}
            </el-button>
          </EmptyBackground>
        </template>
      </el-container>
    </div>
  </div>
</template>

<style lang="less">
.dashboard-workspace {
  width: 100%;
  height: 100%;
  min-width: 0;

  .dashboard-mobile-toolbar {
    display: none;
  }
}

.dv-preview {
  width: 100%;
  height: 100%;
  overflow: hidden;
  display: flex;
  background: #ffffff;
  position: relative;
  border-radius: 12px;

  .resource-area {
    --ed-aside-width: 260px;

    position: relative;
    height: 100%;
    padding: 0;

    box-shadow: 0 0 3px #d7d7d7;
    z-index: 1;

    overflow: visible;

    &.retract {
      display: none;
    }
  }

  .preview-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow-x: hidden;
    overflow-y: auto;
    position: relative;
    //transition: 0.5s;

    &.no-data {
      background-color: rgba(245, 246, 247, 1);
    }

    .content {
      position: relative;
      display: flex;
      width: 100%;
      height: 100%;
      overflow-x: hidden;
      overflow-y: auto;
      align-items: center;
    }
  }
}

.dashboard-tree-backdrop {
  display: none;
}

.close-side {
  width: 0 !important;
  padding: 0 !important;
}

.flexible-button-area {
  position: absolute;
  height: 60px;
  width: 16px;
  left: 0;
  top: calc(50% - 30px);
  background-color: #ffffff;
  border-radius: 0 4px 4px 0;
  cursor: pointer;
  z-index: 10;
  display: flex;
  align-items: center;
  border-top: 1px solid #d7d7d7;
  border-right: 1px solid #d7d7d7;
  border-bottom: 1px solid #d7d7d7;
}

@media (max-width: 767px) {
  .dashboard-workspace {
    display: flex;
    flex-direction: column;

    .dashboard-mobile-toolbar {
      height: 48px;
      flex: 0 0 48px;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 0 12px;
      background: var(--ink-50);

      button {
        width: 40px;
        height: 40px;
        flex: 0 0 40px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 1px solid var(--ink-200);
        border-radius: var(--radius-sm);
        color: var(--ink-800);
        background: var(--paper);
        cursor: pointer;
      }

      .dashboard-mobile-title {
        min-width: 0;
        font-weight: 600;
        color: var(--ink-800);
      }
    }
  }

  .dv-preview {
    flex: 1 1 auto;
    min-height: 0;
    border-radius: 0;

    .resource-area {
      --ed-aside-width: min(280px, calc(100vw - 56px));

      position: absolute;
      inset: 0 auto 0 0;
      width: var(--ed-aside-width);
      z-index: 5;
      background: var(--paper);
      box-shadow: var(--shadow-md);

      &.close-side {
        visibility: hidden;
        box-shadow: none;
      }
    }

    .dashboard-tree-backdrop {
      display: block;
      position: absolute;
      inset: 0;
      z-index: 4;
      border: 0;
      background: rgba(11, 11, 13, 0.32);
    }

    .preview-area {
      width: 100%;
      min-width: 0;
    }
  }
}
</style>
