<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

type QuestionType = "single" | "multiple";

interface CatalogItem {
  id: string;
  name: string;
}

interface RestaurantWithRoles {
  id: string;
  name: string;
  roles: CatalogItem[];
}

interface TestOption {
  text: string;
  is_correct: boolean;
}

interface TestQuestion {
  text: string;
  question_type: QuestionType;
  options: TestOption[];
}

interface TestPublic {
  id: number;
  external_code: string | null;
  title: string;
  description: string | null;
  restaurant_id: string;
  restaurant_name: string;
  job_title_id: string;
  job_title_name: string;
  created_at: string;
  questions: Array<{
    id: number;
    text: string;
    question_type: QuestionType;
    sort_order: number;
    options: Array<{ id: number; text: string; is_correct: boolean; sort_order: number }>;
  }>;
}

const auth = useAuthStore();
const router = useRouter();
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const success = ref("");
const restaurants = ref<RestaurantWithRoles[]>([]);
const tests = ref<TestPublic[]>([]);
const modalOpen = ref(false);
const modalTest = ref<TestPublic | null>(null);
const editMode = ref(false);
const importDryRun = ref(true);
const importFile = ref<File | null>(null);
const importReport = ref("");

const form = reactive({
  title: "",
  description: "",
  restaurant_id: "",
  job_title_id: "",
  questions: [
    {
      text: "",
      question_type: "single" as QuestionType,
      options: [
        { text: "", is_correct: true },
        { text: "", is_correct: false }
      ]
    }
  ] as TestQuestion[]
});

const selectedRestaurant = computed(() => restaurants.value.find((r) => r.id === form.restaurant_id));
const availableRoles = computed(() => selectedRestaurant.value?.roles ?? []);
const editForm = reactive({
  title: "",
  description: "",
  restaurant_id: "",
  job_title_id: "",
  questions: [] as TestQuestion[]
});
const editRestaurant = computed(() => restaurants.value.find((r) => r.id === editForm.restaurant_id));
const editAvailableRoles = computed(() => editRestaurant.value?.roles ?? []);

function goToAnalytics() {
  router.push({ name: "tests-analytics" });
}

function onRestaurantChange() {
  form.job_title_id = availableRoles.value[0]?.id ?? "";
}

function addQuestion() {
  form.questions.push({
    text: "",
    question_type: "single",
    options: [
      { text: "", is_correct: true },
      { text: "", is_correct: false }
    ]
  });
}

function removeQuestion(index: number) {
  if (form.questions.length <= 1) {
    return;
  }
  form.questions.splice(index, 1);
}

function addOption(question: TestQuestion) {
  question.options.push({ text: "", is_correct: false });
}

function removeOption(question: TestQuestion, optionIndex: number) {
  if (question.options.length <= 2) {
    return;
  }
  question.options.splice(optionIndex, 1);
}

function setCorrectSingle(question: TestQuestion, optionIndex: number) {
  question.options.forEach((opt, idx) => {
    opt.is_correct = idx === optionIndex;
  });
}

function onQuestionTypeChange(question: TestQuestion) {
  if (question.question_type === "single") {
    const firstCorrect = question.options.findIndex((opt) => opt.is_correct);
    setCorrectSingle(question, firstCorrect >= 0 ? firstCorrect : 0);
  }
}

async function loadCatalogs() {
  const { data } = await api.get<RestaurantWithRoles[]>("/users/catalog/restaurants-with-roles");
  restaurants.value = data;
  if (!form.restaurant_id && data.length > 0) {
    form.restaurant_id = data[0].id;
    form.job_title_id = data[0].roles[0]?.id ?? "";
  }
}

async function loadTests() {
  loading.value = true;
  try {
    const { data } = await api.get<TestPublic[]>("/tests", {
      params: {
        restaurant_id: form.restaurant_id || undefined,
        job_title_id: form.job_title_id || undefined
      }
    });
    tests.value = data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить тесты";
  } finally {
    loading.value = false;
  }
}

