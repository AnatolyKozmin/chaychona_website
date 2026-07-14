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

type AnalyticsTab = "overview" | "scores" | "attempts" | "questions" | "users";
const activeTab = ref<AnalyticsTab>("overview");
const scoreView = ref<"byTest" | "matrix">("byTest");
const selectedTestId = ref<number | null>(null);

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

/** Все тесты для селектора вкладки «Баллы → По тесту». */
const allScoreboardTests = computed(() => scoreboard.value?.tests ?? []);

const selectedTest = computed(
  () => allScoreboardTests.value.find((t) => t.id === selectedTestId.value) ?? null
);

/** Рейтинг сотрудников по выбранному тесту (только сдавшие), отсортированный по убыванию. */
const perTestRows = computed(() => {
  if (selectedTestId.value == null) {
    return [] as Array<{ user: ScoreboardUser; cell: ScoreboardCell }>;
  }
  return filteredScoreboardUsers.value
    .map((user) => ({ user, cell: scoreboardCell(user, selectedTestId.value!) }))
    .filter((row): row is { user: ScoreboardUser; cell: ScoreboardCell } => row.cell !== null)
    .sort((a, b) => cellPercent(b.cell) - cellPercent(a.cell));
});

/** Сотрудники (в текущем фильтре), которые выбранный тест ещё не проходили. */
const perTestNotTaken = computed(() => {
  if (selectedTestId.value == null) {
    return [] as ScoreboardUser[];
  }
  return filteredScoreboardUsers.value.filter((user) => !scoreboardCell(user, selectedTestId.value!));
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
    if (selectedTestId.value == null || !scoreboardResp.data.tests.some((t) => t.id === selectedTestId.value)) {
      selectedTestId.value = scoreboardResp.data.tests[0]?.id ?? null;
    }
    filterRestaurant.value = "";
    filterRole.value = "";
    filterUser.value = (route.query.user as string) || "";
    scoreFilterUser.value = (route.query.user as string) || "";
    // Пришли по ссылке из карточки сотрудника — открываем список прохождений с фильтром.
    if (route.query.user) {
      activeTab.value = "attempts";
    }
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
      <div class="tests-tabs" role="tablist">
        <button type="button" class="tests-tab" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">Обзор</button>
        <button type="button" class="tests-tab" :class="{ active: activeTab === 'scores' }" @click="activeTab = 'scores'">Баллы по тестам</button>
        <button type="button" class="tests-tab" :class="{ active: activeTab === 'attempts' }" @click="activeTab = 'attempts'">Прохождения</button>
        <button type="button" class="tests-tab" :class="{ active: activeTab === 'questions' }" @click="activeTab = 'questions'">Проблемные вопросы</button>
        <button type="button" class="tests-tab" :class="{ active: activeTab === 'users' }" @click="activeTab = 'users'">Ошибки по людям</button>
      </div>

      <div v-if="activeTab === 'overview'" class="card">
        <h3>Сводка</h3>
        <p><strong>Всего прохождений:</strong> {{ analytics.summary.total_attempts }}</p>
        <p><strong>Уникальных пользователей:</strong> {{ analytics.summary.unique_users }}</p>
        <p><strong>Средний результат:</strong> {{ analytics.summary.avg_score_percent.toFixed(1) }}%</p>
        <p v-if="analytics.summary.avg_duration_seconds !== null">
          <strong>Среднее время:</strong> {{ analytics.summary.avg_duration_seconds.toFixed(1) }} сек.
        </p>
        <p class="muted" style="margin-top: 14px">
          Разделы вынесены во вкладки выше. «Баллы по тестам» удобнее смотреть в режиме «По тесту» — рейтинг сотрудников по одному тесту без горизонтальной прокрутки.
        </p>
      </div>

      <div v-if="activeTab === 'scores'" class="card">
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
          <div class="score-mode-toggle">
            <button
              type="button"
              class="score-mode-btn"
              :class="{ 'score-mode-btn--active': scoreView === 'byTest' }"
              @click="scoreView = 'byTest'"
            >
              По тесту
            </button>
            <button
              type="button"
              class="score-mode-btn"
              :class="{ 'score-mode-btn--active': scoreView === 'matrix' }"
              @click="scoreView = 'matrix'"
            >
              Матрица
            </button>
          </div>
        </div>
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

        <!-- Разрез по одному тесту: рейтинг сотрудников, нормальная ширина -->
        <template v-else-if="scoreView === 'byTest'">
          <div style="max-width: 460px; margin: 4px 0 14px">
            <label>Тест</label>
            <select v-model.number="selectedTestId">
              <option v-for="t in allScoreboardTests" :key="t.id" :value="t.id">{{ t.title }}</option>
            </select>
          </div>
          <p v-if="perTestRows.length === 0" class="muted">Этот тест пока никто не проходил (по текущим фильтрам).</p>
          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style="width: 44px">#</th>
                  <th>Сотрудник</th>
                  <th>Ресторан / роль</th>
                  <th>Результат ({{ scoreMode === 'best' ? 'лучший' : 'последний' }})</th>
                  <th>Попыток</th>
                  <th>Последняя попытка</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in perTestRows" :key="row.user.user_id">
                  <td class="muted">{{ idx + 1 }}</td>
                  <td>
                    <div>{{ row.user.user_name }}</div>
                    <div class="muted" style="font-size: 12px">{{ row.user.user_email }}</div>
                  </td>
                  <td>{{ row.user.user_restaurant || "-" }} / {{ row.user.user_job_title || "-" }}</td>
                  <td>
                    <span class="score-badge" :class="scoreCellClass(row.cell)">
                      {{ cellScoreText(row.cell) }}
                      <span class="score-badge-percent">{{ cellPercent(row.cell).toFixed(0) }}%</span>
                    </span>
                  </td>
                  <td>{{ row.cell.attempts_count }}</td>
                  <td>{{ formatDate(row.cell.last_finished_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="selectedTest && perTestNotTaken.length" class="muted" style="margin-top: 10px">
            Не проходили «{{ selectedTest.title }}»: {{ perTestNotTaken.length }} чел.
          </p>
        </template>

        <!-- Полная матрица: все тесты сразу (широкая, прокрутка по горизонтали) -->
        <template v-else>
          <p class="muted" style="margin: 0 0 12px 0">
            Все сотрудники и их баллы по каждому тесту сразу. Таблица широкая — прокручивается по горизонтали. Наведите на ячейку, чтобы увидеть число попыток и дату.
          </p>
          <div class="table-wrap">
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
        </template>
      </div>

      <div v-if="activeTab === 'attempts'" class="card">
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

      <div v-if="activeTab === 'questions'" class="card">
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

      <div v-if="activeTab === 'users'" class="card">
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

      <div v-if="activeTab === 'attempts'" class="card">
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
                <th>Пользователь</th>
                <th>Ресторан / роль</th>
                <th>Тест</th>
                <th>Результат</th>
                <th>Время, с</th>
                <th>Когда</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="attempt in filteredAttempts" :key="attempt.id">
                <td>
                  <div>{{ attempt.user_name }}</div>
                  <div class="muted" style="font-size: 12px">{{ attempt.user_email }}</div>
                </td>
                <td>{{ attempt.user_restaurant || "-" }} / {{ attempt.user_job_title || "-" }}</td>
                <td>{{ attempt.test_title }}</td>
                <td>{{ attempt.correct_answers }}/{{ attempt.total_questions }}</td>
                <td>{{ attempt.duration_seconds ?? "-" }}</td>
                <td>{{ formatDate(attempt.finished_at) }}</td>
                <td>
                  <button type="button" class="ghost" @click="openAttemptDetail(attempt.id)">Открыть</button>
                </td>
              </tr>
              <tr v-if="filteredAttempts.length === 0">
                <td colspan="7" class="muted">По выбранным фильтрам нет данных.</td>
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
