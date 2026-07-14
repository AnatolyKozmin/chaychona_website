<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
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
    question_id: number | null;
    question_text: string;
    selected_options: string[];
    correct_options: string[];
    is_correct: boolean;
  }>;
}

interface ScoreboardTestRef {
  id: number;
  title: string;
}

interface ScoreboardCell {
  test_id: number;
  attempts_count: number;
  best_correct: number;
  best_total: number;
  best_percent: number;
  last_correct: number;
  last_total: number;
  last_percent: number;
  last_finished_at: string;
}

interface ScoreboardUser {
  user_id: string;
  user_name: string;
  user_email: string;
  user_restaurant: string | null;
  user_job_title: string | null;
  scores: ScoreboardCell[];
}

interface ScoreboardResponse {
  tests: ScoreboardTestRef[];
  users: ScoreboardUser[];
}

const route = useRoute();
const auth = useAuthStore();
const loading = ref(false);
const error = ref("");
const analytics = ref<AnalyticsResponse | null>(null);
const scoreboard = ref<ScoreboardResponse | null>(null);
const scoreMode = ref<"best" | "last">("best");
const scoreFilterUser = ref("");
const scoreFilterRestaurant = ref("");
const scoreFilterRole = ref("");
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

const scoreboardRestaurants = computed(() => {
  const source = scoreboard.value?.users ?? [];
  return [...new Set(source.map((u) => u.user_restaurant || "").filter(Boolean))].sort((a, b) => a.localeCompare(b));
});

const scoreboardRoles = computed(() => {
  const source = scoreboard.value?.users ?? [];
  return [...new Set(source.map((u) => u.user_job_title || "").filter(Boolean))].sort((a, b) => a.localeCompare(b));
});

const filteredScoreboardUsers = computed(() => {
  const source = scoreboard.value?.users ?? [];
  const nameQuery = scoreFilterUser.value.trim().toLowerCase();
  return source.filter((u) => {
    const matchesRestaurant = !scoreFilterRestaurant.value || (u.user_restaurant || "") === scoreFilterRestaurant.value;
    const matchesRole = !scoreFilterRole.value || (u.user_job_title || "") === scoreFilterRole.value;
    const haystack = `${u.user_name} ${u.user_email}`.toLowerCase();
    const matchesUser = !nameQuery || haystack.includes(nameQuery);
    return matchesRestaurant && matchesRole && matchesUser;
  });
});

/** Тесты-колонки: если фильтры сузили список людей, пустые колонки убираем. */
const visibleScoreboardTests = computed(() => {
  const tests = scoreboard.value?.tests ?? [];
  const users = filteredScoreboardUsers.value;
  const takenTestIds = new Set(users.flatMap((u) => u.scores.map((s) => s.test_id)));
  return tests.filter((t) => takenTestIds.has(t.id));
});

function scoreboardCell(user: ScoreboardUser, testId: number): ScoreboardCell | null {
  return user.scores.find((s) => s.test_id === testId) ?? null;
}

function cellPercent(cell: ScoreboardCell): number {
  return scoreMode.value === "best" ? cell.best_percent : cell.last_percent;
}

function cellScoreText(cell: ScoreboardCell): string {
  return scoreMode.value === "best"
    ? `${cell.best_correct}/${cell.best_total}`
    : `${cell.last_correct}/${cell.last_total}`;
}