async function downloadImportTemplate() {
  try {
    const response = await api.get("/tests/import-template", { responseType: "blob" });
    const blob = new Blob([response.data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "tests_import_template.xlsx";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось скачать шаблон";
  }
}

function onImportFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  importFile.value = target.files?.[0] ?? null;
}

async function uploadImportFile() {
  if (!importFile.value) {
    error.value = "Выберите Excel файл для загрузки";
    return;
  }
  saving.value = true;
  error.value = "";
  importReport.value = "";
  try {
    const formData = new FormData();
    formData.append("file", importFile.value);
    const { data } = await api.post("/tests/import-xlsx", formData, {
      params: { dry_run: importDryRun.value }
    });
    importReport.value = `Файл обработан. Тестов в файле: ${data.tests_in_file}, создано: ${data.created}, обновлено: ${data.updated}, режим: ${data.dry_run ? "dry-run" : "apply"}.`;
    if (!importDryRun.value) {
      await loadTests();
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail;
    if (Array.isArray(detail)) {
      error.value = detail.join(" | ");
    } else if (!e?.response) {
      error.value = "Файл изменился во время загрузки. Сохраните Excel и выберите файл заново.";
    } else {
      error.value = detail ?? "Ошибка импорта файла";
    }
  } finally {
    saving.value = false;
  }
}

function cloneQuestions(
  questions: Array<{ text: string; question_type: QuestionType; options: Array<{ text: string; is_correct: boolean }> }>
): TestQuestion[] {
  return questions.map((q) => ({
    text: q.text,
    question_type: q.question_type,
    options: q.options.map((o) => ({ text: o.text, is_correct: o.is_correct }))
  }));
}

function openTestModal(test: TestPublic) {
  modalTest.value = test;
  modalOpen.value = true;
  editMode.value = false;
  editForm.title = test.title;
  editForm.description = test.description || "";
  editForm.restaurant_id = test.restaurant_id;
  editForm.job_title_id = test.job_title_id;
  editForm.questions = cloneQuestions(test.questions);
}

function closeModal() {
  modalOpen.value = false;
  modalTest.value = null;
  editMode.value = false;
}

function startEdit() {
  if (!modalTest.value) {
    return;
  }
  editMode.value = true;
}

function onEditRestaurantChange() {
  editForm.job_title_id = editAvailableRoles.value[0]?.id ?? "";
}

function addEditQuestion() {
  editForm.questions.push({
    text: "",
    question_type: "single",
    options: [
      { text: "", is_correct: true },
      { text: "", is_correct: false }
    ]
  });
}

function removeEditQuestion(index: number) {
  if (editForm.questions.length <= 1) {
    return;
  }
  editForm.questions.splice(index, 1);
}

function addEditOption(question: TestQuestion) {
  question.options.push({ text: "", is_correct: false });
}

function removeEditOption(question: TestQuestion, optionIndex: number) {
  if (question.options.length <= 2) {
    return;
  }
  question.options.splice(optionIndex, 1);
}

function setEditCorrectSingle(question: TestQuestion, optionIndex: number) {
  question.options.forEach((opt, idx) => {
    opt.is_correct = idx === optionIndex;
  });
}

function onEditQuestionTypeChange(question: TestQuestion) {
  if (question.question_type === "single") {
    const firstCorrect = question.options.findIndex((opt) => opt.is_correct);
    setEditCorrectSingle(question, firstCorrect >= 0 ? firstCorrect : 0);
  }
}

async function saveEditedTest() {
  if (!modalTest.value) {
    return;
  }
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    await api.put(`/tests/${modalTest.value.id}`, {
      title: editForm.title,
      description: editForm.description || null,
      restaurant_id: editForm.restaurant_id,
      job_title_id: editForm.job_title_id,
      questions: editForm.questions
    });
    success.value = "Тест успешно обновлен";
    await loadTests();
    const updated = tests.value.find((test) => test.id === modalTest.value?.id);
    if (updated) {
      openTestModal(updated);
    }
    editMode.value = false;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось обновить тест";
  } finally {
    saving.value = false;
  }
}

async function deleteSelectedTest() {
  if (!modalTest.value) {
    return;
  }
  const confirmed = window.confirm("Вы уверены, что хотите удалить тест?");
  if (!confirmed) {
    return;
  }
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    await api.delete(`/tests/${modalTest.value.id}`);
    success.value = "Тест удален";
    closeModal();
    await loadTests();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось удалить тест";
  } finally {
    saving.value = false;
  }
}

