<script setup>
import { computed, ref } from "vue";
import { renderMarkdown } from "../utils/markdown";

const props = defineProps({
  markdown: { type: String, default: "" },
  title: { type: String, default: "研究报告" },
  note: { type: String, default: "" },
});

const html = computed(() => renderMarkdown(props.markdown));

const copied = ref(false);

// navigator.clipboard 只在安全上下文可用（localhost 算安全上下文，http 的局域网 IP 不算）
async function copy() {
  try {
    await navigator.clipboard.writeText(props.markdown);
    copied.value = true;
    setTimeout(() => (copied.value = false), 1600);
  } catch {
    copied.value = false;
  }
}

// 必须包成函数：模板里拿不到 window（不在 Vue 的全局白名单里），写 window.print() 会报未定义
function print() {
  window.print();
}
</script>

<template>
  <article class="panel report">
    <h2 class="panel-title">
      {{ title }}
      <span v-if="note" class="tag">{{ note }}</span>
      <span class="spacer"></span>
      <button class="mini" :disabled="!markdown" @click="copy">
        {{ copied ? "已复制" : "复制" }}
      </button>
      <!-- 打印样式在 style.css 的 @media print 里单独调过：深色会被翻成白底黑字 -->
      <button class="mini" :disabled="!markdown" @click="print">打印</button>
    </h2>
    <!-- 内容来自自家后端 LLM；renderMarkdown 内部已做 HTML 转义，不会执行注入脚本 -->
    <div class="md" v-html="html"></div>
  </article>
</template>
