<script lang="ts" setup>
import { useI18n } from 'vue-i18n'
import icon_spark from '@/assets/svg/icon_new_chat_outlined.svg'

const { t } = useI18n()

const emits = defineEmits<{
  (e: 'ask', question: string): void
}>()

// 空状态示例问题（静态默认，可按需在 appearance 配置里扩展）
const sampleQuestions = [
  { icon: '📊', text: '查看数据库各表的数据量概览' },
  { icon: '🗂️', text: '列出所有数据源表清单' },
  { icon: '📈', text: '分析近七天的日报数据趋势' },
  { icon: '📝', text: '统计日报提交的完整度情况' },
]

function ask(q: string) {
  emits('ask', q)
}
</script>

<template>
  <div class="welcome-questions">
    <div class="welcome-questions__label">{{ t('qa.try_ask') }}</div>
    <div class="welcome-questions__grid">
      <button
        v-for="(q, i) in sampleQuestions"
        :key="i"
        type="button"
        class="wq-card"
        @click="ask(q.text)"
      >
        <span class="wq-card__icon">{{ q.icon }}</span>
        <span class="wq-card__text">{{ q.text }}</span>
      </button>
    </div>
  </div>
</template>

<style lang="less" scoped>
.welcome-questions {
  width: 100%;
  display: flex;
  flex-direction: column;
  --gap-size: 12px;
  gap: 12px;
  margin-top: 8px;

  &__label {
    font-size: 12px;
    font-weight: 500;
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
    color: var(--ink-400);
    text-align: center;
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }
}

.wq-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--ink-200);
  background: var(--paper);
  cursor: pointer;
  text-align: left;
  font-family: var(--font-sans);
  transition:
    border-color var(--dur-base) var(--ease-out-quart),
    background-color var(--dur-base) var(--ease-out-quart),
    transform 140ms var(--ease-out-quart),
    box-shadow var(--dur-base) var(--ease-out-quart);

  &:hover {
    border-color: var(--accent-500);
    background: var(--accent-50);
    transform: translateY(-1px);
    box-shadow: var(--shadow-sm);
  }

  &:active {
    transform: translateY(0) scale(0.99);
    box-shadow: none;
  }

  &__icon {
    font-size: 16px;
    line-height: 1;
    flex-shrink: 0;
  }

  &__text {
    font-size: 14px;
    line-height: 20px;
    font-weight: 400;
    color: var(--ink-700);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
