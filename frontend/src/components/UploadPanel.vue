<script setup>
import { ref } from "vue";
import { getUserId } from "../api/identity.js";

// 只用于前端提前拦一次，给出更快的反馈；后端 MAX_UPLOAD_BYTES 才是真正的守门人
const MAX_MB = 20;

const uploading = ref(false);
const error = ref("");
const over = ref(false); // 拖拽悬停
// 后端没有「列出已入库文档」的接口，所以这里只做本次会话内的回显，刷新即失
const history = ref([]);
const input = ref(null);

function openPicker() {
  if (!uploading.value) input.value?.click();
}

function onChange(e) {
  const file = e.target.files?.[0];
  // 不清空的话，连续选同一个文件不会触发 change，看起来像「点了没反应」
  if (input.value) input.value.value = "";
  if (file) send(file);
}

function onDrop(e) {
  over.value = false;
  if (uploading.value) return;
  const file = e.dataTransfer?.files?.[0];
  if (file) send(file);
}

async function send(file) {
  error.value = "";

  if (!file.name.toLowerCase().endsWith(".pdf")) {
    error.value = "只支持 PDF 文件";
    return;
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    error.value = `文件超过 ${MAX_MB}MB 上限`;
    return;
  }

  const fd = new FormData();
  fd.append("file", file); // 字段名必须是 file，对应后端 UploadFile = File(...)

  uploading.value = true;
  try {
    // 关键：不要手写 Content-Type，要让浏览器自动带上 multipart 的 boundary
    const res = await fetch("/api/upload", {
      method: "POST",
      // 告诉后端这份文件算谁的
      headers: { "X-User-Id": getUserId() },
      body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    // 返回 { file, stored_as, pages, chunks }
    history.value.unshift(data);
  } catch (e) {
    error.value = String(e?.message || e);
  } finally {
    uploading.value = false;
  }
}
</script>

<template>
  <div class="panel">
    <h2 class="panel-title">知识库上传</h2>

    <div
      :class="['drop', { over, busy: uploading }]"
      @click="openPicker"
      @dragover.prevent="over = true"
      @dragleave.prevent="over = false"
      @drop.prevent="onDrop"
    >
      <div class="drop-icon">{{ uploading ? "◌" : "⇪" }}</div>
      <div class="drop-main">
        {{ uploading ? "解析 + 向量化中…" : "拖入 PDF，或点击选择" }}
      </div>
      <div class="drop-sub">
        {{
          uploading
            ? "页数多的文件可能要几十秒，别关页面"
            : `单文件 ≤ ${MAX_MB}MB · 60 秒内最多 3 份`
        }}
      </div>
    </div>
    <input
      ref="input"
      class="hidden-input"
      type="file"
      accept="application/pdf,.pdf"
      :disabled="uploading"
      @change="onChange"
    />

    <p class="muted tip">
      入库后的片段会成为「检索双路」里的本地那一路；
      <strong>同名文件重传是覆盖</strong>（后端先 delete 同 source 再写入）。
    </p>

    <p v-if="error" class="error">{{ error }}</p>

    <ul v-if="history.length" class="files">
      <li v-for="f in history" :key="f.stored_as">
        <span class="fname" :title="f.file">{{ f.file }}</span>
        <span class="fmeta">{{ f.pages }}页 / {{ f.chunks }}片段</span>
      </li>
    </ul>
  </div>
</template>
