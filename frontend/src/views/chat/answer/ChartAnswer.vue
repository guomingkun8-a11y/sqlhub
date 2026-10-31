<script setup lang="ts">
import BaseAnswer from './BaseAnswer.vue'
import { Chat, chatApi, ChatInfo, type ChatMessage, ChatRecord, questionApi } from '@/api/chat.ts'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import ChartBlock from '@/views/chat/chat-block/ChartBlock.vue'
import MdComponent from '@/views/chat/component/MdComponent.vue'
import JSONBig from 'json-bigint'
import { useI18n } from 'vue-i18n'

const props = withDefaults(
  defineProps<{
    recordId?: number
    chatList?: Array<ChatInfo>
    currentChatId?: number
    currentChat?: ChatInfo
    message?: ChatMessage
    loading?: boolean
    agentMode?: boolean
    reasoningName: 'sql_answer' | 'chart_answer' | Array<'sql_answer' | 'chart_answer'>
  }>(),
  {
    recordId: undefined,
    chatList: () => [],
    currentChatId: undefined,
    currentChat: () => new ChatInfo(),
    message: undefined,
    loading: false,
    agentMode: false,
  }
)

const emits = defineEmits([
  'finish',
  'error',
  'stop',
  'scrollBottom',
  'update:loading',
  'update:chatList',
  'update:currentChat',
  'update:currentChatId',
])
const { t } = useI18n()
const agentSteps = computed(() => props.message?.record?.agent_steps?.slice(0, 4) ?? [])

const index = computed(() => {
  if (props.message?.index) {
    return props.message.index
  }
  if (props.message?.index === 0) {
    return 0
  }
  return -1
})

const _currentChatId = computed({
  get() {
    return props.currentChatId
  },
  set(v) {
    emits('update:currentChatId', v)
  },
})

const _currentChat = computed({
  get() {
    return props.currentChat
  },
  set(v) {
    emits('update:currentChat', v)
  },
})

const _chatList = computed({
  get() {
    return props.chatList
  },
  set(v) {
    emits('update:chatList', v)
  },
})

const _loading = computed({
  get() {
    return props.loading
  },
  set(v) {
    emits('update:loading', v)
  },
})

const stopFlag = ref(false)
let activeController: AbortController | undefined

