<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api/client";

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

onMounted(async () => {
  await loadStudy();
});
</script>

<template>
  <section class="card">
    <div class="actions-row">
      <h2 style="margin: 0">Обучение</h2>
      <button type="button" class="ghost" @click="router.push({ name: 'standards' })">К списку стандартов</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>

    <template v-if="!loading && study">
      <h3 style="margin-bottom: 6px">{{ study.course.title }}</h3>
      <p class="muted" style="margin-top: 0">
        {{ study.course.restaurant_name || "Все рестораны" }} • {{ study.course.job_title_name || "Все роли" }}
      </p>
      <p v-if="study.course.description" class="muted long-text">{{ study.course.description }}</p>

      <div class="menu-stats-row">
        <span class="status-chip">Прогресс: {{ study.progress_percent }}%</span>
        <span v-if="study.linked_test_stats" class="status-chip status-chip-success">
          Лучший тест: {{ study.linked_test_stats.best_score_percent ?? 0 }}%
        </span>
      </div>

      <div class="clean-list" style="margin-top: 10px">
        <div v-for="(item, idx) in study.blocks_progress" :key="item.block_id" class="clean-item">
          <div class="actions-row">
            <button
              type="button"
              class="ghost"
              :disabled="!item.is_unlocked"
              @click="activeBlockIdx = idx"
              style="text-align: left; margin: 0; width: auto; padding: 6px 10px"
            >
              {{ item.title }}
            </button>
            <span class="result-pill" :class="item.is_completed ? 'result-pill-success' : 'result-pill-error'">
              {{ item.is_completed ? "Понял" : item.is_unlocked ? "Открыт" : "Закрыт" }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="activeBlock && activeProgress" class="tinder-card" style="margin-top: 12px">
        <p class="muted" style="margin-top: 0">
          Этап {{ activeBlockIdx + 1 }} из {{ study.course.blocks.length }}
        </p>
        <h3 style="margin-top: 0">{{ activeBlock.heading || activeProgress.title }}</h3>
        <img
          v-if="activeBlock.image_path"
          :src="toMediaUrl(activeBlock.image_path) || undefined"
          alt="block image"
          style="width: 100%; border-radius: 12px; margin-bottom: 10px"
        />
        <p class="long-text">{{ activeBlock.text }}</p>
        <div v-for="subblock in activeBlock.subblocks" :key="subblock.id" class="clean-item" style="margin-top: 10px">
          <h4 v-if="subblock.heading" style="margin-top: 0">{{ subblock.heading }}</h4>
          <img
            v-if="subblock.image_path"
            :src="toMediaUrl(subblock.image_path) || undefined"
            alt="subblock image"
            style="width: 100%; border-radius: 10px; margin-bottom: 8px"
          />
          <p class="long-text" style="margin-bottom: 0">{{ subblock.text }}</p>
        </div>
        <div class="actions-row" style="margin-top: 10px">
          <button type="button" class="ghost" :disabled="!canGoPrev" @click="goPrev">Назад</button>
          <button type="button" :disabled="saving || activeProgress.is_completed" @click="markUnderstood">
            {{ activeProgress.is_completed ? "Изучено" : "Понял!" }}
          </button>
          <button type="button" class="ghost" :disabled="!canGoNext" @click="goNext">Дальше</button>
        </div>
      </div>

      <div v-if="study.linked_test_stats" class="card" style="margin-top: 12px">
        <p><strong>Тест после обучения:</strong> {{ study.linked_test_stats.test_title }}</p>
        <p class="muted">
          Попыток: {{ study.linked_test_stats.attempts_count }} | Последний результат:
          {{ study.linked_test_stats.last_score_percent ?? 0 }}%
        </p>
        <button type="button" @click="router.push({ name: 'my-tests' })">Перейти к тестам</button>
      </div>
    </template>
  </section>
</template>
