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

const loading = ref(false);
const submitting = ref(false);
const error = ref("");
const tests = ref<MyTest[]>([]);
const activeTest = ref<TakeTest | null>(null);
const result = ref<SubmitResult | null>(null);
const answers = ref<Record<number, number[]>>({});
const startedAt = ref<string | null>(null);

const hasActiveTest = computed(() => Boolean(activeTest.value));

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
});
</script>

<template>
  <section class="card">
    <h2>Мои тесты</h2>
    <p class="muted">Выберите тест и пройдите его. После отправки увидите разбор и правильные ответы.</p>
    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="!hasActiveTest">
      <p v-if="loading">Загрузка...</p>
      <p v-else-if="tests.length === 0" class="muted">Для вас пока нет доступных тестов.</p>
      <div v-else class="clean-list">
        <button
          v-for="test in tests"
          :key="test.id"
          type="button"
          class="ghost clean-item"
          style="display: block; width: 100%; text-align: left; padding: 10px 12px"
          @click="startTest(test.id)"
        >
          <div>{{ test.title }}</div>
          <div class="muted" style="font-size: 12px; margin-top: 4px">
            {{ test.restaurant_name }} • {{ test.job_title_name }}
          </div>
          <div class="muted" style="font-size: 12px; margin-top: 2px" v-if="test.description">
            {{ test.description }}
          </div>
        </button>
      </div>
    </div>

    <div v-else-if="activeTest">
      <div class="actions-row">
        <h3 style="margin: 0">{{ activeTest.title }}</h3>
        <button type="button" class="ghost" @click="resetToList">К списку тестов</button>
      </div>
      <p class="muted">{{ activeTest.restaurant_name }} / {{ activeTest.job_title_name }}</p>
      <p class="muted" v-if="activeTest.description">{{ activeTest.description }}</p>

      <template v-if="!result">
        <div v-for="(question, idx) in activeTest.questions" :key="question.id" class="clean-item">
          <h4 style="margin: 0 0 8px">Вопрос {{ idx + 1 }}</h4>
          <p style="margin-top: 0">{{ question.text }}</p>
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
          <p v-if="result.duration_seconds !== null"><strong>Время прохождения:</strong> {{ result.duration_seconds }} сек.</p>
        </div>

        <div class="clean-item" v-for="item in result.results" :key="item.question_id">
          <p style="margin-top: 0"><strong>{{ item.question_text }}</strong></p>
          <p>
            <strong>Статус:</strong>
            <span :class="item.is_correct ? 'muted' : 'error'">{{ item.is_correct ? "Верно" : "Неверно" }}</span>
          </p>
          <p><strong>Ваш ответ:</strong> {{ item.selected_options.join(", ") || "Не выбран" }}</p>
          <p><strong>Правильный ответ:</strong> {{ item.correct_options.join(", ") }}</p>
        </div>
      </template>
    </div>
  </section>
</template>
