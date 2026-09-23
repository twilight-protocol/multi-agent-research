<script setup>
import { nextTick, ref, watch } from "vue";

const props = defineProps({
  messages: { type: Array, required: true },
  sending: { type: Boolean, default: false },
});
const emit = defineEmits(["send", "stop"]);

const input = ref("");
const listEl = ref(null);

// 内容变化就滚到底
watch(
  () => props.messages.map((m) => m.content.length).join(","),
  async () => {
    await nextTick();
    const el = listEl.value;
    if (el) el.scrollTop = el.scrollHeight;
  },
);

function submit() {
  if (props.sending) return;
  const text = input.value;
  input.value = "";
  emit("send", text);
}
</script>

<template>
  <section class="panel chat">
    <div ref="listEl" class="list">
      <div v-if="!messages.length" class="empty">
        上传 PDF 后，直接提问文档里的内容
      </div>

      <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
        <div class="bubble">
          <span class="text">{{ m.content }}</span>
          <span v-if="m.error" class="err">出错了：{{ m.error }}</span>
        </div>
      </div>

      <div v-if="sending" class="typing">正在输入…</div>
    </div>

    <div class="row">
      <textarea
        v-model="input"
        :disabled="sending"
        rows="2"
        placeholder="输入问题，Enter 发送 / Shift+Enter 换行"
        @keydown.enter.exact.prevent="submit"
      ></textarea>

      <button
        v-if="!sending"
        class="primary"
        :disabled="!input.trim()"
        @click="submit"
      >
        发送
      </button>
      <button v-else class="danger" @click="emit('stop')">停止</button>
    </div>
  </section>
</template>
