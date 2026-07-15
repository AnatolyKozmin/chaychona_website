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

interface DirectoryUser {
  id: string;
  email: string;
  full_name: string;
  restaurant: string | null;
  role: string;
  job_title: string | null;
  is_active: boolean;
}

interface EmployeeScoreRow {
  key: string;
  name: string;
  email: string;
  jobTitle: string;
  scores: Array<{ testId: number; testTitle: string; cell: ScoreboardCell }>;
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

type AnalyticsTab = "overview" | "restaurant" | "scores" | "attempts" | "questions" | "users";
const activeTab = ref<AnalyticsTab>("overview");

const directory = ref<DirectoryUser[]>([]);
const selectedRestaurant = ref("");
const restaurantSearch = ref("");
const scoreView = ref<"byTest" | "matrix">("byTest");
const selectedTestId = ref<number | null>(null);

// Постраничная навигация по «Проблемным вопросам» (окно + язычки)
const questionsPage = ref(1);
const QUESTIONS_PAGE_SIZE = 12;

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

/** Строки «сотрудник + его баллы по тестам» для одного ресторана.
 *  База — активные learner'ы из справочника (видно и тех, кто ничего не сдавал),
 *  плюс люди из scoreboard с этим рестораном, которых в справочнике уже нет. */
function buildRestaurantRows(restaurant: string): EmployeeScoreRow[] {
  if (!restaurant) {
    return [];
  }
  const testTitleById = new Map((scoreboard.value?.tests ?? []).map((t) => [t.id, t.title]));
  const scoresByUserId = new Map((scoreboard.value?.users ?? []).map((u) => [u.user_id, u]));

  function makeRow(id: string, name: string, email: string, jobTitle: string): EmployeeScoreRow {
    const scores = (scoresByUserId.get(id)?.scores ?? [])
      .map((cell) => ({
        testId: cell.test_id,
        testTitle: testTitleById.get(cell.test_id) ?? "",
        cell
      }))
      .filter((s) => s.testTitle)
      .sort((a, b) => a.testTitle.localeCompare(b.testTitle, "ru"));
    return { key: id, name, email, jobTitle, scores };
  }

  const rows: EmployeeScoreRow[] = [];
  const seen = new Set<string>();
  for (const u of directory.value) {
    if (u.role !== "learner" || !u.is_active || (u.restaurant || "") !== restaurant) {
      continue;
    }
    seen.add(u.id);
    rows.push(makeRow(u.id, u.full_name, u.email, u.job_title || ""));
  }
  for (const sbUser of scoreboard.value?.users ?? []) {
    if ((sbUser.user_restaurant || "") !== restaurant || seen.has(sbUser.user_id)) {
      continue;
    }
    rows.push(makeRow(sbUser.user_id, sbUser.user_name, sbUser.user_email, sbUser.user_job_title || ""));
  }
  return rows;
}

/** Язычки ресторанов: справочник сотрудников + рестораны из scoreboard. */
const restaurantOptions = computed(() => {
  const names = new Set<string>();
  for (const u of directory.value) {
    if (u.role === "learner" && u.is_active && u.restaurant) {
      names.add(u.restaurant);
    }
  }
  for (const u of scoreboard.value?.users ?? []) {
    if (u.user_restaurant) {
      names.add(u.user_restaurant);
    }
  }
  return [...names]
    .sort((a, b) => a.localeCompare(b, "ru"))
    .map((name) => ({ name, employees: buildRestaurantRows(name).length }));
});

const restaurantRows = computed(() => buildRestaurantRows(selectedRestaurant.value));

/** Поиск + порядок: сначала сдававшие (по алфавиту), затем не сдававшие. */
const visibleRestaurantRows = computed(() => {
  const q = restaurantSearch.value.trim().toLowerCase();
  return restaurantRows.value
    .filter((r) => !q || `${r.name} ${r.email}`.toLowerCase().includes(q))
    .sort((a, b) => {
      const aEmpty = a.scores.length === 0 ? 1 : 0;
      const bEmpty = b.scores.length === 0 ? 1 : 0;
      return aEmpty - bEmpty || a.name.localeCompare(b.name, "ru");
    });
});

function rowAvgPercent(row: EmployeeScoreRow): number | null {
  if (row.scores.length === 0) {
    return null;
  }
  return row.scores.reduce((sum, s) => sum + cellPercent(s.cell), 0) / row.scores.length;
}

function avgBadgeClass(percent: number): string {
  if (percent >= 80) {
    return "score-cell--good";
  }
  if (percent >= 50) {
    return "score-cell--mid";
  }
  return "score-cell--bad";
}

const restaurantSummary = computed(() => {
  const rows = restaurantRows.value;
  const tested = rows.filter((r) => r.scores.length > 0);
  const percents = tested.flatMap((r) => r.scores.map((s) => cellPercent(s.cell)));
  return {
    employees: rows.length,
    tested: tested.length,
    avgPercent: percents.length ? percents.reduce((a, b) => a + b, 0) / percents.length : null
  };
});

const questionRows = computed(() => analytics.value?.question_analytics ?? []);
const questionsTotalPages = computed(() =>
  Math.max(1, Math.ceil(questionRows.value.length / QUESTIONS_PAGE_SIZE))
);
const pagedQuestions = computed(() => {
  const start = (questionsPage.value - 1) * QUESTIONS_PAGE_SIZE;
  return questionRows.value.slice(start, start + QUESTIONS_PAGE_SIZE);
});
const questionsRangeFrom = computed(() =>
  questionRows.value.length === 0 ? 0 : (questionsPage.value - 1) * QUESTIONS_PAGE_SIZE + 1
);
const questionsRangeTo = computed(() =>
  Math.min(questionsPage.value * QUESTIONS_PAGE_SIZE, questionRows.value.length)
);

/** Язычки страниц с многоточиями: 1 … 4 5 [6] 7 8 … 20 */
const questionPageTabs = computed<Array<number | "gap">>(() => {
  const total = questionsTotalPages.value;
  const current = questionsPage.value;
  const tabs: Array<number | "gap"> = [];
  for (let p = 1; p <= total; p++) {
    if (p === 1 || p === total || (p >= current - 2 && p <= current + 2)) {
      tabs.push(p);
    } else if (tabs[tabs.length - 1] !== "gap") {
      tabs.push("gap");
    }
  }
  return tabs;
});

function goQuestionsPage(page: number) {
  questionsPage.value = Math.min(Math.max(1, page), questionsTotalPages.value);
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
    const [analyticsResp, scoreboardResp, usersResp] = await Promise.all([
      api.get<AnalyticsResponse>("/tests/analytics", {
        params: {
          limit_recent: 5,
          attempts_limit: 500
        }
      }),
      api.get<ScoreboardResponse>("/tests/scoreboard"),
      api.get<DirectoryUser[]>("/users")
    ]);
    analytics.value = analyticsResp.data;
    scoreboard.value = scoreboardResp.data;
    directory.value = usersResp.data;
    questionsPage.value = 1;
    if (!selectedRestaurant.value || !restaurantOptions.value.some((r) => r.name === selectedRestaurant.value)) {
      selectedRestaurant.value = restaurantOptions.value[0]?.name ?? "";
    }
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
        <button type="button" class="tests-tab" :class="{ active: activeTab === 'restaurant' }" @click="activeTab = 'restaurant'">По ресторану</button>
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

      <div v-if="activeTab === 'restaurant'" class="card">
        <div class="actions-row" style="flex-wrap: wrap; gap: 10px">
          <h3 style="margin: 0">Результаты по ресторану</h3>
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

        <p v-if="restaurantOptions.length === 0" class="muted">Пока нет сотрудников, привязанных к ресторанам.</p>

        <template v-else>
          <!-- Язычки ресторанов -->
          <div class="rest-chips">
            <button
              v-for="opt in restaurantOptions"
              :key="opt.name"
              type="button"
              class="rest-chip"
              :class="{ 'rest-chip--active': opt.name === selectedRestaurant }"
              @click="selectedRestaurant = opt.name"
            >
              {{ opt.name }}
              <span class="rest-chip-count">{{ opt.employees }}</span>
            </button>
          </div>

          <!-- Сводка по выбранному ресторану -->
          <div class="rest-summary">
            <div class="rest-summary-item">
              <span class="rest-summary-value">{{ restaurantSummary.employees }}</span>
              <span class="rest-summary-label">сотрудников</span>
            </div>
            <div class="rest-summary-item">
              <span class="rest-summary-value">{{ restaurantSummary.tested }}</span>
              <span class="rest-summary-label">проходили тесты</span>
            </div>
            <div class="rest-summary-item">
              <span class="rest-summary-value">
                {{ restaurantSummary.avgPercent !== null ? restaurantSummary.avgPercent.toFixed(0) + "%" : "—" }}
              </span>
              <span class="rest-summary-label">средний балл</span>
            </div>
          </div>

          <div style="max-width: 320px; margin: 0 0 12px">
            <label>Поиск сотрудника</label>
            <input v-model="restaurantSearch" placeholder="Имя или email" />
          </div>

          <p v-if="visibleRestaurantRows.length === 0" class="muted">По выбранным условиям нет сотрудников.</p>
          <div v-else class="table-wrap">
            <table class="rest-table">
              <thead>
                <tr>
                  <th>Сотрудник</th>
                  <th>Должность</th>
                  <th>Тест</th>
                  <th>Балл ({{ scoreMode === "best" ? "лучший" : "последний" }})</th>
                  <th>Последняя попытка</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="row in visibleRestaurantRows" :key="row.key">
                  <tr class="rest-row-first">
                    <td :rowspan="Math.max(1, row.scores.length)" class="rest-name-cell">
                      <div>{{ row.name }}</div>
                      <div class="muted" style="font-size: 12px">{{ row.email }}</div>
                      <span
                        v-if="rowAvgPercent(row) !== null"
                        class="score-badge rest-avg-badge"
                        :class="avgBadgeClass(rowAvgPercent(row)!)"
                        title="Средний балл по всем тестам сотрудника"
                      >
                        среднее {{ rowAvgPercent(row)!.toFixed(0) }}%
                      </span>
                    </td>
                    <td :rowspan="Math.max(1, row.scores.length)" class="rest-job-cell">
                      {{ row.jobTitle || "—" }}
                    </td>
                    <template v-if="row.scores.length > 0">
                      <td>{{ row.scores[0].testTitle }}</td>
                      <td>
                        <span class="score-badge" :class="scoreCellClass(row.scores[0].cell)">
                          {{ cellScoreText(row.scores[0].cell) }}
                          <span class="score-badge-percent">{{ cellPercent(row.scores[0].cell).toFixed(0) }}%</span>
                        </span>
                        <span v-if="row.scores[0].cell.attempts_count > 1" class="muted score-attempts">
                          ×{{ row.scores[0].cell.attempts_count }}
                        </span>
                      </td>
                      <td class="muted">{{ formatDate(row.scores[0].cell.last_finished_at) }}</td>
                    </template>
                    <template v-else>
                      <td colspan="3" class="muted">Тестов пока не проходил</td>
                    </template>
                  </tr>
                  <tr v-for="score in row.scores.slice(1)" :key="score.testId">
                    <td>{{ score.testTitle }}</td>
                    <td>
                      <span class="score-badge" :class="scoreCellClass(score.cell)">
                        {{ cellScoreText(score.cell) }}
                        <span class="score-badge-percent">{{ cellPercent(score.cell).toFixed(0) }}%</span>
                      </span>
                      <span v-if="score.cell.attempts_count > 1" class="muted score-attempts">
                        ×{{ score.cell.attempts_count }}
                      </span>
                    </td>
                    <td class="muted">{{ formatDate(score.cell.last_finished_at) }}</td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </template>
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
        <div class="actions-row" style="flex-wrap: wrap; gap: 10px">
          <h3 style="margin: 0">Проблемные вопросы</h3>
          <span class="pager-info" v-if="questionRows.length">
            {{ questionsRangeFrom }}–{{ questionsRangeTo }} из {{ questionRows.length }}
          </span>
        </div>

        <p v-if="questionRows.length === 0" class="muted">Пока нет данных по вопросам.</p>

        <template v-else>
          <!-- Язычки страниц сверху — листать не прокручивая -->
          <div v-if="questionsTotalPages > 1" class="pager" style="margin-top: 8px">
            <button
              type="button"
              class="pager-btn"
              :disabled="questionsPage === 1"
              @click="goQuestionsPage(questionsPage - 1)"
            >
              ‹
            </button>
            <template v-for="(tab, i) in questionPageTabs" :key="i">
              <span v-if="tab === 'gap'" class="pager-ellipsis">…</span>
              <button
                v-else
                type="button"
                class="pager-btn"
                :class="{ 'pager-btn--active': tab === questionsPage }"
                @click="goQuestionsPage(tab)"
              >
                {{ tab }}
              </button>
            </template>
            <button
              type="button"
              class="pager-btn"
              :disabled="questionsPage === questionsTotalPages"
              @click="goQuestionsPage(questionsPage + 1)"
            >
              ›
            </button>
          </div>

          <div class="table-wrap" style="margin-top: 12px">
            <table>
              <thead>
                <tr>
                  <th style="width: 44px">#</th>
                  <th>Тест</th>
                  <th>Вопрос</th>
                  <th>Попыток</th>
                  <th>Ошибок</th>
                  <th>Доля ошибок</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(question, idx) in pagedQuestions" :key="question.question_id">
                  <td class="muted">{{ questionsRangeFrom + idx }}</td>
                  <td>{{ question.test_title }}</td>
                  <td>{{ question.question_text }}</td>
                  <td>{{ question.total_attempts }}</td>
                  <td>{{ question.wrong_attempts }}</td>
                  <td>{{ formatPercent(question.wrong_rate) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
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

<style scoped>
.pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.pager-btn {
  width: auto;
  margin: 0;
  min-width: 36px;
  padding: 6px 11px;
  border: 1px solid #d0d8e5;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.pager-btn:hover:not(:disabled) {
  background: #f5f8ff;
  border-color: #c5d4f0;
  color: #1d4ed8;
}
.pager-btn--active,
.pager-btn--active:hover {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.pager-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.pager-ellipsis {
  color: #94a3b8;
  padding: 0 2px;
}
.pager-info {
  font-size: 13px;
  color: #64748b;
}

/* Вкладка «По ресторану» */
.rest-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0 16px;
}
.rest-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: auto;
  margin: 0;
  padding: 8px 14px;
  border: 1px solid #d0d8e5;
  border-radius: 999px;
  background: #fff;
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.rest-chip:hover {
  background: #f5f8ff;
  border-color: #c5d4f0;
  color: #1d4ed8;
}
.rest-chip--active,
.rest-chip--active:hover {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.rest-chip-count {
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
  font-size: 12px;
}
.rest-chip--active .rest-chip-count {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
}
.rest-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 0 0 14px;
}
.rest-summary-item {
  display: flex;
  align-items: baseline;
  gap: 7px;
  padding: 8px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #f8fafc;
}
.rest-summary-value {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}
.rest-summary-label {
  font-size: 13px;
  color: #64748b;
}
/* Группировка строк по сотруднику */
.rest-table td {
  vertical-align: top;
}
.rest-row-first td {
  border-top: 2px solid #e2e8f0;
}
.rest-name-cell {
  min-width: 200px;
}
.rest-job-cell {
  min-width: 130px;
}
.rest-avg-badge {
  margin-top: 6px;
  font-size: 12px;
}
</style>
