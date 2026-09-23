<script setup>
import { onMounted, ref } from "vue";
import ChatPanel from "./components/ChatPanel.vue";
import UploadPanel from "./components/UploadPanel.vue";
import SessionList from "./components/SessionList.vue";
import { streamChat } from "./api/chat.js";
import { listSessions, getMessages, delSession } from "./api/sessions.js";

const THREAD_KEY = "aka_thread_id";

const threadId = ref("");
const messages = ref([]);
const sending = ref(false);
const sessions = ref([]);
let controller = null;

onMounted(async () => {
  let id = localStorage.getItem(THREAD_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(THREAD_KEY, id);
  }
  threadId.value = id;
  await refreshSessions();
});

function newThread() {
  if (sending.value) return;
  const id = crypto.randomUUID();
  localStorage.setItem(THREAD_KEY, id);
  threadId.value = id;
  messages.value = [];
  // 本地占位：后端此刻还没这条记录，不插一条列表就没有高亮项；
  // 发消息后 refreshSessions() 会用后端的真实记录（带标题）整表覆盖掉它
  sessions.value.unshift({
    thread_id: id,
    title: "新对话",
    updated_at: "",
    message_count: 0,
  });
}

function stop() {
  controller?.abort();
}

async function send(text) {
  const content = (text || "").trim();
  if (!content || sending.value) return;

  messages.value.push({ role: "user", content });
  messages.value.push({ role: "assistant", content: "" });

  const idx = messages.value.length - 1;
  sending.value = true;
  controller = new AbortController();

  try {
    await streamChat({
      message: content,
      threadId: threadId.value,
      signal: controller.signal,
      onDelta: (delta) => {
        // 改最后一条，不 push
        messages.value[idx].content += delta;
      },
      onError: (detail) => {
        messages.value[idx].error = detail;
        if (!messages.value[idx].content)
          messages.value[idx].content = "（生成失败）";
      },
    });
  } catch (e) {
    if (e.name === "AbortError") {
      // 用户主动停止，保留已生成的部分
      if (!messages.value[idx].content)
        messages.value[idx].content = "（已停止）";
    } else {
      messages.value[idx].error = e.message || String(e);
      if (!messages.value[idx].content)
        messages.value[idx].content = "（请求失败）";
    }
  } finally {
    //复位
    sending.value = false;
    controller = null;
    await refreshSessions();
  }
}
async function refreshSessions() {
  sessions.value = await listSessions();
}
async function switchThread(id) {
  if (sending.value || id === threadId.value) return;
  threadId.value = id;
  localStorage.setItem(THREAD_KEY, id);
  const rows = await getMessages(id);
  // 兜底：接口异常时返回的不是数组，直接 map 会抛 TypeError
  messages.value = Array.isArray(rows)
    ? rows.map((r) => ({ role: r.role, content: r.content }))
    : [];
}
async function removeThread(id) {
  if (sending.value) return;
  await delSession(id);
  await refreshSessions();
  if (id === threadId.value) newThread();
}
</script>

<template>
  <div class="app">
    <header class="topbar">
      <h1>AI Knowledge Assistant</h1>
      <button class="ghost" :disabled="sending" @click="newThread">
        新对话
      </button>
    </header>

    <main class="body">
      <div class="main-row">
        <SessionList
          :sessions="sessions"
          :active-id="threadId"
          :disabled="sending"
          @select="switchThread"
          @new="newThread"
          @remove="removeThread"
        />
        <ChatPanel
          :messages="messages"
          :sending="sending"
          @send="send"
          @stop="stop"
        />
      </div>
      <UploadPanel />
    </main>

    <footer class="foot">thread_id: {{ threadId }}</footer>
  </div>
</template>
