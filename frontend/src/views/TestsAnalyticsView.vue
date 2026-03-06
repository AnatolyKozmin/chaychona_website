<script setup lang="ts">
import { onMounted, ref } from "vue";
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

const auth = useAuthStore();
const loading = ref(false);
const error = ref("");
const analytics = ref<AnalyticsResponse | null>(null);

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
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить аналитику";
  } finally {
    loading.value = false;
  }
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
              </tr>
            </thead>
            <tbody>
              <tr v-for="attempt in analytics.recent_attempts" :key="attempt.id">
                <td>{{ formatDate(attempt.finished_at) }}</td>
                <td>{{ attempt.user_name }}</td>
                <td>{{ attempt.test_title }}</td>
                <td>{{ attempt.correct_answers }}/{{ attempt.total_questions }}</td>
                <td>{{ attempt.duration_seconds ?? "-" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3>Все прохождения</h3>
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
              </tr>
            </thead>
            <tbody>
              <tr v-for="attempt in analytics.attempts" :key="attempt.id">
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
    </template>
  </section>

  <section v-else class="card">
    <h2>Аналитика тестов</h2>
    <p class="error">Доступ только для суперадмина.</p>
  </section>
</template>
