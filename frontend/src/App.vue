<script setup>
import { computed, ref } from "vue";
import { streamResearch } from "./api/research";
import NodeProgress from "./components/NodeProgress.vue";
import ReportView from "./components/ReportView.vue";
import ReviewCard from "./components/ReviewCard.vue";
import UploadPanel from "./components/UploadPanel.vue";

const question = ref("");
const threadId = ref("");
const running = ref(false); // 图正在跑（含 /resume 之后）
const waiting = ref(false); // 卡在 human_review 等签字
const log = ref([]); // progress 事件累积
const report = ref("");
const review = ref(null); // interrupt 帧的 payload
const stopReason = ref("");
const error = ref("");

// stop_reason 是后端给的「报告是怎么停下来的」，放在标题旁做溯源
const STOP_TEXT = {
  passed: "自审通过",
  limit_reached: "达到修订上限",
};
const stopText = computed(
  () => STOP_TEXT[stopReason.value] ?? stopReason.value,
);

// thread_id 由前端生成：interrupt 帧里不带 thread_id，而 /resume 必须靠它找回中断点
function newThreadId() {
  return (
    globalThis.crypto?.randomUUID?.().replace(/-/g, "").slice(0, 12) ??
    Math.random().toString(16).slice(2, 14)
  );
}

function reset() {
  threadId.value = newThreadId();
  log.value = [];
  report.value = "";
  review.value = null;
  stopReason.value = "";
  error.value = "";
  waiting.value = false;
}

// 四个事件与后端 sse_frame 一一对应
const handlers = {
  progress: (d) => log.value.push(d),
  interrupt: (d) => {
    review.value = d;
    waiting.value = true;
    running.value = false;
  },
  done: (d) => {
    report.value = d.report;
    stopReason.value = d.stop_reason;
    threadId.value = d.thread_id; // 以后端返回的为准
    running.value = false;
  },
  error: (d) => {
    error.value = d.detail;
    running.value = false;
  },
};

async function start() {
  const q = question.value.trim();
  if (!q || running.value) return;
  reset();
  running.value = true;
  try {
    await streamResearch(
      "/api/research/stream",
      { question: q, thread_id: threadId.value },
      handlers,
    );
  } catch (e) {
    error.value = String(e?.message || e);
  } finally {
    running.value = false;
  }
}

async function decide({ action, comment }) {
  review.value = null;
  waiting.value = false;
  running.value = true;
  try {
    await streamResearch(
      "/api/research/resume",
      { thread_id: threadId.value, action, comment },
      handlers,
    );
  } catch (e) {
    error.value = String(e?.message || e);
  } finally {
    running.value = false;
  }
}
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div>
        <h1>多智能体行业研究助手</h1>
        <p class="sub">
          六节点图：检索双路 → 分析 → 写作 → 自审 → 修订 → 人工终审
        </p>
      </div>
      <div class="right-side">
        <span v-if="running" class="live"><i></i>图运行中</span>
        <span v-else-if="waiting" class="live warn-live"><i></i>等待终审</span>
        <code v-if="threadId" class="tid" :title="threadId"
          >thread: {{ threadId }}</code
        >
      </div>
    </header>

    <section class="ask">
      <textarea
        v-model="question"
        rows="2"
        placeholder="输入要研究的问题，例如：2025 年国内储能行业的竞争格局与主要玩家？"
        @keydown.ctrl.enter="start"
      ></textarea>
      <button
        class="primary"
        :disabled="running || !question.trim()"
        @click="start"
      >
        {{ running ? "研究进行中…" : "开始研究" }}
      </button>
    </section>

    <p v-if="error" class="error">请求失败：{{ error }}</p>

    <div class="cols">
      <aside class="left">
        <!-- 先喂资料，再提问：本地那一路检索依赖它 -->
        <UploadPanel />
        <NodeProgress :log="log" :running="running" :waiting="waiting" />
      </aside>

      <main class="right">
        <ReviewCard v-if="review" :review="review" @decide="decide" />
        <ReportView v-else-if="report" :markdown="report" :note="stopText" />
        <div v-else class="placeholder">报告会显示在这里</div>
      </main>
    </div>
  </div>
</template>
