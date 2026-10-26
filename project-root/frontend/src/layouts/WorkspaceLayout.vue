<template>
  <!-- 三栏工作台容器：历史记录 / 中间业务区 / 右侧面板 -->
  <!-- 所有业务组件都必须包在本容器内部，禁止外漏 -->
  <div class="workspace">
    <!-- 子项1：历史记录（模块局部侧边栏） -->
    <div class="history-column">
      <slot name="history" />
    </div>

    <!-- 子项2：中间主业务区（flex:1 自适应） -->
    <div class="main-content">
      <h1 v-if="title" class="workspace-title">{{ title }}</h1>
      <div class="workspace-body">
        <slot />
      </div>
    </div>

    <!-- 子项3：右侧辅助面板（固定宽度，按需） -->
    <aside v-if="$slots.panel" class="right-panel">
      <slot name="panel" />
    </aside>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
}>()
</script>

<style scoped>
.workspace {
  flex: 1;
  display: flex;
  min-width: 0;
  overflow: hidden;
}

/* 子项1：历史记录列 */
.history-column {
  width: var(--history-width, 240px);
  flex: none;
  display: flex;
  flex-direction: column;
  background: var(--color-panel);
  border-right: 1px solid var(--divider);
  overflow-y: auto;
}

/* 子项2：中间主业务区，flex:1 自适应 */
.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.workspace-title {
  flex: none;
  padding: 16px 24px 0;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary, #111827);
}

.workspace-body {
  flex: 1;
  overflow: auto;
  min-height: 0;
}

/* 子项3：右侧面板 */
.right-panel {
  width: var(--panel-width, 360px);
  flex: none;
  background: var(--color-panel);
  border-left: 1px solid var(--divider);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
