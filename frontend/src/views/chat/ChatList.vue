<script setup lang="ts">
import icon_more_outlined from '@/assets/svg/icon_more_outlined.svg'
import icon_expand_down_filled from '@/assets/embedded/icon_expand-down_filled.svg'
import rename from '@/assets/svg/icon_rename_outlined.svg'
import delIcon from '@/assets/svg/icon_delete.svg'
import { type Chat, chatApi, ChatInfo } from '@/api/chat.ts'
import { computed, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { getDate } from '@/utils/utils.ts'
import { groupBy, orderBy } from 'lodash-es'
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{
    currentChatId?: number
    chatList: Array<ChatInfo>
    loading?: boolean
    batchMode?: boolean
  }>(),
  {
    currentChatId: undefined,
    chatList: () => [],
    loading: false,
    batchMode: false,
  }
)

const { t } = useI18n()

function groupByDate(chat: Chat) {
  const todayStart = dayjs(dayjs().format('YYYY-MM-DD') + ' 00:00:00').toDate()
  const todayEnd = dayjs(dayjs().format('YYYY-MM-DD') + ' 23:59:59').toDate()
  const weekStart = dayjs(dayjs().subtract(7, 'day').format('YYYY-MM-DD') + ' 00:00:00').toDate()

  const time = getDate(chat.latest_record_time ?? chat.create_time)

  if (time) {
    if (time >= todayStart && time <= todayEnd) {
      return t('qa.today')
    }
    if (time < todayStart && time >= weekStart) {
      return t('qa.week')
    }
    if (time < weekStart) {
      return t('qa.earlier')
    }
  }

  return t('qa.no_time')
}

const computedChatGroup = computed(() => {
  return groupBy(
    orderBy(props.chatList, [(c: Chat) => c.latest_record_time ?? c.create_time], ['desc']),
    groupByDate
  )
})

const expandMap = ref({
  [t('qa.today')]: true,
  [t('qa.week')]: true,
  [t('qa.earlier')]: true,
  [t('qa.no_time')]: true,
})

const computedChatList = computed(() => {
  const _list = []
  if (computedChatGroup.value[t('qa.today')]) {
    _list.push({
      key: t('qa.today'),
      list: computedChatGroup.value[t('qa.today')],
    })
  }
  if (computedChatGroup.value[t('qa.week')]) {
    _list.push({
      key: t('qa.week'),
      list: computedChatGroup.value[t('qa.week')],
    })
  }
  if (computedChatGroup.value[t('qa.earlier')]) {
    _list.push({
      key: t('qa.earlier'),
      list: computedChatGroup.value[t('qa.earlier')],
    })
  }
  if (computedChatGroup.value[t('qa.no_time')]) {
    _list.push({
      key: t('qa.no_time'),
      list: computedChatGroup.value[t('qa.no_time')],
    })
  }

  return _list
})

const emits = defineEmits([
  'chatSelected',
  'chatRenamed',
  'chatDeleted',
  'update:loading',
  'batchDelete',
  'update:batchMode',
])

const _loading = computed({
  get() {
    return props.loading
  },
  set(v) {
    emits('update:loading', v)
  },
})

function onClickHistory(chat: Chat) {
  if (props.batchMode) {
    toggleSelect(chat)
    return
  }
  emits('chatSelected', chat)
}

// ===== 批量删除逻辑 =====
const selectedIds = ref<Set<number>>(new Set())

const allIds = computed(() => {
  const ids: number[] = []
  props.chatList.forEach((c) => {
    if (c.id !== undefined) ids.push(c.id)
  })
  return ids
})

const isAllSelected = computed(() => {
  return allIds.value.length > 0 && allIds.value.every((id) => selectedIds.value.has(id))
})

function toggleSelect(chat: Chat) {
  if (chat.id === undefined) return
  const next = new Set(selectedIds.value)
  if (next.has(chat.id)) {
    next.delete(chat.id)
  } else {
    next.add(chat.id)
  }
  selectedIds.value = next
}

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(allIds.value)
  }
}

function clearSelection() {
  selectedIds.value = new Set()
}

function confirmBatchDelete() {
  if (selectedIds.value.size === 0) {
    ElMessage({ type: 'warning', message: t('qa.batch_delete_select_hint') })
    return
  }
  const count = selectedIds.value.size
  ElMessageBox.confirm(t('qa.batch_delete_confirm', { count }), {
    confirmButtonType: 'danger',
    tip: t('common.proceed_with_caution'),
    confirmButtonText: t('dashboard.delete'),
    cancelButtonText: t('common.cancel'),
    customClass: 'confirm-no_icon',
    autofocus: false,
  }).then(() => {
    _loading.value = true
    const ids = Array.from(selectedIds.value)
    let failed = 0
    Promise.all(
      ids.map((id) =>
        chatApi
          .deleteChat(id, undefined)
          .catch((err) => {
            failed++
            console.error(err)
          })
      )
    ).finally(() => {
      _loading.value = false
      if (failed === 0) {
        ElMessage({ type: 'success', message: t('dashboard.delete_success') })
      } else {
        ElMessage({ type: 'warning', message: t('qa.batch_delete_partial', { count: failed }) })
      }
      // 通知父组件批量删除完成，携带所有被删除的 id
      emits('batchDelete', ids)
      clearSelection()
    })
  })
}