const sendMessage = async () => {
  stopFlag.value = false
  _loading.value = true

  if (index.value < 0) {
    _loading.value = false
    return
  }

  const currentRecord: ChatRecord = _currentChat.value.records[index.value]

  let error: boolean = false
  if (_currentChatId.value === undefined) {
    error = true
  }
  if (error) {
    _loading.value = false
    emits('error', currentRecord.id)
    return
  }

  const controller = new AbortController()
  activeController = controller
  try {
    _currentChat.value.latest_record_time = new Date()
    _chatList.value.forEach((c: Chat) => {
      if (c.id === _currentChat.value.id) {
        c.latest_record_time = _currentChat.value.latest_record_time
      }
    })

    const param = {
      question: currentRecord.question,
      chat_id: _currentChatId.value,
      ...(props.agentMode && {
        agent_mode: true,
        time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        ...(currentRecord.source_record_id && { source_record_id: currentRecord.source_record_id }),
      }),
    }
    const response = await questionApi.add(param, controller)
    if (!response.ok) {
      throw new Error(`${t('qa.ask_failed')} (HTTP ${response.status})`)
    }
    if (!response.body) {
      throw new Error(t('qa.ask_failed'))
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')

    let sql_answer = ''
    let chart_answer = ''
    let answer = ''
    let terminalEvent = false

    let tempResult = ''

    while (true) {
      if (stopFlag.value) {
        controller.abort()
        break
      }

      const { done, value } = await reader.read()
      if (done) {
        if (!terminalEvent) {
          throw new Error(t('qa.ask_failed'))
        }
        break
      }

      let chunk = decoder.decode(value, { stream: true })
      tempResult += chunk
      const split = tempResult.match(/data:.*}\n\n/g)
      if (split) {
        chunk = split.join('')
        tempResult = tempResult.replace(chunk, '')
      } else {
        continue
      }
      if (chunk && chunk.startsWith('data:{')) {
        if (split) {
          for (const str of split) {
            let data
            try {
              data = JSONBig.parse(str.replace('data:{', '{'))
            } catch (err) {
              console.error('JSON string:', str)
              throw err
            }

            if (data.code && data.code !== 200) {
              terminalEvent = true
              currentRecord.error = data.msg ?? t('qa.ask_failed')
              ElMessage({
                message: currentRecord.error,
                type: 'error',
                showClose: true,
              })
              emits('error', currentRecord.id)
              controller.abort()
              return
            }

            switch (data.type) {
              case 'id':
                currentRecord.id = data.id
                _currentChat.value.records[index.value].id = data.id
                break
              case 'regenerate_record_id':
                currentRecord.regenerate_record_id = data.regenerate_record_id
                _currentChat.value.records[index.value].regenerate_record_id =
                  data.regenerate_record_id
                break
              case 'question':
                currentRecord.question = data.question
                _currentChat.value.records[index.value].question = data.question
                break
              case 'info':
                console.info(data.msg)
                break
              case 'brief':
                _currentChat.value.brief = data.brief
                _chatList.value.forEach((c: Chat) => {
                  if (c.id === _currentChat.value.id) {
                    c.brief = _currentChat.value.brief
                  }
                })
                break
              case 'error':
                terminalEvent = true
                currentRecord.error = data.content
                emits('error', currentRecord.id)
                break
              case 'sql-result':
                sql_answer += data.reasoning_content
                _currentChat.value.records[index.value].sql_answer = sql_answer
                break
              case 'sql':
                _currentChat.value.records[index.value].sql = data.content
                break
              case 'sql-data':
                getChatData(_currentChat.value.records[index.value].id)
                break
              case 'chart-result':
                chart_answer += data.reasoning_content
                _currentChat.value.records[index.value].chart_answer = chart_answer
                break
              case 'chart':
                _currentChat.value.records[index.value].chart = data.content
                break
              case 'answer-result':
                answer += data.content ?? ''
                _currentChat.value.records[index.value].answer = answer
                break
              case 'agent-step':
                if (data.step && typeof data.step === 'object') {
                  _currentChat.value.records[index.value].agent_steps = [
                    ...(_currentChat.value.records[index.value].agent_steps ?? []),
                    data.step,
                  ].slice(0, 4)
                }
                break
              case 'datasource':
                if (!_currentChat.value.datasource) {
                  _currentChat.value.datasource = data.id
                  _currentChat.value.datasource_name = data.datasource_name
                  _currentChat.value.ds_type = data.ds_type
                  _currentChat.value.engine_type = data.engine_type
                }
                break
              case 'finish':
                terminalEvent = true
                emits('finish', currentRecord.id)
                break
            }
            await nextTick()
          }
        }
      }
    }
  } catch (error) {
    if (stopFlag.value) return
    if (!currentRecord.error) {
      currentRecord.error = ''
    }
    if (currentRecord.error.trim().length !== 0) {
      currentRecord.error = currentRecord.error + '\n'
    }
    currentRecord.error = currentRecord.error + 'Error:' + error
    console.error('Error:', error)
    emits('error')
  } finally {
    if (activeController === controller) activeController = undefined
    _loading.value = false
  }
}

const loadingData = ref(false)

function getChatData(recordId?: number) {
  loadingData.value = true
  chatApi
    .get_chart_data(recordId)
    .then((response) => {
      _currentChat.value.records.forEach((record) => {
        if (record.id === recordId) {
          record.data = response
        }
      })
    })
    .finally(() => {
      loadingData.value = false
      emits('scrollBottom')
    })
}

function stop() {
  stopFlag.value = true
  activeController?.abort()
  _loading.value = false
  emits('stop')
}

