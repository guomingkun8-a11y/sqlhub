<script lang="ts" setup>
import { Document } from '@element-plus/icons-vue'
withDefaults(
  defineProps<{
    name: string
    description: string
    creator: string
  }>(),
  {
    name: '',
    description: '',
    creator: '',
  }
)
</script>

<template>
  <div class="datasource-card">
    <div class="datasource-card__header">
      <el-icon size="18" class="datasource-card__icon">
        <Document></Document>
      </el-icon>
      <span class="datasource-card__name">{{ name }}</span>
    </div>
    <div class="datasource-card__row">
      <span class="datasource-card__key">描述</span>
      <span class="datasource-card__value">{{ description }}</span>
    </div>
    <div class="datasource-card__row">
      <span class="datasource-card__key">创建人</span>
      <span class="datasource-card__value">{{ creator }}</span>
    </div>
  </div>
</template>

<style lang="less" scoped>
.datasource-card {
  height: 120px;
  padding: 16px;
  border-radius: var(--radius-md, 10px);
  background: var(--paper, #fff);
  border: 1px solid var(--ink-150, var(--border-color));
  box-shadow: var(--shadow-xs);
  display: flex;
  flex-direction: column;
  transition:
    border-color var(--dur-base) var(--ease-out-quart),
    box-shadow var(--dur-base) var(--ease-out-quart),
    transform var(--dur-base) var(--ease-out-quart);

  &:hover {
    border-color: var(--ink-200);
    box-shadow: var(--shadow-sm);
  }

  .datasource-card__header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;

    .datasource-card__icon {
      color: var(--accent-500);
      flex-shrink: 0;
    }

    .datasource-card__name {
      font-size: 15px;
      font-weight: 600;
      letter-spacing: var(--tracking-tight);
      color: var(--ink-900);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .datasource-card__row {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 6px;
    font-size: 13px;
    line-height: 20px;

    .datasource-card__key {
      flex-shrink: 0;
      color: var(--ink-400);
    }

    .datasource-card__value {
      color: var(--ink-700);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }
}
</style>
