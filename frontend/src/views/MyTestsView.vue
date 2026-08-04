<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";
import { useBodyScrollLock } from "../composables/useBodyScrollLock";

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
  question_id: number | null;
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

/*
 * Тест идёт по одному вопросу на экран. Раньше все вопросы висели одним
 * списком: на телефоне это стена текста, в которой теряешь место, и вдобавок
 * легко отправить тест, промотав мимо неотвеченного вопроса.
 */
const questionIndex = ref(0);

const currentQuestion = computed(() => activeTest.value?.questions[questionIndex.value] ?? null);
const questionsCount = computed(() => activeTest.value?.questions.length ?? 0);
const isLastQuestion = computed(() => questionIndex.value >= questionsCount.value - 1);
const currentAnswered = computed(() => {
  const question = currentQuestion.value;
  return question ? (answers.value[question.id] ?? []).length > 0 : false;
});

function isOptionSelected(questionId: number, optionId: number): boolean {
  return (answers.value[questionId] ?? []).includes(optionId);
}

function chooseOption(questionId: number, optionId: number, multiple: boolean) {
  if (multiple) {
    toggleMultiple(questionId, optionId, !isOptionSelected(questionId, optionId));
  } else {
    setSingle(questionId, optionId);
  }
}

function goNextQuestion() {
  if (!isLastQuestion.value) {
    questionIndex.value += 1;
  }
}

function goPrevQuestion() {
  if (questionIndex.value > 0) {
    questionIndex.value -= 1;
  }
}

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
    questionIndex.value = 0;
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
  questionIndex.value = 0;
  startedAt.value = null;
}

onMounted(async () => {
  await loadMyTests();
  await loadMyAttempts();
});
useBodyScrollLock(computed(() => attemptsModalOpen.value));
</script>

<template>
  <section class="card tests-page">
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
      <div class="actions-row tests-active-header">
        <h3 style="margin: 0">{{ activeTest.title }}</h3>
        <button type="button" class="ghost" @click="resetToList">К списку тестов</button>
      </div>
      <p class="muted">{{ activeTest.restaurant_name }} / {{ activeTest.job_title_name }}</p>
      <p class="muted" v-if="activeTest.description">{{ activeTest.description }}</p>
      <div v-if="!result" class="test-progress">
        <div class="muted">Отвечено {{ totalAnswered }} из {{ activeTest.questions.length }}</div>
        <div class="test-progress-bar">
          <div class="test-progress-fill" :style="{ width: `${progressPercent}%` }" />
        </div>
      </div>

      <template v-if="!result && currentQuestion">
        <div class="quiz-card">
          <p class="quiz-num">Вопрос {{ questionIndex + 1 }} из {{ questionsCount }}</p>
          <p class="quiz-text long-text">{{ currentQuestion.text }}</p>
          <p class="quiz-hint">
            {{ currentQuestion.question_type === "multiple" ? "Можно выбрать несколько ответов" : "Один правильный ответ" }}
          </p>

          <div class="quiz-options">
            <button
              v-for="option in currentQuestion.options"
              :key="option.id"
              type="button"
              class="quiz-option"
              :class="{ selected: isOptionSelected(currentQuestion.id, option.id) }"
              :aria-pressed="isOptionSelected(currentQuestion.id, option.id)"
              @click="chooseOption(currentQuestion.id, option.id, currentQuestion.question_type === 'multiple')"
            >
              <span
                class="quiz-mark"
                :class="{ multi: currentQuestion.question_type === 'multiple' }"
                aria-hidden="true"
              >✓</span>
              <span class="quiz-option-text">{{ option.text }}</span>
            </button>
          </div>
        </div>

        <div class="quiz-nav">
          <button
            v-if="questionIndex > 0"
            type="button"
            class="ghost quiz-back"
            @click="goPrevQuestion"
          >
            Назад
          </button>
          <button
            v-if="!isLastQuestion"
            type="button"
            class="quiz-next"
            :disabled="!currentAnswered"
            @click="goNextQuestion"
          >
            Дальше
          </button>
          <button
            v-else
            type="button"
            class="quiz-next"
            :disabled="!currentAnswered || submitting"
            @click="submitTest"
          >
            {{ submitting ? "Отправка..." : "Завершить тест" }}
          </button>
        </div>
      </template>

      <template v-else-if="result">
        <div class="test-summary-card">
          <p
            class="quiz-score"
            :class="scorePercent(result) >= 80 ? 'good' : scorePercent(result) >= 60 ? 'mid' : 'low'"
          >
            {{ scorePercent(result) }}%
          </p>
          <p class="quiz-score-note">
            {{ result.correct_answers }} из {{ result.total_questions }} верно
            <template v-if="result.duration_seconds !== null"> · {{ result.duration_seconds }} сек.</template>
          </p>
        </div>

        <div
          v-for="item in result.results"
          :key="item.question_id"
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
              <span class="test-result-label">Ваш ответ:</span>
              <span :class="item.is_correct ? 'test-result-value--correct' : 'test-result-value--incorrect'">
                {{ item.selected_options.join(", ") || "Не выбран" }}
              </span>
            </p>
            <p v-if="!item.is_correct" class="test-result-row">
              <span class="test-result-label">Правильный:</span>
              <span class="test-result-value--correct">{{ item.correct_options.join(", ") }}</span>
            </p>
          </div>
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
      <div v-else class="clean-list">
        <div v-for="attempt in filteredAttempts" :key="attempt.id" class="attempt-card">
          <div class="actions-row">
            <strong class="long-text">{{ attempt.test_title }}</strong>
            <span class="result-pill" :class="scorePercent(attempt) >= 70 ? 'result-pill-success' : 'result-pill-error'">
              {{ scorePercent(attempt) }}%
            </span>
          </div>
          <p class="muted" style="margin: 6px 0 0 0">{{ attempt.user_restaurant || "-" }}</p>
          <p class="muted" style="margin: 6px 0 0 0">
            {{ attempt.correct_answers }}/{{ attempt.total_questions }} • {{ attempt.duration_seconds ?? "-" }} сек.
          </p>
          <p class="muted" style="margin: 6px 0 0 0">{{ new Date(attempt.finished_at).toLocaleString() }}</p>
          <button type="button" class="ghost" style="margin-top: 8px" @click="openAttemptDetails(attempt.id)">Подробнее</button>
        </div>
      </div>
    </div>
  </section>

  <Transition name="fade-scale">
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
        <div
          v-for="(item, itemIdx) in selectedAttemptDetail.results"
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
              <span class="test-result-label">Ваш ответ:</span>
              <span :class="item.is_correct ? 'test-result-value--correct' : 'test-result-value--incorrect'">
                {{ item.selected_options.join(", ") || "Не выбран" }}
              </span>
            </p>
            <p v-if="!item.is_correct" class="test-result-row">
              <span class="test-result-label">Правильный:</span>
              <span class="test-result-value--correct">{{ item.correct_options.join(", ") }}</span>
            </p>
          </div>
        </div>
      </div>
      </div>
    </div>
  </Transition>
</template>