function handleCommand(command: string | number | object, chat: Chat) {
  if (chat && chat.id !== undefined) {
    switch (command) {
      case 'rename':
        password.id = chat.id
        password.name = chat.brief as string
        dialogVisiblePassword.value = true
        break
      case 'delete':
        ElMessageBox.confirm(t('common.sales_in_2024', { msg: chat.brief }), {
          confirmButtonType: 'danger',
          tip: t('common.proceed_with_caution'),
          confirmButtonText: t('dashboard.delete'),
          cancelButtonText: t('common.cancel'),
          customClass: 'confirm-no_icon',
          autofocus: false,
        }).then(() => {
          _loading.value = true
          chatApi
            .deleteChat(chat.id, chat.brief)
            .then(() => {
              ElMessage({
                type: 'success',
                message: t('dashboard.delete_success'),
              })
              emits('chatDeleted', chat.id)
            })
            .catch((err) => {
              ElMessage({
                type: 'error',
                message: err.message,
              })
              console.error(err)
            })
            .finally(() => {
              _loading.value = false
            })
        })

        break
    }
  }
}

const passwordRef = ref()
const dialogVisiblePassword = ref(false)
const password = reactive({
  name: '',
  id: 0,
})

const passwordRules = {
  name: [
    {
      required: true,
      message: t('datasource.please_enter') + t('common.empty') + t('qa.conversation_title'),
      trigger: 'blur',
    },
  ],
}

const handleClosePassword = () => {
  passwordRef.value.clearValidate()
  dialogVisiblePassword.value = false
  password.id = 0
  password.name = ''
}
const handleConfirmPassword = () => {
  passwordRef.value.validate((res: any) => {
    if (res) {
      chatApi
        .renameChat(password.id, password.name)
        .then((res) => {
          ElMessage({
            type: 'success',
            message: t('common.save_success'),
          })
          emits('chatRenamed', { id: password.id, brief: res })
          handleClosePassword()
        })
        .catch((err) => {
          ElMessage({
            type: 'error',
            message: err.message,
          })
          console.error(err)
        })
        .finally(() => {
          _loading.value = false
        })
    }
  })
}
</script>

