<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api/client";

let dragStartX = 0;
let dragging = false;

interface CourseSubBlock {
  id: number;
  heading: string | null;
  text: string;
  image_path: string | null;
  image_url: string | null;
  sort_order: number;
}

interface CourseBlock {
  id: number;
  heading: string | null;
  text: string;
  image_path: string | null;
  image_url: string | null;
  sort_order: number;
  subblocks: CourseSubBlock[];
}

interface CoursePublic {
  id: number;
  title: string;
  description: string | null;
  restaurant_name: string | null;
  job_title_name: string | null;
  linked_test: { id: number; title: string } | null;
  blocks: CourseBlock[];
}

interface BlockProgress {
  block_id: number;
  title: string;
  sort_order: number;
  is_completed: boolean;
  completed_at: string | null;
  is_unlocked: boolean;
}

interface LinkedTestStats {
  test_id: number;
  test_title: string;
  attempts_count: number;
  best_score_percent: number | null;
  last_score_percent: number | null;
  last_attempt_at: string | null;
}

interface StudyResponse {
  course: CoursePublic;
  blocks_progress: BlockProgress[];
  progress_percent: number;
  linked_test_stats: LinkedTestStats | null;
}

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const study = ref<StudyResponse | null>(null);
const activeBlockIdx = ref(0);
const cardOffsetX = ref(0);

const activeBlock = computed(() => study.value?.course.blocks[activeBlockIdx.value] ?? null);
const activeProgress = computed(() => study.value?.blocks_progress[activeBlockIdx.value] ?? null);
const canGoPrev = computed(() => activeBlockIdx.value > 0);
const canGoNext = computed(() => {
  if (!study.value || !activeProgress.value) {
    return false;
  }
  if (activeBlockIdx.value >= study.value.course.blocks.length - 1) {
    return false;
  }
  return activeProgress.value.is_completed;
});

function toMediaUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const backendOrigin = new URL(baseUrl).origin;
  return `${backendOrigin}/api/v1/menu/media?path=${path}`;
}

function extractError(e: any, fallback: string): string {
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item: any) => item?.msg || JSON.stringify(item)).join(" | ");
  }
  if (typeof detail === "string" && detail.trim()) return detail;
  return fallback;
}

function chooseInitialBlock() {
  if (!study.value) {
    activeBlockIdx.value = 0;
    return;
  }
  const firstPendingUnlocked = study.value.blocks_progress.findIndex((item) => item.is_unlocked && !item.is_completed);
  if (firstPendingUnlocked >= 0) {
    activeBlockIdx.value = firstPendingUnlocked;
    return;
  }
  const lastUnlocked = study.value.blocks_progress.map((item, idx) => ({ item, idx })).filter((x) => x.item.is_unlocked).pop();
  activeBlockIdx.value = lastUnlocked ? lastUnlocked.idx : 0;
}

async function loadStudy() {
  const courseId = Number(route.params.id);
  if (!courseId || Number.isNaN(courseId)) {
    error.value = "Некорректный ID курса";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<StudyResponse>(`/courses/my/${courseId}/study`);
    study.value = data;
    chooseInitialBlock();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить обучение");
  } finally {
    loading.value = false;
  }
}

async function markUnderstood() {
  if (!study.value || !activeBlock.value) {
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    const { data } = await api.post<StudyResponse>(
      `/courses/my/${study.value.course.id}/blocks/${activeBlock.value.id}/complete`
    );
    study.value = data;
    const currentCompleted = study.value.blocks_progress[activeBlockIdx.value]?.is_completed;
    if (currentCompleted && activeBlockIdx.value < study.value.course.blocks.length - 1) {
      activeBlockIdx.value += 1;
    }
  } catch (e: any) {
    error.value = extractError(e, "Не удалось отметить блок");
  } finally {
    saving.value = false;
  }
}

function goPrev() {
  if (!canGoPrev.value) return;
  activeBlockIdx.value -= 1;
}

function goNext() {
  if (!canGoNext.value) return;
  activeBlockIdx.value += 1;
}

function onPointerDown(event: PointerEvent) {
  dragging = true;
  dragStartX = event.clientX;
}

function onPointerMove(event: PointerEvent) {
  if (!dragging) return;
  cardOffsetX.value = event.clientX - dragStartX;
}

function onPointerUp() {
  if (!dragging) return;
  const threshold = 90;
  if (cardOffsetX.value <= -threshold) {
    if (canGoNext.value) goNext();
  } else if (cardOffsetX.value >= threshold) {
    if (canGoPrev.value) goPrev();
  }
  cardOffsetX.value = 0;
  dragging = false;
}

onMounted(async () => {
  await loadStudy();
});
</script>

<template>
  <section class="card standards-study-card">
    <div class="standards-study-header">
      <button type="button" class="ghost standards-back-btn" @click="router.push({ name: 'standards' })">
        ← Назад
      </button>
      <h2 class="standards-study-title">{{ study?.course?.title ?? "Стандарт" }}</h2>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>

    <template v-if="!loading && study">
      <div class="standards-progress-wrap standards-progress-wrap--study">
        <div class="standards-progress-bar standards-progress-bar--shimmer">
          <div
            class="standards-progress-fill"
            :style="{ width: `${study.progress_percent}%` }"
          />
        </div>
        <span class="standards-progress-text">{{ activeBlockIdx + 1 }} / {{ study.course.blocks.length }}</span>
      </div>

      <div
        v-if="activeBlock && activeProgress"
        class="tinder-card standards-tinder-card"
        :style="{ transform: `translateX(${cardOffsetX}px) rotate(${cardOffsetX / 18}deg)` }"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerUp"
        @pointerleave="onPointerUp"
      >
        <h3 class="standards-block-heading">{{ activeBlock.heading || activeProgress.title }}</h3>
        <img
          v-if="activeBlock.image_path"
          :src="toMediaUrl(activeBlock.image_path) || undefined"
          alt="block image"
          style="width: 100%; border-radius: 12px; margin-bottom: 10px"
        />
        <p class="long-text">{{ activeBlock.text }}</p>
        <div v-for="subblock in activeBlock.subblocks" :key="subblock.id" class="standards-subblock">
          <h4 v-if="subblock.heading" class="standards-subblock-heading">{{ subblock.heading }}</h4>
          <img
            v-if="subblock.image_path"
            :src="toMediaUrl(subblock.image_path) || undefined"
            alt=""
            class="standards-subblock-img"
          />
          <p class="long-text">{{ subblock.text }}</p>
        </div>
        <div class="standards-block-actions">
          <button type="button" class="ghost" :disabled="!canGoPrev" @click="goPrev">←</button>
          <button type="button" class="standards-understood-btn" :disabled="saving || activeProgress.is_completed" @click="markUnderstood">
            {{ activeProgress.is_completed ? "Изучено" : "Понял!" }}
          </button>
          <button type="button" class="ghost" :disabled="!canGoNext" @click="goNext">→</button>
        </div>
      </div>

      <div v-if="study.linked_test_stats" class="standards-test-link">
        <button type="button" @click="router.push({ name: 'my-tests', query: { test: String(study.linked_test_stats.test_id) } })">
          Пройти тест: {{ study.linked_test_stats.test_title }}
        </button>
      </div>
    </template>
  </section>
</template>
