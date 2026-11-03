<template>
  <div v-loading="loading" class="datasource-page">
    <div class="header">
      <h1 class="page-title">{{ t('menu.Data Connections') }}</h1>
      <div class="header-controls">
        <div class="search-control">
          <el-input
            v-model="searchValue"
            :placeholder="t('ds.Search Datasource')"
            class="input-with-select"
            clearable
            @change="searchHandle"
          >
            <template #prepend>
              <el-icon>
                <Search />
              </el-icon>
            </template>
          </el-input>
        </div>

        <el-button
          class="border-radius_8"
          type="primary"
          :icon="IconOpeAdd"
          @click="editDs(undefined)"
          >{{ t('ds.add') }}</el-button
        >
      </div>
    </div>

    <div v-if="loadFailed" class="datasource-error" role="alert">
      <el-icon size="18"><WarningFilled /></el-icon>
      <span>{{ t('datasource.load_failed') }}</span>
      <el-button text type="primary" @click="list">
        <template #icon><RefreshRight /></template>
        {{ t('datasource.retry') }}
      </el-button>
    </div>
    <div v-else-if="dsList.length" class="connections-container flex-gap-fallback">
      <template v-for="ds in dsList" :key="ds">
        <DatasourceItemCard :ds="ds">
          <div class="connection-actions">
            <el-button
              class="action-btn"
              circle
              :aria-label="`${t('ds.tables')}: ${ds.name}`"
              :title="`${t('ds.tables')}: ${ds.name}`"
              :icon="List"
              @click="getTables(ds.id, ds.name)"
            />
            <el-button
              type="primary"
              class="action-btn"
              circle
              :aria-label="`${t('datasource.edit')}: ${ds.name}`"
              :title="`${t('datasource.edit')}: ${ds.name}`"
              :icon="IconOpeEdit"
              @click="editDs(ds)"
            />
            <el-button
              type="danger"
              class="action-btn"
              circle
              :aria-label="`${t('dashboard.delete')}: ${ds.name}`"
              :title="`${t('dashboard.delete')}: ${ds.name}`"
              :icon="IconOpeDelete"
              @click="deleteDs(ds)"
            />
          </div>
        </DatasourceItemCard>
      </template>
    </div>
    <EmptyBackground
      v-else-if="!loading"
      :description="searchValue ? t('datasource.relevant_content_found') : t('datasource.data_source_yet')"
      img-type="none"
    >
      <el-button v-if="!searchValue" type="primary" :icon="IconOpeAdd" @click="editDs(undefined)">
        {{ t('ds.add') }}
      </el-button>
    </EmptyBackground>
  </div>
  <DsForm ref="dsForm" @refresh="refresh" />
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import IconOpeAdd from '@/assets/svg/operate/ope-add.svg'
import IconOpeEdit from '@/assets/svg/operate/ope-edit.svg'
import IconOpeDelete from '@/assets/svg/operate/ope-delete.svg'
import { Search, List, RefreshRight, WarningFilled } from '@element-plus/icons-vue'
import DsForm from './form.vue'
import { datasourceApi } from '@/api/datasource'
import { ElMessageBox } from 'element-plus-secondary'
import { useRouter } from 'vue-router'
import DatasourceItemCard from '@/views/ds/DatasourceItemCard.vue'
import EmptyBackground from '@/views/dashboard/common/EmptyBackground.vue'

const { t } = useI18n()
const searchValue = ref<string>('')
const dsForm = ref()
const dsList = ref<any>([]) // show ds list
const allDsList = ref<any>([]) // all ds list
const router = useRouter()
const loading = ref(true)
const loadFailed = ref(false)

function searchHandle() {
  if (searchValue.value) {
    dsList.value = JSON.parse(JSON.stringify(allDsList.value)).filter((item: any) => {
      return item.name.toLowerCase().includes(searchValue.value.toLowerCase())
    })
  } else {
    dsList.value = JSON.parse(JSON.stringify(allDsList.value))
  }
}

const refresh = () => {
  list()
}

const list = () => {
  loading.value = true
  loadFailed.value = false
  datasourceApi.list().then((res) => {
    allDsList.value = res
    dsList.value = JSON.parse(JSON.stringify(allDsList.value))
  }).catch(() => {
    loadFailed.value = true
  }).finally(() => {
    loading.value = false
  })
}

const editDs = (item: any) => {
  dsForm.value.open(item)
}

const deleteDs = (item: any) => {
  ElMessageBox.confirm(t('ds.delete'), t('common.confirm'), {
    confirmButtonText: t('common.confirm'),
    cancelButtonText: t('common.cancel'),
    type: 'warning',
  })
    .then(() => {
      datasourceApi.delete(item.id, item.name).then(() => {
        refresh()
      })
    })
    .catch(() => {})
}

const getTables = (id: number, name: string) => {
  router.push(`/dsTable/${id}/${name}`)
}

onMounted(() => {
  list()
})
</script>
<style lang="less" scoped>
.header {
  background-color: var(--paper);
  padding: 14px 16px;
  border: 1px solid var(--ink-200);
  border-radius: var(--radius-md);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;

  .page-title {
    margin: 0;
    color: var(--ink-900);
    font-size: 18px;
    font-weight: 600;
    line-height: 26px;
  }

  .header-controls {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    flex: 1;
    min-width: 0;
    margin-left: 24px;
  }

  .search-control {
    width: min(360px, 100%);
    min-width: 0;
  }

  .input-with-select {
    --ed-input-border-radius: 8px;
    --ed-border-radius-base: 8px;
    width: 100%;
  }
}

.datasource-error {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 12px;
  min-height: 180px;
  padding: 24px;
  color: var(--ink-700);
  text-align: center;

  .ed-icon {
    color: var(--ed-color-danger);
  }
}

.connections-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  --gap-size: 16px;
  gap: 16px;

  .connection-actions {
    position: absolute;
    bottom: 20px;
    right: 20px;
    display: flex;

    .action-btn {
      min-width: 0;
      width: 36px;
      height: 36px;
    }
  }
}

@media (max-width: 640px) {
  .header {
    align-items: flex-start;
    flex-wrap: wrap;
    padding: 12px;

    .page-title {
      width: 100%;
    }

    .header-controls {
      width: 100%;
      flex-wrap: wrap;
      gap: 8px;
      margin-left: 0;
    }

    .search-control,
    .input-with-select {
      width: 100%;
    }

    .header-controls > .ed-button {
      flex: 1;
    }
  }

  .connections-container {
    grid-template-columns: minmax(0, 1fr);
    gap: 12px;
  }
}
</style>
