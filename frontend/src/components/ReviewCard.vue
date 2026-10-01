<script setup>
import { ref } from "vue";
import ReportView from "./ReportView.vue";

const props = defineProps({
  // 来自 interrupt 帧：draft / issues / limit_reached / revision_count
  review: { type: Object, required: true },
});
const emit = defineEmits(["decide"]);

const comment = ref("");
</script>

<template>
  <div class="panel review">
    <h2 class="panel-title">
      人工终审
      <span class="tag">已修订 {{ review.revision_count }} 次</span>
    </h2>

    <p v-if="review.limit_reached" class="warn">
      自审循环已到修订上限。你可以直接放行，或再给 AI 一次修订机会。
    </p>

    <template v-if="review.issues.length">
      <div class="sub-title">审查清单</div>
      <ul class="issues">
        <li v-for="(it, i) in review.issues" :key="i">{{ it }}</li>
      </ul>
    </template>
    <p v-else class="muted">审查清单为空（自审已通过）。</p>

    <ReportView :markdown="review.draft" title="待审草稿" />

    <div class="decide">
      <textarea
        v-model="comment"
        rows="2"
        placeholder="打回时写清要改什么；它会以 [人工] 意见的形式进入下一轮修订"
      ></textarea>
      <div class="btns">
        <button
          class="primary"
          @click="emit('decide', { action: 'approve', comment: comment })"
        >
          批准发布
        </button>
        <!-- 后端约定：action != approve 且 comment 非空才算打回，空评论会被兜底成 approve，所以这里直接禁用 -->
        <button
          class="ghost"
          :disabled="!comment.trim()"
          @click="emit('decide', { action: 'revise', comment: comment })"
        >
          打回修订
        </button>
      </div>
    </div>
  </div>
</template>
