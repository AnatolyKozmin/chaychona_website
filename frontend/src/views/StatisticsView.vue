<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const loading = ref(false);
const error = ref("");

interface LearnerResultItem {
  test_id: number;
  test_title: string;
  score_percent: number;
  finished_at: string;
}

interface LearnerOverview {
  total_trainings: number;
  completed_trainings: number;
  completed_percent: number;
  total_tests: number;
  attempts_count: number;
  best_result: LearnerResultItem | null;
  worst_result: LearnerResultItem | null;
  attempts_last_7_days: number;
  avg_score_last_7_days: number;
  current_streak_days: number;
  longest_streak_days: number;
  daily_progress: Array<{
    date: string;
    attempts: number;
    avg_score_percent: number;
  }>;
}

interface AttemptItem {
  id: number;
  test_id: number;
  test_title: string;
  started_at: string | null;
  finished_at: string;
  duration_seconds: number | null;
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
}

interface AttemptDetail {
  attempt: AttemptItem;
  results: Array<{
    question_id: number;
    question_text: string;
    selected_options: string[];
    correct_options: string[];
    is_correct: boolean;
  }>;
}

const learnerOverview = ref<LearnerOverview | null>(null);
const learnerAttempts = ref<AttemptItem[]>([]);
const attemptDetails = ref<Record<number, AttemptDetail>>({});
const expandedAttemptId = ref<number | null>(null);

function formatDate(value: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU");
}

function formatShortDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}

async function loadLearnerAttempts() {
  const { data } = await api.get<AttemptItem[]>("/tests/my-attempts");
  learnerAttempts.value = data;
}

async function toggleAttemptDetails(attemptId: number) {
  if (expandedAttemptId.value === attemptId) {
    expandedAttemptId.value = null;
    return;
  }
  expandedAttemptId.value = attemptId;
  if (!attemptDetails.value[attemptId]) {
    const { data } = await api.get<AttemptDetail>(`/tests/my-attempts/${attemptId}`);
    attemptDetails.value[attemptId] = data;
  }
}

async function loadOverview() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<LearnerOverview>("/dashboard/me-overview");
    learnerOverview.value = data;
    await loadLearnerAttempts();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить статистику";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await loadOverview();
});
</script>

<template>
  <section class="card">
    <div class="actions-row">
      <h2 style="margin: 0">Статистика</h2>
      <button type="button" class="ghost" @click="loadOverview">Обновить</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>
    <template v-if="learnerOverview && !loading">
      <div class="dashboard-grid">
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Обучения пройдено</p>
          <h3 style="margin: 0">{{ learnerOverview.completed_percent.toFixed(1) }}%</h3>
          <p class="muted" style="margin: 6px 0 0">
            {{ learnerOverview.completed_trainings }} из {{ learnerOverview.total_trainings }}
          </p>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Доступно тестов</p>
          <h3 style="margin: 0">{{ learnerOverview.total_tests }}</h3>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Пройдено тестов (попыток)</p>
          <h3 style="margin: 0">{{ learnerOverview.attempts_count }}</h3>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Попыток за 7 дней</p>
          <h3 style="margin: 0">{{ learnerOverview.attempts_last_7_days }}</h3>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Средний результат (7 дней)</p>
          <h3 style="margin: 0">{{ learnerOverview.avg_score_last_7_days.toFixed(1) }}%</h3>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Текущая серия дней</p>
          <h3 style="margin: 0">{{ learnerOverview.current_streak_days }}</h3>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Лучшая серия дней</p>
          <h3 style="margin: 0">{{ learnerOverview.longest_streak_days }}</h3>
        </div>
      </div>

      <hr class="card-divider" />

      <div class="card">
        <h3>Динамика за 7 дней</h3>
        <div class="progress-chart">
          <div v-for="point in learnerOverview.daily_progress" :key="point.date" class="progress-col">
            <div class="progress-bar-wrap">
              <div
                class="progress-bar"
                :style="{ height: `${Math.max(6, Math.min(100, point.avg_score_percent))}%` }"
                :title="`${point.avg_score_percent.toFixed(1)}%`"
              />
            </div>
            <div class="muted" style="font-size: 11px">{{ point.attempts }} попыт.</div>
            <div class="muted" style="font-size: 11px">{{ formatShortDate(point.date) }}</div>
          </div>
        </div>
      </div>

      <hr class="card-divider" />

      <div class="card">
        <h3>Лучший результат</h3>
        <p v-if="!learnerOverview.best_result" class="muted">Пока нет попыток.</p>
        <template v-else>
          <p><strong>Тест:</strong> {{ learnerOverview.best_result.test_title }}</p>
          <p><strong>Результат:</strong> {{ learnerOverview.best_result.score_percent.toFixed(1) }}%</p>
          <p><strong>Дата:</strong> {{ formatDate(learnerOverview.best_result.finished_at) }}</p>
        </template>
      </div>

      <hr class="card-divider" />

      <div class="card">
        <h3>Худший результат</h3>
        <p v-if="!learnerOverview.worst_result" class="muted">Пока нет попыток.</p>
        <template v-else>
          <p><strong>Тест:</strong> {{ learnerOverview.worst_result.test_title }}</p>
          <p><strong>Результат:</strong> {{ learnerOverview.worst_result.score_percent.toFixed(1) }}%</p>
          <p><strong>Дата:</strong> {{ formatDate(learnerOverview.worst_result.finished_at) }}</p>
        </template>
      </div>

      <hr class="card-divider" />

      <div class="card">
        <h3>Мои попытки</h3>
        <p v-if="learnerAttempts.length === 0" class="muted">Попыток пока нет.</p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Тест</th>
                <th>Результат</th>
                <th>Время</th>
                <th>Дата</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <template v-for="item in learnerAttempts" :key="item.id">
                <tr>
                  <td>{{ item.test_title }}</td>
                  <td>{{ item.correct_answers }}/{{ item.total_questions }}</td>
                  <td>{{ item.duration_seconds ?? "-" }} сек.</td>
                  <td>{{ formatDate(item.finished_at) }}</td>
                  <td>
                    <button type="button" class="ghost" @click="toggleAttemptDetails(item.id)">
                      {{ expandedAttemptId === item.id ? "Скрыть" : "Открыть" }}
                    </button>
                  </td>
                </tr>
                <tr v-if="expandedAttemptId === item.id">
                  <td colspan="5">
                    <div class="clean-item">
                      <p v-if="!attemptDetails[item.id]" class="muted">Загрузка деталей...</p>
                      <div v-else class="attempt-result-list">
                        <div
                          v-for="res in attemptDetails[item.id].results"
                          :key="res.question_id"
                          class="test-result-card"
                          :class="res.is_correct ? 'test-result-card--correct' : 'test-result-card--incorrect'"
                        >
                          <div class="test-result-icon" :class="res.is_correct ? 'test-result-icon--correct' : 'test-result-icon--incorrect'">
                            <span v-if="res.is_correct">✓</span>
                            <span v-else>✗</span>
                          </div>
                          <p class="test-result-question long-text">{{ res.question_text }}</p>
                          <div class="test-result-answers">
                            <p class="test-result-row">
                              <span class="test-result-label">Ваш ответ:</span>
                              <span :class="res.is_correct ? 'test-result-value--correct' : 'test-result-value--incorrect'">
                                {{ res.selected_options.join(", ") || "Не выбран" }}
                              </span>
                            </p>
                            <p v-if="!res.is_correct" class="test-result-row">
                              <span class="test-result-label">Правильный:</span>
                              <span class="test-result-value--correct">{{ res.correct_options.join(", ") || "—" }}</span>
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>
</template>
