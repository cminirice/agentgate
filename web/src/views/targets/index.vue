<script setup lang="ts">
// 评测对象页（占位，P2 阶段实现）
import PageContainer from '@/components/PageContainer.vue'
import ComingSoon from '@/components/ComingSoon.vue'
</script>

<template>
  <PageContainer title="评测对象" description="管理被评测的 Agent 目标及其版本与端点。">
    <ComingSoon
      title="评测对象管理"
      description="注册、配置、版本化 Agent 目标（含端点、认证、能力声明等），将在 P2 阶段交付。"
      phase="P2"
    />
  </PageContainer>
</template>
