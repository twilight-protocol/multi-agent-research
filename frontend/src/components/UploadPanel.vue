<script setup>
import { ref } from "vue";
import { uploadPdf } from "../api/upload.js";

const file = ref(null);
const loading = ref(false);
const result = ref(null);
const error = ref("");

function pick(e) {
  file.value = e.target.files?.[0] || null;
  result.value = null;
  error.value = "";
  e.target.value = "";
}

async function doUpload() {
  if (!file.value || loading.value) return;
  loading.value = true;
  error.value = "";
  try {
    result.value = await uploadPdf(file.value);
  } catch (e) {
    error.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="panel upload">
    <h2>知识库</h2>

    <input type="file" accept=".pdf" :disabled="loading" @change="pick" />

    <button class="primary" :disabled="!file || loading" @click="doUpload">
      {{ loading ? "解析入库中，请稍候…" : "上传并入库" }}
    </button>

    <p v-if="loading" class="hint">
      正在切分并逐批调 Embedding（每批 10 条），几十页 PDF
      需要几十秒，不需要重复点
    </p>

    <p v-if="result" class="ok">
      已入库：{{ result.file }}（{{ result.pages }} 页 /
      {{ result.chunks }} 个片段）
    </p>
    <p v-if="error" class="err">上传失败：{{ error }}</p>
  </section>
</template>
