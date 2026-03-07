<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

interface AttemptItem {
  id: number;
  test_id: number;
  test_title: string;
  user_id: string;
  user_name: string;
  user_email: string;
  user_restaurant: string | null;
  user_job_title: string | null;
  started_at: string | null;
  finished_at: string;
  duration_seconds: number | null;
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
}

interface QuestionAnalyticsItem {
  question_id: number;
  test_id: number;
  test_title: string;
  question_text: string;
  total_attempts: number;
  wrong_attempts: number;
  correct_attempts: number;
  wrong_rate: number;
}

interface UserAnalyticsItem {
  user_id: string;
  user_name: string;
  user_email: string;
  attempts_count: number;
  total_answers: number;
  wrong_answers: number;
  wrong_rate: number;
  avg_duration_seconds: number | null;
}

interface AnalyticsSummary {
  total_attempts: number;
  unique_users: number;
  avg_score_percent: number;
  avg_duration_seconds: number | null;
}

interface AnalyticsResponse {
  summary: AnalyticsSummary;
  recent_attempts: AttemptItem[];
  attempts: AttemptItem[];
  question_analytics: QuestionAnalyticsItem[];
  user_analytics: UserAnalyticsItem[];
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

const auth = useAuthStore();
const loading = ref(false);
const error = ref("");
const analytics = ref<AnalyticsResponse | null>(null);
const detailLoading = ref(false);
const detailOpen = ref(false);
const selectedAttempt = ref<AttemptDetail | null>(null);
const filterRestaurant = ref("");
const filterRole = ref("");
const filterUser = ref("");

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU");
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

const availableRestaurants = computed(() => {
  const source = analytics.value?.attempts ?? [];
  return [...new Set(source.map((item) => item.user_restaurant || "").filter(Boolean))].sort((a, b) => a.localeCompare(b));
});

const availableRoles = computed(() => {
  const source = analytics.value?.attempts ?? [];
  return [...new Set(source.map((item) => item.user_job_title || "").filter(Boolean))].sort((a, b) => a.localeCompare(b));
});

const filteredAttempts = computed(() => {
  const source = analytics.value?.attempts ?? [];
  const nameQuery = filterUser.value.trim().toLowerCase();
  return source.filter((item) => {
    const matchesRestaurant = !filterRestaurant.value || (item.user_restaurant || "") === filterRestaurant.value;
    const matchesRole = !filterRole.value || (item.user_job_title || "") === filterRole.value;
    const haystack = `${item.user_name} ${item.user_email}`.toLowerCase();
    const matchesUser = !nameQuery || haystack.includes(nameQuery);
    return matchesRestaurant && matchesRole && matchesUser;
  });
});

async function loadAnalytics() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<AnalyticsResponse>("/tests/analytics", {
      params: {
        limit_recent: 5,
        attempts_limit: 500
      }
    });
    analytics.value = data;
    filterRestaurant.value = "";
    filterRole.value = "";
    filterUser.value = "";
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить аналитику";
  } finally {
    loading.value = false;
  }
}

async function openAttemptDetail(attemptId: number) {
  detailLoading.value = true;
  detailOpen.value = true;
  selectedAttempt.value = null;
  try {
    const { data } = await api.get<AttemptDetail>(`/tests/my-attempts/${attemptId}`);
    selectedAttempt.value = data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить детали прохождения";
    detailOpen.value = false;
  } finally {
    detailLoading.value = false;
  }
}

function closeAttemptDetail() {
  detailOpen.value = false;
  selectedAttempt.value = null;
}

onMounted(async () => {
  if (!auth.isSuperadmin) {
    return;
  }
  await loadAnalytics();
});
</script>

