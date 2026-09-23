<script setup>
const props = defineProps({
  sessions: { type: Array, required: true },
  activeId: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(["select", "new", "remove"]);

const fmt = (t) => (t ? t.slice(5, 16) : "");

function confirmRemove(s) {
  if (window.confirm(`删除会话「${s.title}」？该会话的聊天记录会一并删除。`)) {
    emit("remove", s.thread_id);
  }
}
</script>

<template>
  <aside class="sessions">
    <div class="head">
      <span>会话</span>
      <button class="ghost sm" :disabled="disabled" @click="emit('new')">
        + 新对话
      </button>
    </div>

    <div v-if="!sessions.length" class="empty">还没有会话</div>

    <ul v-else class="list">
      <li
        v-for="s in sessions"
        :key="s.thread_id"
        class="item"
        :class="{ active: s.thread_id === activeId }"
        @click="!disabled && emit('select', s.thread_id)"
      >
        <div class="meta">
          <span class="title">{{ s.title }}</span>
          <span class="time">
            {{ fmt(s.updated_at) }}
            <template v-if="s.message_count">
              · {{ s.message_count }} 条</template
            >
          </span>
        </div>

        <button
          class="del"
          :disabled="disabled"
          title="删除会话"
          @click.stop="confirmRemove(s)"
        >
          ×
        </button>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.sessions {
  width: 200px;
  flex: 0 0 200px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: #fff;
  border: 1px solid #e3e5e8;
  border-radius: 8px;
  padding: 10px;
  min-height: 0;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
}
.ghost.sm {
  padding: 3px 8px;
  font-size: 12px;
  background: transparent;
  border: 1px solid #ccc;
}
.empty {
  color: #999;
  font-size: 13px;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 22px 6px 8px;
  border-radius: 6px;
  cursor: pointer;
}
.item:hover {
  background: #f0f1f3;
}
.item.active {
  background: #d8e8ff;
}
.meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.title {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.time {
  font-size: 11px;
  color: #8a8f95;
}
.del {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  width: 18px;
  height: 18px;
  padding: 0;
  line-height: 1;
  font-size: 13px;
  color: #9aa0a6;
  background: transparent;
  border: 0;
  border-radius: 4px;
  visibility: hidden;
}
.item:hover .del {
  visibility: visible;
}
.del:hover {
  color: #c0392b;
  background: #fdecea;
}
</style>
