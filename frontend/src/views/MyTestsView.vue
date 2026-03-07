<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";

type QuestionType = "single" | "multiple";

interface MyTest {
  id: number;
  title: string;
  description: string | null;
  restaurant_name: string;
  job_title_name: string;
}

interface TakeOption {
  id: number;
  text: string;
  sort_order: number;
}

interface TakeQuestion {
  id: number;
  text: string;
  question_type: QuestionType;
  sort_order: number;
  options: TakeOption[];
}

interface TakeTest {
  id: number;
  title: string;
  description: string | null;
  restaurant_name: string;
  job_title_name: string;
  questions: TakeQuestion[];
}

interface SubmitQuestionResult {
  question_id: number;
  question_text: string;
  correct_options: string[];
  selected_options: string[];
  is_correct: boolean;
}

interface SubmitResult {
  attempt_id: number;
  started_at: string | null;
  finished_at: string;
  duration_seconds: number | null;
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
  results: SubmitQuestionResult[];
}

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

interface AttemptQuestionDetail {
  question_id: number;
  question_text: string;
  selected_options: string[];
  correct_options: string[];
  is_correct: boolean;
}

interface AttemptDetail {
  attempt: AttemptItem;
  results: AttemptQuestionDetail[];
}

type TestsTab = "available" | "attempts";

const loading = ref(false);
const submitting = ref(false);
const error = ref("");
const tests = ref<MyTest[]>([]);
const activeTest = ref<TakeTest | null>(null);
const result = ref<SubmitResult | null>(null);
const answers = ref<Record<number, number[]>>({});
const startedAt = ref<string | null>(null);
const tab = ref<TestsTab>("available");
const attemptsLoading = ref(false);
const attempts = ref<AttemptItem[]>([]);
const attemptsModalOpen = ref(false);
const selectedAttemptDetail = ref<AttemptDetail | null>(null);
const attemptsQuery = ref("");

const hasActiveTest = computed(() => Boolean(activeTest.value));
const totalAnswered = computed(() => {
  if (!activeTest.value) {
    return 0;
  }
  return activeTest.value.questions.filter((q) => (answers.value[q.id] ?? []).length > 0).length;
});
const progressPercent = computed(() => {
  if (!activeTest.value || activeTest.value.questions.length === 0) {
    return 0;
  }
  return Math.round((totalAnswered.value / activeTest.value.questions.length) * 100);
});
const filteredAttempts = computed(() => {
  const query = attemptsQuery.value.trim().toLowerCase();
  if (!query) {
    return attempts.value;
  }
  return attempts.value.filter((attempt) => {
    return (
      attempt.test_title.toLowerCase().includes(query) ||
      (attempt.user_restaurant || "").toLowerCase().includes(query) ||
      (attempt.user_job_title || "").toLowerCase().includes(query)
    );
  });
});

function toggleMultiple(questionId: number, optionId: number, checked: boolean) {
  const current = new Set(answers.value[questionId] ?? []);
  if (checked) {
    current.add(optionId);
  } else {
    current.delete(optionId);
  }
  answers.value[questionId] = Array.from(current);
}

function setSingle(questionId: number, optionId: number) {
  answers.value[questionId] = [optionId];
}

async function loadMyTests() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<MyTest[]>("/tests/my");
    tests.value = data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить тесты";
  } finally {
    loading.value = false;
  }
}

async function loadMyAttempts() {
  attemptsLoading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<AttemptItem[]>("/tests/my-attempts");
    attempts.value = data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить попытки";
  } finally {
    attemptsLoading.value = false;
  }
}

async function openAttemptDetails(attemptId: number) {
  attemptsLoading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<AttemptDetail>(`/tests/my-attempts/${attemptId}`);
    selectedAttemptDetail.value = data;
    attemptsModalOpen.value = true;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось открыть детали попытки";
  } finally {
    attemptsLoading.value = false;
  }
}

function closeAttemptModal() {
  attemptsModalOpen.value = false;
  selectedAttemptDetail.value = null;
}

function scorePercent(item: { total_questions: number; correct_answers: number }): number {
  if (!item.total_questions) {
    return 0;
  }
  return Math.round((item.correct_answers / item.total_questions) * 100);
}