<template>
  <section v-if="auth.isSuperadmin" class="card">
    <div class="actions-row">
      <h2 style="margin: 0">Аналитика тестов</h2>
      <button type="button" class="ghost" @click="loadAnalytics">Обновить</button>
    </div>
    <p class="muted">Последние прохождения, полный список, проблемные вопросы и статистика ошибок по пользователям.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>

    <template v-if="analytics && !loading">
      <div class="card">
        <h3>Сводка</h3>
        <p><strong>Всего прохождений:</strong> {{ analytics.summary.total_attempts }}</p>
        <p><strong>Уникальных пользователей:</strong> {{ analytics.summary.unique_users }}</p>
        <p><strong>Средний результат:</strong> {{ analytics.summary.avg_score_percent.toFixed(1) }}%</p>
        <p v-if="analytics.summary.avg_duration_seconds !== null">
          <strong>Среднее время:</strong> {{ analytics.summary.avg_duration_seconds.toFixed(1) }} сек.
        </p>
      </div>

      <div class="card">
        <h3>5 последних прохождений</h3>
        <p v-if="analytics.recent_attempts.length === 0" class="muted">Пока нет прохождений.</p>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Когда</th>
                <th>Пользователь</th>
                <th>Тест</th>
                <th>Результат</th>
                <th>Время</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="attempt in analytics.recent_attempts" :key="attempt.id">
                <td>{{ formatDate(attempt.finished_at) }}</td>
                <td>{{ attempt.user_name }}</td>
                <td>{{ attempt.test_title }}</td>
                <td>{{ attempt.correct_answers }}/{{ attempt.total_questions }}</td>
                <td>{{ attempt.duration_seconds ?? "-" }}</td>
                <td>
                  <button type="button" class="ghost" @click="openAttemptDetail(attempt.id)">Открыть</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3>Проблемные вопросы</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Тест</th>
                <th>Вопрос</th>
                <th>Попыток</th>
                <th>Ошибок</th>
                <th>Доля ошибок</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="question in analytics.question_analytics.slice(0, 50)" :key="question.question_id">
                <td>{{ question.test_title }}</td>
                <td>{{ question.question_text }}</td>
                <td>{{ question.total_attempts }}</td>
                <td>{{ question.wrong_attempts }}</td>
                <td>{{ formatPercent(question.wrong_rate) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3>Кто где ошибается</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Попыток</th>
                <th>Ответов</th>
                <th>Ошибок</th>
                <th>Доля ошибок</th>
                <th>Среднее время</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in analytics.user_analytics" :key="user.user_id">
                <td>
                  <div>{{ user.user_name }}</div>
                  <div class="muted" style="font-size: 12px">{{ user.user_email }}</div>
                </td>
                <td>{{ user.attempts_count }}</td>
                <td>{{ user.total_answers }}</td>
                <td>{{ user.wrong_answers }}</td>
                <td>{{ formatPercent(user.wrong_rate) }}</td>
                <td>{{ user.avg_duration_seconds?.toFixed(1) ?? "-" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3>Все прохождения</h3>
        <div class="analytics-filters">
          <div>
            <label>Ресторан</label>
            <select v-model="filterRestaurant">
              <option value="">Все рестораны</option>
              <option v-for="item in availableRestaurants" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div>
            <label>Роль</label>
            <select v-model="filterRole">
              <option value="">Все роли</option>
              <option v-for="item in availableRoles" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div>
            <label>Имя или email</label>
            <input v-model="filterUser" placeholder="Введите имя или email" />
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Пользователь</th>
                <th>Ресторан / роль</th>
                <th>Тест</th>
                <th>Результат</th>
                <th>Время</th>
                <th>Начало</th>
                <th>Окончание</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="attempt in filteredAttempts" :key="attempt.id">
                <td>{{ attempt.id }}</td>
                <td>
                  <div>{{ attempt.user_name }}</div>
                  <div class="muted" style="font-size: 12px">{{ attempt.user_email }}</div>
                </td>
                <td>{{ attempt.user_restaurant || "-" }} / {{ attempt.user_job_title || "-" }}</td>
                <td>{{ attempt.test_title }}</td>
                <td>{{ attempt.correct_answers }}/{{ attempt.total_questions }}</td>
                <td>{{ attempt.duration_seconds ?? "-" }}</td>
                <td>{{ formatDate(attempt.started_at) }}</td>
                <td>{{ formatDate(attempt.finished_at) }}</td>
                <td>
                  <button type="button" class="ghost" @click="openAttemptDetail(attempt.id)">Открыть</button>
                </td>
              </tr>
              <tr v-if="filteredAttempts.length === 0">
                <td colspan="9" class="muted">По выбранным фильтрам нет данных.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>

  <section v-else class="card">
    <h2>Аналитика тестов</h2>
    <p class="error">Доступ только для суперадмина.</p>
  </section>

  <div v-if="detailOpen" class="modal-backdrop" @click.self="closeAttemptDetail">
    <div class="card modal-card">
      <div class="actions-row">
        <h3 style="margin: 0">Детали прохождения</h3>
        <button type="button" class="ghost" @click="closeAttemptDetail">Закрыть</button>
      </div>
      <p v-if="detailLoading">Загрузка...</p>
      <template v-else-if="selectedAttempt">
        <div class="attempt-header-grid">
          <div class="clean-item">
            <p class="muted">Пользователь</p>
            <p><strong>{{ selectedAttempt.attempt.user_name }}</strong></p>
            <p class="muted" style="font-size: 12px">{{ selectedAttempt.attempt.user_email }}</p>
          </div>
          <div class="clean-item">
            <p class="muted">Тест</p>
            <p><strong>{{ selectedAttempt.attempt.test_title }}</strong></p>
          </div>
          <div class="clean-item">
            <p class="muted">Результат</p>
            <p><strong>{{ selectedAttempt.attempt.correct_answers }}/{{ selectedAttempt.attempt.total_questions }}</strong></p>
          </div>
          <div class="clean-item">
            <p class="muted">Время</p>
            <p><strong>{{ selectedAttempt.attempt.duration_seconds ?? "-" }} сек.</strong></p>
            <p class="muted" style="font-size: 12px">{{ formatDate(selectedAttempt.attempt.finished_at) }}</p>
          </div>
        </div>

        <div class="attempt-result-list">
          <div class="clean-item" v-for="item in selectedAttempt.results" :key="item.question_id">
            <div class="actions-row">
              <p style="margin: 0"><strong>{{ item.question_text }}</strong></p>
              <span class="result-pill" :class="item.is_correct ? 'result-pill-success' : 'result-pill-error'">
                {{ item.is_correct ? "Верно" : "Неверно" }}
              </span>
            </div>
            <hr class="result-divider" />
            <p><strong>Ваш ответ:</strong> {{ item.selected_options.join(", ") || "Не выбран" }}</p>
            <p><strong>Правильный ответ:</strong> {{ item.correct_options.join(", ") || "—" }}</p>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
