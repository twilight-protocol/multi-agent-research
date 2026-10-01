<script setup>
import { computed } from "vue";

const props = defineProps({
  log: { type: Array, default: () => [] }, // 已完成的节点，按真实执行顺序
  running: { type: Boolean, default: false },
  waiting: { type: Boolean, default: false }, // 已中断、等人签字
});

// 与 graph.py 的 add_node 顺序一致：画出来就是架构图
const NODES = [
  { id: "search", name: "检索", desc: "本地知识库 + 联网双路" },
  { id: "analyze", name: "分析", desc: "只依据片段，标注出处" },
  { id: "write", name: "写作", desc: "结构化报告 + evidence" },
  { id: "critique", name: "自审", desc: "查无出处 / 出处不符 / 覆盖不足" },
  { id: "revise", name: "修订", desc: "逐条改，不顺手重写" },
  { id: "human_review", name: "人工终审", desc: "签字放行，或打回再改" },
];

// 每个节点跑了几次：revise 出现 2 次 = 自审循环真的转了 2 轮
const stats = computed(() => {
  const m = {};
  for (const s of props.log) m[s.node] = (m[s.node] || 0) + 1;
  return m;
});

// progress 事件在节点「跑完」时发出，所以最后一条日志就是刚刚/正在执行的那个
function state(id) {
  if (props.waiting && id === "human_review") return "wait";
  if (!stats.value[id]) return "idle";
  if (props.running && id === props.log.at(-1)?.node) return "active";
  return "done";
}
</script>

<template>
  <div class="panel">
    <h2 class="panel-title">执行进度</h2>

    <ol class="pipe">
      <li v-for="n in NODES" :key="n.id" :class="['node', state(n.id)]">
        <span class="dot"></span>
        <div class="body">
          <div class="name">
            {{ n.name }}
            <span v-if="stats[n.id] > 1" class="loop">×{{ stats[n.id] }}</span>
          </div>
          <div class="desc">{{ n.desc }}</div>
        </div>
      </li>
    </ol>

    <template v-if="log.length">
      <h2 class="panel-title">执行日志</h2>
      <ol class="log">
        <li v-for="(s, i) in log" :key="i">
          <span class="seq">{{ i + 1 }}</span
          >{{ s.label }}
        </li>
      </ol>
    </template>
  </div>
</template>