<template>
  <el-scrollbar ref="chatListRef">
    <div class="chat-list-inner flex-gap-fallback flex-col">
      <div v-for="group in computedChatList" :key="group.key" class="group">
        <div
          class="group-title"
          style="cursor: pointer"
          @click="expandMap[group.key] = !expandMap[group.key]"
        >
          <el-icon :class="!expandMap[group.key] && 'expand'" style="margin-right: 8px" size="10">
            <icon_expand_down_filled></icon_expand_down_filled>
          </el-icon>
          {{ group.key }}
        </div>
        <template v-for="chat in group.list" :key="chat.id">
          <div
            class="chat-list-item"
            :class="{
              active: currentChatId === chat.id,
              hide: !expandMap[group.key],
              'batch-mode': batchMode,
            }"
            @click="onClickHistory(chat)"
          >
            <el-checkbox
              v-if="batchMode"
              class="batch-check"
              :model-value="chat.id !== undefined && selectedIds.has(chat.id)"
              @click.stop
              @change="toggleSelect(chat)"
            />
            <span class="title">{{ chat.brief ?? 'Untitled' }}</span>
            <el-popover v-if="!batchMode" :teleported="false" popper-class="popover-card_chat" placement="bottom">
              <template #reference>
                <el-icon
                  class="more"
                  size="16"
                  style="margin-left: auto; color: #646a73"
                  @click.stop
                >
                  <icon_more_outlined></icon_more_outlined>
                </el-icon>
              </template>
              <div class="content">
                <div class="item" @click.stop="handleCommand('rename', chat)">
                  <el-icon size="16">
                    <rename></rename>
                  </el-icon>
                  {{ $t('dashboard.rename') }}
                </div>
                <div class="item" @click.stop="handleCommand('delete', chat)">
                  <el-icon size="16">
                    <delIcon></delIcon>
                  </el-icon>
                  {{ $t('dashboard.delete') }}
                </div>
              </div>
            </el-popover>
          </div>
        </template>
      </div>
    </div>
  </el-scrollbar>
  <div v-if="batchMode" class="batch-bar">
    <el-checkbox
      :model-value="isAllSelected"
      :indeterminate="selectedIds.size > 0 && !isAllSelected"
      @change="toggleSelectAll"
    >
      {{ $t('qa.batch_select_all') }}
    </el-checkbox>
    <span class="batch-count">{{ selectedIds.size }}</span>
    <div class="batch-actions">
      <el-button size="small" @click="emits('update:batchMode', false); clearSelection()">
        {{ $t('qa.batch_cancel') }}
      </el-button>
      <el-button size="small" type="danger" :disabled="selectedIds.size === 0" @click="confirmBatchDelete">
        {{ $t('dashboard.delete') }}
      </el-button>
    </div>
  </div>
  <el-dialog
    v-model="dialogVisiblePassword"
    :title="$t('qa.rename_conversation_title')"
    width="420"
    :before-close="handleClosePassword"
    append-to-body
  >
    <el-form
      ref="passwordRef"
      :model="password"
      label-width="180px"
      label-position="top"
      :rules="passwordRules"
      class="form-content_error"
      @submit.prevent
    >
      <el-form-item prop="name" :label="t('qa.conversation_title')">
        <el-input
          v-model="password.name"
          maxlength="20"
          :placeholder="
            $t('datasource.please_enter') + $t('common.empty') + $t('qa.conversation_title')
          "
          clearable
          autocomplete="off"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="dialog-footer">
        <el-button secondary @click="handleClosePassword">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleConfirmPassword">
          {{ $t('common.save') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped lang="less">
.chat-list-inner {
  --hover-color: var(--ed-color-primary-light-9);
  --active-color: var(--hover-color);

  padding-left: 16px;
  padding-right: 16px;
  width: 100%;

  display: flex;
  flex-direction: column;

  --gap-size: 16px;
  gap: 16px;

  .group {
    display: flex;
    flex-direction: column;

    .group-title {
      padding: 0 8px;
      color: rgba(100, 106, 115, 1);
      line-height: 20px;
      font-weight: 500;
      font-size: 12px;

      margin-bottom: 4px;

      .expand {
        transform: rotate(-90deg);
      }
    }
  }

  .chat-list-item {
    width: 100%;
    height: 40px;
    cursor: pointer;
    border-radius: 6px;
    line-height: 22px;
    font-size: 14px;
    font-weight: 400;
    margin-bottom: 2px;

    display: flex;
    align-items: center;
    padding: 8px;

    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;

    &.batch-mode {
      cursor: default;
      &:hover {
        background-color: rgba(31, 35, 41, 0.06);
      }
    }

    .batch-check {
      margin-right: 8px;
      flex-shrink: 0;
      :deep(.ed-checkbox__inner) {
        width: 16px;
        height: 16px;
      }
    }

    .title {
      flex: 1;
      width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .more {
      display: none;
      &.ed-icon {
        position: relative;
        cursor: pointer;
        margin-top: 4px;

        &::after {
          content: '';
          background-color: #1f23291a;
          position: absolute;
          border-radius: 6px;
          width: 24px;
          height: 24px;
          transform: translate(-50%, -50%);
          top: 50%;
          left: 50%;
          display: none;
        }

        &:hover {
          &::after {
            display: block;
          }
        }
      }
    }

    &:hover {
      background-color: rgba(31, 35, 41, 0.1);

      .more {
        display: block;
      }
    }

    &.active {
      background-color: rgba(255, 255, 255, 1);
      font-weight: 500;
    }

    &.hide {
      display: none;
    }
  }
}

.batch-bar {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 1);
  border-top: 1px solid #dee0e3;
  gap: 8px;

  .batch-count {
    color: #646a73;
    font-size: 13px;
    min-width: 20px;
  }

  .batch-actions {
    margin-left: auto;
    display: flex;
    gap: 8px;
  }
}
</style>

<style lang="less">
.popover-card_chat.popover-card_chat.popover-card_chat {
  box-shadow: 0px 4px 8px 0px #1f23291a;
  border-radius: 6px;
  border: 1px solid #dee0e3;
  width: fit-content !important;
  min-width: 120px !important;
  padding: 0;
  .content {
    position: relative;
    &::after {
      position: absolute;
      content: '';
      top: 40px;
      left: 0;
      width: 100%;
      height: 1px;
      background: #dee0e3;
    }
    .item {
      position: relative;
      padding: 0 12px;
      height: 40px;
      display: flex;
      align-items: center;
      cursor: pointer;
      .ed-icon {
        margin-right: 8px;
        color: #646a73;
      }
      &:hover {
        &::after {
          display: block;
        }
      }

      &::after {
        content: '';
        width: calc(100% - 8px);
        height: 32px;
        border-radius: 6px;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: #1f23291a;
        display: none;
      }
    }
  }
}
</style>
