<script setup>
import { computed, onMounted, ref } from "vue";
import { streamResearch } from "./api/research";
import { getUserId } from "./api/identity";
import NodeProgress from "./components/NodeProgress.vue";
import ReportView from "./components/ReportView.vue";
import ReviewCard from "./components/ReviewCard.vue";
import UploadPanel from "./components/UploadPanel.vue";

const question = ref("");
// 检索范围：kb=只查自己上传的文档，web=只联网，both=双路（原行为，故设为默认）
// 值必须与后端 ResearchRequest.scope 的 Literal 一致，否则会被 pydantic 挡成 422
const scope = ref("both");
const SCOPES = [
  { value: "kb", label: "仅知识库" },
  { value: "web", label: "仅联网" },
  { value: "both", label: "自动双路" },
];
const threadId = ref("");
const running = ref(false); // 图正在跑（含 /resume 之后）
const waiting = ref(false); // 卡在 human_review 等签字
const log = ref([]); // progress 事件累积
const report = ref("");
const review = ref(null); // interrupt 帧的 payload
const stopReason = ref("");
const error = ref("");
// 检索降级说明：联网没生效时后端会带回来，必须显示——否则用户只看到「没有网址」
const searchNote = ref("");
// 恢复失败要说清原因（403/404/网络），不要静默清空让用户以为「刷新必丢」
const restoreError = ref("");

// stop_reason 是后端给的「报告是怎么停下来的」，放在标题旁做溯源
const STOP_TEXT = {
  passed: "自审通过",
  limit_reached: "达到修订上限",
};
const stopText = computed(
  () => STOP_TEXT[stopReason.value] ?? stopReason.value,
);

// 刷新恢复：thread_id 只存在 ref 里，一刷新就没了 —— 后端断点还在，
// 但前端连「去问哪条线程」的钥匙都丢了。所以钥匙要落在 localStorage。
const STATE_KEY = "mar_last_run";
const restored = ref(false);

function saveRun() {
  if (!threadId.value) return;
  localStorage.setItem(
    STATE_KEY,
    JSON.stringify({
      thread_id: threadId.value,
      question: question.value,
      scope: scope.value,
    }),
  );
}

function clearRun() {
  localStorage.removeItem(STATE_KEY);
}

// 只恢复两种状态：跑完了（next 为空）、卡在人工终审。
// 中途断掉的图没有续跑接口，硬恢复只会给一个走不动的半成品。
async function restore() {
  let saved = null;
  try {
    saved = JSON.parse(localStorage.getItem(STATE_KEY) || "null");
  } catch {
    saved = null;
  }
  if (!saved?.thread_id) return;

  try {
    const res = await fetch(
      `/api/research/state?thread_id=${encodeURIComponent(saved.thread_id)}`,
      { headers: { "X-User-Id": getUserId() } },
    );
    if (!res.ok) {
      // 403 = 换了身份（localStorage 里的 uid 和会话归属对不上）
      // 404 = 断点被清 / 服务端数据卷丢了
      restoreError.value = `上次会话无法恢复（HTTP ${res.status}）`;
      clearRun(); // 这两种是永久失败，钥匙作废
      return;
    }
    const d = await res.json();
    restoreError.value = "";
    searchNote.value = d.search_note || "";
    threadId.value = d.thread_id;
    question.value = saved.question || d.question || "";
    scope.value = saved.scope || "both";

    if (d.awaiting_review) {
      // 重建终审卡片：字段与 interrupt 帧保持一致，ReviewCard 不用改
      review.value = {
        draft: d.report,
        issues: d.issues,
        revision_count: d.revision_count,
        limit_reached: d.limit_reached,
        thread_id: d.thread_id,
      };
      waiting.value = true;
      restored.value = true;
      return;
    }

    if (!d.pending.length && d.report) {
      report.value = d.report;
      stopReason.value = d.stop_reason || "";
      restored.value = true;
      return;
    }

    clearRun();
  } catch (e) {
    // 网络错误不清钥匙：下次刷新还能再试，也给用户一个「重试」按钮
    restoreError.value = `上次会话恢复失败：${e?.message || e}`;
  }
}

onMounted(restore);

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
  restored.value = false;
  searchNote.value = "";
  restoreError.value = "";
  clearRun(); // 新一轮开始，旧断点不再作为恢复目标
}

// 四个事件与后端 sse_frame 一一对应
const handlers = {
  progress: (d) => {
    log.value.push(d);
    // 进度帧带 scoped thread_id：第一个节点跑完就把钥匙落盘，
    // 不用等 interrupt/done（中断帧万一没送到，刷新也不至于完全失联）
    if (d.thread_id) {
      threadId.value = d.thread_id;
      saveRun();
    }
  },
  interrupt: (d) => {
    review.value = d;
    // 必须收下带前缀的 thread_id：手上这份还是「原始 id」，
    // 直接拿去 /resume 会因归属对不上被 403（多租户改造后才有的要求）
    threadId.value = d.thread_id ?? threadId.value;
    waiting.value = true;
    running.value = false;
    searchNote.value = d.search_note || "";
    saveRun(); // 卡在终审时刷新，靠这把钥匙回来
  },
  done: (d) => {
    report.value = d.report;
    stopReason.value = d.stop_reason;
    threadId.value = d.thread_id; // 以后端返回的为准
    running.value = false;
    searchNote.value = d.search_note || "";
    saveRun();
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
      { question: q, thread_id: threadId.value, scope: scope.value },
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
        <span v-else-if="restored" class="live"><i></i>已恢复上次会话</span>
        <code v-if="threadId" class="tid" :title="threadId"
          >thread: {{ threadId }}</code
        >
      </div>
    </header>

    <section class="ask">
      <div class="ask-col">
        <!-- 先选范围再提问：切到「仅知识库」就不会再跑 web_search -->
        <div class="scope">
          <span>检索范围</span>
          <div class="seg" role="group" aria-label="检索范围">
            <button
              v-for="s in SCOPES"
              :key="s.value"
              type="button"
              :class="{ on: scope === s.value }"
              :disabled="running"
              @click="scope = s.value"
            >
              {{ s.label }}
            </button>
          </div>
        </div>
        <textarea
          v-model="question"
          rows="2"
          placeholder="输入要研究的问题，例如：2025 年国内储能行业的竞争格局与主要玩家？"
          @keydown.ctrl.enter="start"
        ></textarea>
      </div>
      <button
        class="primary"
        :disabled="running || !question.trim()"
        @click="start"
      >
        {{ running ? "研究进行中…" : "开始研究" }}
      </button>
    </section>

    <p v-if="error" class="error">请求失败：{{ error }}</p>
    <!-- 刷新恢复失败：必须显式说出来，否则用户只会看到「一片空白」 -->
    <p v-if="restoreError" class="error">
      {{ restoreError }}
      <button class="mini" @click="restore">重试</button>
    </p>
    <!-- 联网没生效（无 Key / 配额用完 / 无结果）：不算错误，但不说明白就会被当成模型 bug -->
    <p v-if="searchNote" class="warn">{{ searchNote }}</p>

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