const enableThousandsSeparatorList = ref<Array<string>>([])
const showLabel = ref<boolean>(false)

onBeforeUnmount(() => {
  stop()
})

onMounted(() => {
  if (
    props.message?.record?.id &&
    props.message.record.finish &&
    (props.message.record.chart || props.message.record.sql)
  ) {
    getChatData(props.message.record.id)
  }
})

defineExpose({ sendMessage, index: () => index.value, stop })
</script>

<template>
  <BaseAnswer v-if="message" :message="message" :reasoning-name="reasoningName" :loading="_loading">
    <MdComponent
      v-if="message.record?.answer"
      :message="message.record.answer"
      class="agent-answer"
    />
    <ChartBlock
      v-model:show-label="showLabel"
      v-model:thousands-separator-list="enableThousandsSeparatorList"
      style="margin-top: 6px"
      :message="message"
      :record-id="recordId"
      :loading-data="loadingData"
    />
    <details v-if="agentSteps.length" class="agent-steps">
      <summary>{{ t('chat.agent_steps', [agentSteps.length]) }}</summary>
      <div v-for="(step, stepIndex) in agentSteps" :key="stepIndex" class="agent-step">
        <div class="agent-step-heading">
          <span>{{ t('chat.agent_step', [stepIndex + 1]) }}</span>
          <span>{{
            step.error ? t('chat.agent_step_failed') : t('chat.agent_step_rows', [step.row_count])
          }}</span>
        </div>
        <div v-if="step.question" class="agent-step-question">{{ step.question }}</div>
        <pre v-if="step.sql" class="agent-step-sql"><code>{{ step.sql }}</code></pre>
        <details v-if="step.result" class="agent-step-preview">
          <summary>{{ t('datasource.preview') }}</summary>
          <div
            v-if="step.result.rows.length && step.result.fields.length"
            class="agent-step-preview-scroll"
          >
            <table>
              <thead>
                <tr>
                  <th
                    v-for="(field, fieldIndex) in step.result.fields.slice(0, 16)"
                    :key="fieldIndex"
                    scope="col"
                  >
                    {{ field }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in step.result.rows.slice(0, 20)" :key="rowIndex">
                  <td
                    v-for="(field, fieldIndex) in step.result.fields.slice(0, 16)"
                    :key="fieldIndex"
                  >
                    {{ row[field] ?? '' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="agent-step-empty">{{ t('chat.no_data') }}</div>
        </details>
      </div>
    </details>
    <slot></slot>
    <template #tool>
      <slot name="tool"></slot>
    </template>
    <template #footer>
      <slot name="footer"></slot>
    </template>
  </BaseAnswer>
</template>

<style scoped lang="less">
.agent-answer {
  margin-bottom: 12px;
}

.agent-steps {
  margin-top: 12px;
  color: #646a73;
  font-size: 14px;

  summary {
    cursor: pointer;
    width: fit-content;
  }

  .agent-step {
    padding: 10px 0 10px 12px;
    border-left: 1px solid #dee0e3;
  }

  .agent-step-heading {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    font-weight: 500;
    color: #1f2329;
  }

  .agent-step-question {
    margin-top: 4px;
  }

  .agent-step-sql {
    overflow-x: auto;
    margin: 8px 0 0;
    padding: 8px;
    border-radius: 6px;
    background: #f5f6f7;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .agent-step-preview {
    margin-top: 8px;

    summary {
      color: #3370ff;
    }
  }

  .agent-step-preview-scroll {
    max-height: 320px;
    margin-top: 8px;
    overflow: auto;
  }

  table {
    width: max-content;
    min-width: 100%;
    border-collapse: collapse;
    font-size: 13px;

    th,
    td {
      min-width: 120px;
      max-width: 260px;
      padding: 6px 10px;
      border-bottom: 1px solid #dee0e3;
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }

    th {
      background: #f5f6f7;
      font-weight: 500;
      color: #1f2329;
    }
  }

  .agent-step-empty {
    margin-top: 8px;
  }
}
</style>