async function startTest(testId: number) {
  loading.value = true;
  error.value = "";
  result.value = null;
  try {
    const { data } = await api.get<TakeTest>(`/tests/${testId}/take`);
    activeTest.value = data;
    answers.value = {};
    startedAt.value = new Date().toISOString();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось открыть тест";
  } finally {
    loading.value = false;
  }
}

async function submitTest() {
  if (!activeTest.value) {
    return;
  }
  submitting.value = true;
  error.value = "";
  try {
    const payload = {
      answers: activeTest.value.questions.map((question) => ({
        question_id: question.id,
        option_ids: answers.value[question.id] ?? []
      })),
      started_at: startedAt.value
    };
    const { data } = await api.post<SubmitResult>(`/tests/${activeTest.value.id}/submit`, payload);
    result.value = data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось отправить ответы";
  } finally {
    submitting.value = false;
  }
}

function resetToList() {
  activeTest.value = null;
  result.value = null;
  answers.value = {};
  startedAt.value = null;
}

onMounted(async () => {
  await loadMyTests();
  await loadMyAttempts();
});
</script>

<template>
  <section class="card">
    <h2>Мои тесты</h2>
    <p class="muted">Выберите тест и пройдите его. После отправки увидите разбор, правильные ответы и историю попыток.</p>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="tests-tabs">
      <button type="button" class="tests-tab" :class="{ active: tab === 'available' }" @click="tab = 'available'">
        Доступные тесты
      </button>
      <button type="button" class="tests-tab" :class="{ active: tab === 'attempts' }" @click="tab = 'attempts'">
        Мои прохождения
      </button>
    </div>

    <div v-if="tab === 'available' && !hasActiveTest">
      <p v-if="loading">Загрузка...</p>
      <p v-else-if="tests.length === 0" class="muted">Для вас пока нет доступных тестов.</p>
      <div v-else class="test-card-grid">
        <button
          v-for="test in tests"
          :key="test.id"
          type="button"
          class="ghost test-card"
          @click="startTest(test.id)"
        >
          <div class="test-card-title">{{ test.title }}</div>
          <div class="muted test-card-meta">{{ test.restaurant_name }} • {{ test.job_title_name }}</div>
          <div class="muted test-card-desc" v-if="test.description">
            {{ test.description }}
          </div>
          <div class="test-card-action">Начать тест</div>
        </button>
      </div>
    </div>

    <div v-else-if="tab === 'available' && activeTest">
      <div class="actions-row">
        <h3 style="margin: 0">{{ activeTest.title }}</h3>
        <button type="button" class="ghost" @click="resetToList">К списку тестов</button>
      </div>
      <p class="muted">{{ activeTest.restaurant_name }} / {{ activeTest.job_title_name }}</p>
      <p class="muted" v-if="activeTest.description">{{ activeTest.description }}</p>
      <div v-if="!result" class="test-progress">
        <div class="muted">Прогресс: {{ totalAnswered }}/{{ activeTest.questions.length }} ({{ progressPercent }}%)</div>
        <div class="test-progress-bar">
          <div class="test-progress-fill" :style="{ width: `${progressPercent}%` }" />
        </div>
      </div>

      <template v-if="!result">
        <div v-for="(question, idx) in activeTest.questions" :key="question.id" class="clean-item">
          <h4 style="margin: 0 0 8px">Вопрос {{ idx + 1 }}</h4>
          <p class="long-text" style="margin-top: 0">{{ question.text }}</p>
          <label
            v-for="option in question.options"
            :key="option.id"
            class="answer-option"
            :class="{
              selected:
                question.question_type === 'multiple'
                  ? (answers[question.id] ?? []).includes(option.id)
                  : (answers[question.id] ?? [])[0] === option.id
            }"
          >
            <span class="answer-option-text">{{ option.text }}</span>
            <input
              v-if="question.question_type === 'multiple'"
              type="checkbox"
              :checked="(answers[question.id] ?? []).includes(option.id)"
              @change="toggleMultiple(question.id, option.id, ($event.target as HTMLInputElement).checked)"
            />
            <input
              v-else
              type="radio"
              :name="`question-${question.id}`"
              :checked="(answers[question.id] ?? [])[0] === option.id"
              @change="setSingle(question.id, option.id)"
            />
          </label>
        </div>
        <button type="button" :disabled="submitting" @click="submitTest">Завершить тест</button>
      </template>

      <template v-else>
        <div class="clean-item">
          <h3 style="margin-top: 0">Результат</h3>
          <p><strong>Всего вопросов:</strong> {{ result.total_questions }}</p>
          <p><strong>Правильно:</strong> {{ result.correct_answers }}</p>
          <p><strong>Неправильно:</strong> {{ result.incorrect_answers }}</p>
          <p><strong>Процент:</strong> {{ scorePercent(result) }}%</p>
          <p v-if="result.duration_seconds !== null"><strong>Время прохождения:</strong> {{ result.duration_seconds }} сек.</p>
        </div>

        <div class="clean-item" v-for="item in result.results" :key="item.question_id">
          <p class="long-text" style="margin-top: 0"><strong>{{ item.question_text }}</strong></p>
          <p>
            <strong>Статус:</strong>
            <span :class="item.is_correct ? 'muted' : 'error'">{{ item.is_correct ? "Верно" : "Неверно" }}</span>
          </p>
          <p><strong>Ваш ответ:</strong> {{ item.selected_options.join(", ") || "Не выбран" }}</p>
          <p><strong>Правильный ответ:</strong> {{ item.correct_options.join(", ") }}</p>
        </div>
      </template>
    </div>

    <div v-else-if="tab === 'attempts'" class="clean-list">
      <div class="actions-row">
        <input v-model="attemptsQuery" placeholder="Поиск: тест, ресторан, должность" />
        <button type="button" class="ghost" :disabled="attemptsLoading" @click="loadMyAttempts">Обновить</button>
      </div>
      <p v-if="attemptsLoading">Загрузка...</p>
      <p v-else-if="filteredAttempts.length === 0" class="muted">Прохождений пока нет.</p>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Тест</th>
              <th>Ресторан</th>
              <th>Результат</th>
              <th>Время</th>
              <th>Дата</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="attempt in filteredAttempts" :key="attempt.id">
              <td>{{ attempt.test_title }}</td>
              <td>{{ attempt.user_restaurant || "-" }}</td>
              <td>{{ attempt.correct_answers }}/{{ attempt.total_questions }} ({{ scorePercent(attempt) }}%)</td>
              <td>{{ attempt.duration_seconds ?? "-" }} сек.</td>
              <td>{{ new Date(attempt.finished_at).toLocaleString() }}</td>
              <td>
                <button type="button" class="ghost" @click="openAttemptDetails(attempt.id)">Подробнее</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <div v-if="attemptsModalOpen && selectedAttemptDetail" class="modal-backdrop" @click.self="closeAttemptModal">
    <div class="modal-window modal-window-wide">
      <div class="actions-row">
        <h3 style="margin: 0">Результат прохождения</h3>
        <button type="button" class="ghost" @click="closeAttemptModal">Закрыть</button>
      </div>
      <div class="attempt-header-grid">
        <div class="clean-item">
          <strong>Тест</strong>
          <p style="margin: 6px 0 0 0">{{ selectedAttemptDetail.attempt.test_title }}</p>
        </div>
        <div class="clean-item">
          <strong>Результат</strong>
          <p style="margin: 6px 0 0 0">
            {{ selectedAttemptDetail.attempt.correct_answers }}/{{ selectedAttemptDetail.attempt.total_questions }}
            ({{ scorePercent(selectedAttemptDetail.attempt) }}%)
          </p>
        </div>
        <div class="clean-item">
          <strong>Время</strong>
          <p style="margin: 6px 0 0 0">{{ selectedAttemptDetail.attempt.duration_seconds ?? "-" }} сек.</p>
        </div>
      </div>

      <div class="attempt-result-list" style="margin-top: 10px">
        <div class="clean-item" v-for="item in selectedAttemptDetail.results" :key="item.question_id">
          <div class="actions-row">
            <strong class="long-text" style="margin: 0">{{ item.question_text }}</strong>
            <span class="result-pill" :class="item.is_correct ? 'result-pill-success' : 'result-pill-error'">
              {{ item.is_correct ? "Верно" : "Неверно" }}
            </span>
          </div>
          <hr class="result-divider" />
          <p><strong>Ваш ответ:</strong> {{ item.selected_options.join(", ") || "Не выбран" }}</p>
          <p><strong>Правильный ответ:</strong> {{ item.correct_options.join(", ") }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
