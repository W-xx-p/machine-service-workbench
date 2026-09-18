<script setup lang="ts">
defineProps<{ status: string }>()

const labels: Record<string, string> = {
  published: '已发布', pending: '待审核', approved: '已批准', rejected: '已驳回',
  deprecated: '已废止', complete: '已解析', processing: '解析中', failed: '解析失败',
  official_public: '官方公开', demo_process_data: '演示数据', internal: '企业内部', external_public: '外部公开',
  high: '高风险', medium: '中风险', low: '低风险', active: '在用',
}
</script>

<template>
  <span class="status-badge" :class="`status-${status}`">{{ labels[status] || status }}</span>
</template>