async function createTest() {
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    await api.post("/tests", {
      title: form.title,
      description: form.description || null,
      restaurant_id: form.restaurant_id,
      job_title_id: form.job_title_id,
      questions: form.questions
    });
    success.value = "Тест успешно создан";
    form.title = "";
    form.description = "";
    form.questions = [
      {
        text: "",
        question_type: "single",
        options: [
          { text: "", is_correct: true },
          { text: "", is_correct: false }
        ]
      }
    ];
    await loadTests();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось создать тест";
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  if (!auth.isSuperadmin) {
    return;
  }
  await loadCatalogs();
  await loadTests();
});
</script>

<template>
  <section class="card" v-if="auth.isSuperadmin">
    <div class="actions-row">
      <h2 style="margin: 0">Конструктор тестов</h2>
      <button type="button" class="ghost" @click="goToAnalytics">Аналитика прохождений</button>
    </div>
    <p class="muted">Выберите ресторан и роль, затем добавьте вопросы и варианты ответов.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="muted">{{ success }}</p>
    <p v-if="importReport" class="muted">{{ importReport }}</p>

    <div class="card">
      <h3>Импорт из Excel</h3>
      <div class="actions-row">
        <button type="button" class="ghost" @click="downloadImportTemplate">Скачать шаблон с ID</button>
      </div>
      <label>Файл Excel</label>
      <input type="file" accept=".xlsx" @change="onImportFileChange" />
      <label style="margin-top: 10px">
        <input type="checkbox" v-model="importDryRun" />
        Dry-run (только проверка, без сохранения)
      </label>
      <button type="button" @click="uploadImportFile" :disabled="saving">Загрузить шаблон</button>
    </div>

    <form class="card" @submit.prevent="createTest">
      <label>Ресторан</label>
      <select v-model="form.restaurant_id" @change="onRestaurantChange" required>
        <option value="" disabled>Выберите ресторан</option>
        <option v-for="restaurant in restaurants" :key="restaurant.id" :value="restaurant.id">
          {{ restaurant.name }}
        </option>
      </select>

      <label>Роль</label>
      <select v-model="form.job_title_id" required>
        <option value="" disabled>Выберите роль</option>
        <option v-for="role in availableRoles" :key="role.id" :value="role.id">
          {{ role.name }}
        </option>
      </select>

      <label>Название теста</label>
      <input v-model="form.title" required />
      <label>Описание теста</label>
      <input v-model="form.description" />

      <div v-for="(question, qIdx) in form.questions" :key="qIdx" class="card">
        <div class="actions-row">
          <h3>Вопрос {{ qIdx + 1 }}</h3>
          <button type="button" class="ghost" @click="removeQuestion(qIdx)">Удалить вопрос</button>
        </div>
        <label>Текст вопроса</label>
        <input v-model="question.text" required />
        <label>Тип ответа</label>
        <select v-model="question.question_type" @change="onQuestionTypeChange(question)">
          <option value="single">Один вариант</option>
          <option value="multiple">Несколько вариантов</option>
        </select>

        <div v-for="(option, oIdx) in question.options" :key="oIdx" class="actions-row">
          <input v-model="option.text" placeholder="Вариант ответа" required />
          <label style="margin: 0">
            <input
              v-if="question.question_type === 'multiple'"
              type="checkbox"
              v-model="option.is_correct"
            />
            <input
              v-else
              type="radio"
              :checked="option.is_correct"
              @change="setCorrectSingle(question, oIdx)"
            />
            Верный
          </label>
          <button type="button" class="ghost" @click="removeOption(question, oIdx)">-</button>
        </div>
        <button type="button" class="ghost" @click="addOption(question)">Добавить вариант</button>
      </div>

      <button type="button" class="ghost" @click="addQuestion">Добавить вопрос</button>
      <button type="submit" :disabled="saving">Сохранить тест</button>
    </form>

    <div class="card">
      <div class="actions-row">
        <h3>Созданные тесты</h3>
        <button type="button" class="ghost" @click="loadTests">Обновить</button>
      </div>
      <p v-if="loading">Загрузка...</p>
      <p v-else-if="tests.length === 0" class="muted">Тестов пока нет.</p>
      <div v-else class="card">
        <div>
          <button
            v-for="test in tests"
            :key="test.id"
            type="button"
            class="ghost"
            style="display: block; width: 100%; text-align: left; margin-bottom: 8px; padding: 10px 12px"
            @click="openTestModal(test)"
          >
            <div>{{ test.title }}</div>
            <div class="muted" style="font-size: 12px; margin-top: 4px">
              Ресторан: {{ test.restaurant_name }} • Для: {{ test.job_title_name }}
            </div>
            <div class="muted" style="font-size: 12px; margin-top: 2px" v-if="test.external_code">
              Код: {{ test.external_code }}
            </div>
          </button>
        </div>
      </div>
    </div>
  </section>

  <section v-else class="card">
    <h2>Конструктор тестов</h2>
    <p class="error">Доступ только для суперадмина.</p>
  </section>

  <div v-if="modalOpen && modalTest" class="modal-backdrop" @click.self="closeModal">
    <div class="card modal-card">
      <div class="actions-row">
        <h3 style="margin: 0">{{ modalTest.title }}</h3>
        <button type="button" class="ghost" @click="closeModal">Закрыть</button>
      </div>
      <p class="muted" v-if="modalTest.external_code">Код теста: {{ modalTest.external_code }}</p>
      <p class="muted">{{ modalTest.restaurant_name }} / {{ modalTest.job_title_name }}</p>

      <template v-if="!editMode">
        <p class="muted" v-if="modalTest.description">{{ modalTest.description }}</p>
        <ol>
          <li v-for="question in modalTest.questions" :key="question.id">
            {{ question.text }} <span class="muted">({{ question.question_type }})</span>
            <ul>
              <li v-for="option in question.options" :key="option.id">
                {{ option.text }} <strong v-if="option.is_correct">✓</strong>
              </li>
            </ul>
          </li>
        </ol>
        <div class="actions-row">
          <button type="button" class="ghost" @click="startEdit">Редактировать</button>
          <button type="button" @click="deleteSelectedTest" :disabled="saving">Удалить</button>
        </div>
      </template>

      <template v-else>
        <label>Название теста</label>
        <input v-model="editForm.title" required />
        <label>Описание теста</label>
        <input v-model="editForm.description" />
        <label>Ресторан</label>
        <select v-model="editForm.restaurant_id" @change="onEditRestaurantChange" required>
          <option value="" disabled>Выберите ресторан</option>
          <option v-for="restaurant in restaurants" :key="restaurant.id" :value="restaurant.id">
            {{ restaurant.name }}
          </option>
        </select>
        <label>Роль</label>
        <select v-model="editForm.job_title_id" required>
          <option value="" disabled>Выберите роль</option>
          <option v-for="role in editAvailableRoles" :key="role.id" :value="role.id">
            {{ role.name }}
          </option>
        </select>

        <div v-for="(question, qIdx) in editForm.questions" :key="qIdx" class="card">
          <div class="actions-row">
            <h4 style="margin: 0">Вопрос {{ qIdx + 1 }}</h4>
            <button type="button" class="ghost" @click="removeEditQuestion(qIdx)">Удалить</button>
          </div>
          <label>Текст вопроса</label>
          <input v-model="question.text" required />
          <label>Тип ответа</label>
          <select v-model="question.question_type" @change="onEditQuestionTypeChange(question)">
            <option value="single">Один вариант</option>
            <option value="multiple">Несколько вариантов</option>
          </select>

          <div v-for="(option, oIdx) in question.options" :key="oIdx" class="actions-row">
            <input v-model="option.text" placeholder="Вариант ответа" required />
            <label style="margin: 0">
              <input
                v-if="question.question_type === 'multiple'"
                type="checkbox"
                v-model="option.is_correct"
              />
              <input
                v-else
                type="radio"
                :checked="option.is_correct"
                @change="setEditCorrectSingle(question, oIdx)"
              />
              Верный
            </label>
            <button type="button" class="ghost" @click="removeEditOption(question, oIdx)">-</button>
          </div>
          <button type="button" class="ghost" @click="addEditOption(question)">Добавить вариант</button>
        </div>

        <div class="actions-row">
          <button type="button" class="ghost" @click="addEditQuestion">Добавить вопрос</button>
          <button type="button" class="ghost" @click="editMode = false">Отмена</button>
          <button type="button" @click="saveEditedTest" :disabled="saving">Сохранить</button>
        </div>
      </template>
    </div>
  </div>
</template>