function scoreCellClass(cell: ScoreboardCell): string {
  const p = cellPercent(cell);
  if (p >= 80) {
    return "score-cell--good";
  }
  if (p >= 50) {
    return "score-cell--mid";
  }
  return "score-cell--bad";
}

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
    const [analyticsResp, scoreboardResp] = await Promise.all([
      api.get<AnalyticsResponse>("/tests/analytics", {
        params: {
          limit_recent: 5,
          attempts_limit: 500
        }
      }),
      api.get<ScoreboardResponse>("/tests/scoreboard")
    ]);
    analytics.value = analyticsResp.data;
    scoreboard.value = scoreboardResp.data;
    filterRestaurant.value = "";
    filterRole.value = "";
    filterUser.value = (route.query.user as string) || "";
    scoreFilterUser.value = (route.query.user as string) || "";
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
      <div class="stat-row">
        <div class="stat-cell">
          <div class="k">Всего прохождений</div>
          <div class="v">{{ analytics.summary.total_attempts }}</div>
        </div>
        <div class="stat-cell">
          <div class="k">Уникальных пользователей</div>
          <div class="v">{{ analytics.summary.unique_users }}</div>
        </div>
        <div class="stat-cell">
          <div class="k">Средний результат</div>
          <div class="v">{{ analytics.summary.avg_score_percent.toFixed(1) }}<span class="unit">%</span></div>
        </div>
        <div v-if="analytics.summary.avg_duration_seconds !== null" class="stat-cell">
          <div class="k">Среднее время</div>
          <div class="v">{{ analytics.summary.avg_duration_seconds.toFixed(0) }}<span class="unit"> сек</span></div>
        </div>
      </div>

      <div class="card">
        <div class="actions-row" style="flex-wrap: wrap; gap: 10px">
          <h3 style="margin: 0">Баллы по тестам</h3>
          <div class="score-mode-toggle">
            <button
              type="button"
              class="score-mode-btn"
              :class="{ 'score-mode-btn--active': scoreMode === 'best' }"
              @click="scoreMode = 'best'"
            >
              Лучший результат
            </button>
            <button
              type="button"
              class="score-mode-btn"
              :class="{ 'score-mode-btn--active': scoreMode === 'last' }"
              @click="scoreMode = 'last'"
            >
              Последний результат
            </button>
          </div>
        </div>
        <p class="muted" style="margin: 8px 0 12px 0">
          Все сотрудники и их баллы по каждому тесту в одной таблице. Наведите на ячейку, чтобы увидеть число попыток и дату.
        </p>
        <div class="analytics-filters">
          <div>
            <label>Ресторан</label>
            <select v-model="scoreFilterRestaurant">
              <option value="">Все рестораны</option>
              <option v-for="item in scoreboardRestaurants" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div>
            <label>Роль</label>
            <select v-model="scoreFilterRole">
              <option value="">Все роли</option>
              <option v-for="item in scoreboardRoles" :key="item" :value="item">{{ item }}</option>
            </select>
          </div>
          <div>
            <label>Имя или email</label>
            <input v-model="scoreFilterUser" placeholder="Введите имя или email" />
          </div>
        </div>
        <p v-if="!scoreboard || scoreboard.users.length === 0" class="muted">Пока никто не проходил тесты.</p>
        <p v-else-if="filteredScoreboardUsers.length === 0" class="muted">По выбранным фильтрам нет данных.</p>
        <div v-else class="table-wrap">
          <table class="scoreboard-table">
            <thead>
              <tr>
                <th class="scoreboard-user-col">Сотрудник</th>
                <th v-for="test in visibleScoreboardTests" :key="test.id" class="scoreboard-test-col">
                  {{ test.title }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in filteredScoreboardUsers" :key="user.user_id">
                <td class="scoreboard-user-col">
                  <div>{{ user.user_name }}</div>
                  <div class="muted" style="font-size: 12px">{{ user.user_email }}</div>
                  <div class="muted" style="font-size: 12px">
                    {{ user.user_restaurant || "-" }} · {{ user.user_job_title || "-" }}
                  </div>
                </td>
                <td
                  v-for="test in visibleScoreboardTests"
                  :key="test.id"
                  class="score-cell"
                >
                  <template v-if="scoreboardCell(user, test.id)">
                    <span
                      class="score-badge"
                      :class="scoreCellClass(scoreboardCell(user, test.id)!)"
                      :title="`Попыток: ${scoreboardCell(user, test.id)!.attempts_count}, последняя: ${formatDate(scoreboardCell(user, test.id)!.last_finished_at)}`"
                    >
                      {{ cellScoreText(scoreboardCell(user, test.id)!) }}
                      <span class="score-badge-percent">{{ cellPercent(scoreboardCell(user, test.id)!).toFixed(0) }}%</span>
                    </span>
                    <span v-if="scoreboardCell(user, test.id)!.attempts_count > 1" class="muted score-attempts">
                      ×{{ scoreboardCell(user, test.id)!.attempts_count }}
                    </span>
                  </template>
                  <span v-else class="muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="filteredScoreboardUsers.length" class="status-legend">
          <span><i class="g"></i> ≥ 80% — норма</span>
          <span><i class="w"></i> 50–79% — пограничный</span>
          <span><i class="b"></i> &lt; 50% — провал</span>
          <span><i class="n"></i> — тест не пройден</span>
        </div>
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
                <th class="num">Результат</th>
                <th class="num">Время, с</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="attempt in analytics.recent_attempts" :key="attempt.id">
                <td>{{ formatDate(attempt.finished_at) }}</td>
                <td>{{ attempt.user_name }}</td>
                <td>{{ attempt.test_title }}</td>
                <td class="num">{{ attempt.correct_answers }}/{{ attempt.total_questions }}</td>
                <td class="num">{{ attempt.duration_seconds ?? "—" }}</td>
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
                <th class="num">Попыток</th>
                <th class="num">Ошибок</th>
                <th class="num">Доля ошибок</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="question in analytics.question_analytics.slice(0, 50)" :key="question.question_id">
                <td>{{ question.test_title }}</td>
                <td>{{ question.question_text }}</td>
                <td class="num">{{ question.total_attempts }}</td>
                <td class="num">{{ question.wrong_attempts }}</td>
                <td class="num">{{ formatPercent(question.wrong_rate) }}</td>
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
                <th class="num">Попыток</th>
                <th class="num">Ответов</th>
                <th class="num">Ошибок</th>
                <th class="num">Доля ошибок</th>
                <th class="num">Ср. время, с</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in analytics.user_analytics" :key="user.user_id">
                <td class="who">
                  <div class="nm">{{ user.user_name }}</div>
                  <div class="muted" style="font-size: 12px">{{ user.user_email }}</div>
                </td>
                <td class="num">{{ user.attempts_count }}</td>
                <td class="num">{{ user.total_answers }}</td>
                <td class="num">{{ user.wrong_answers }}</td>
                <td class="num">{{ formatPercent(user.wrong_rate) }}</td>
                <td class="num">{{ user.avg_duration_seconds?.toFixed(0) ?? "—" }}</td>
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
                <th class="num">ID</th>
                <th>Пользователь</th>
                <th>Ресторан / роль</th>
                <th>Тест</th>
                <th class="num">Результат</th>
                <th class="num">Время, с</th>
                <th>Начало</th>
                <th>Окончание</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="attempt in filteredAttempts" :key="attempt.id">
                <td class="num">{{ attempt.id }}</td>
                <td class="who">
                  <div class="nm">{{ attempt.user_name }}</div>
                  <div class="muted" style="font-size: 12px">{{ attempt.user_email }}</div>
                </td>
                <td>{{ attempt.user_restaurant || "—" }} / {{ attempt.user_job_title || "—" }}</td>
                <td>{{ attempt.test_title }}</td>
                <td class="num">{{ attempt.correct_answers }}/{{ attempt.total_questions }}</td>
                <td class="num">{{ attempt.duration_seconds ?? "—" }}</td>
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
          <div
            v-for="(item, itemIdx) in selectedAttempt.results"
            :key="itemIdx"
            class="test-result-card"
            :class="item.is_correct ? 'test-result-card--correct' : 'test-result-card--incorrect'"
          >
            <div class="test-result-icon" :class="item.is_correct ? 'test-result-icon--correct' : 'test-result-icon--incorrect'">
              <span v-if="item.is_correct">✓</span>
              <span v-else>✗</span>
            </div>
            <p class="test-result-question long-text">{{ item.question_text }}</p>
            <div class="test-result-answers">
              <p class="test-result-row">
                <span class="test-result-label">Ответ:</span>
                <span :class="item.is_correct ? 'test-result-value--correct' : 'test-result-value--incorrect'">
                  {{ item.selected_options.join(", ") || "Не выбран" }}
                </span>
              </p>
              <p v-if="!item.is_correct" class="test-result-row">
                <span class="test-result-label">Правильный:</span>
                <span class="test-result-value--correct">{{ item.correct_options.join(", ") || "—" }}</span>
              </p>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>
