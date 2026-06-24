<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";
import AssignmentPicker from "../components/AssignmentPicker.vue";
import RestaurantRolesManager from "../components/RestaurantRolesManager.vue";

type QuestionType = "single" | "multiple";

interface Assignment {
  restaurant_id: string;
  job_title_id: string;
}

interface CatalogItem {
  id: string;
  name: string;
}

interface RestaurantWithRoles {
  id: string;
  name: string;
  roles: CatalogItem[];
}

interface TestAssignment {
  restaurant_id: string;
  restaurant_name: string;
  job_title_id: string;
  job_title_name: string;
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
  assignments: TestAssignment[];
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
const importWordFile = ref<File | null>(null);
const importWordCode = ref("");
const importWordTitle = ref("");
const importWordDescription = ref("");
const catalogModalOpen = ref(false);

/** Предпросмотр импорта из Word */
const wordPreviewOpen = ref(false);
const wordPreviewSaving = ref(false);
const wordPreview = reactive({
  title: "",
  external_code: "",
  description: "",
  assignments: [] as Assignment[],
  questions: [] as TestQuestion[]
});

const form = reactive({
  title: "",
  description: "",
  assignments: [] as Assignment[],
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

const editForm = reactive({
  title: "",
  description: "",
  assignments: [] as Assignment[],
  questions: [] as TestQuestion[]
});

function goToAnalytics() {
  router.push({ name: "tests-analytics" });
}

function openCatalogModal() {
  catalogModalOpen.value = true;
}

function closeCatalogModal() {
  catalogModalOpen.value = false;
}

async function onCatalogChanged() {
  await loadCatalogs();
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
}

async function loadTests() {
  loading.value = true;
  try {
    const { data } = await api.get<TestPublic[]>("/tests");
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

function onImportWordFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  importWordFile.value = target.files?.[0] ?? null;
}

async function parseWordForPreview() {
  if (!importWordFile.value) {
    error.value = "Выберите файл Word (.docx)";
    return;
  }
  if (!importWordCode.value.trim() || !importWordTitle.value.trim()) {
    error.value = "Укажите код теста и название";
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    const formData = new FormData();
    formData.append("file", importWordFile.value);
    const { data } = await api.post<{ questions: TestQuestion[] }>("/tests/parse-docx", formData);
    wordPreview.title = importWordTitle.value.trim();
    wordPreview.external_code = importWordCode.value.trim();
    wordPreview.description = importWordDescription.value.trim();
    wordPreview.assignments = [...form.assignments];
    wordPreview.questions = cloneQuestions(data.questions);
    wordPreviewOpen.value = true;
    importReport.value = `Разобрано вопросов: ${data.questions.length}. Проверьте и при необходимости отредактируйте.`;
  } catch (e: any) {
    const detail = e?.response?.data?.detail;
    if (Array.isArray(detail)) {
      error.value = detail.join(" | ");
    } else {
      error.value = detail ?? "Не удалось разобрать Word";
    }
  } finally {
    saving.value = false;
  }
}

function closeWordPreview() {
  if (wordPreviewSaving.value) {
    return;
  }
  wordPreviewOpen.value = false;
}

function setWordPreviewCorrectSingle(question: TestQuestion, optionIndex: number) {
  question.options.forEach((opt, idx) => {
    opt.is_correct = idx === optionIndex;
  });
}

function onWordPreviewQuestionTypeChange(question: TestQuestion) {
  if (question.question_type === "single") {
    const firstCorrect = question.options.findIndex((opt) => opt.is_correct);
    setWordPreviewCorrectSingle(question, firstCorrect >= 0 ? firstCorrect : 0);
  }
}

function addWordPreviewQuestion() {
  wordPreview.questions.push({
    text: "",
    question_type: "single",
    options: [
      { text: "", is_correct: true },
      { text: "", is_correct: false }
    ]
  });
}

function removeWordPreviewQuestion(index: number) {
  if (wordPreview.questions.length <= 1) {
    return;
  }
  wordPreview.questions.splice(index, 1);
}

function addWordPreviewOption(question: TestQuestion) {
  question.options.push({ text: "", is_correct: false });
}

function removeWordPreviewOption(question: TestQuestion, optionIndex: number) {
  if (question.options.length <= 2) {
    return;
  }
  question.options.splice(optionIndex, 1);
}

async function applyWordImport(dryRun: boolean) {
  if (!wordPreview.title.trim() || !wordPreview.external_code.trim()) {
    error.value = "Укажите код и название теста";
    return;
  }
  if (wordPreview.assignments.length === 0) {
    error.value = "Отметьте хотя бы одну пару «ресторан + роль»";
    return;
  }
  if (wordPreview.questions.length < 1) {
    error.value = "Добавьте хотя бы один вопрос";
    return;
  }
  for (let i = 0; i < wordPreview.questions.length; i++) {
    const q = wordPreview.questions[i];
    if (!q.text.trim()) {
      error.value = `Пустой текст вопроса № ${i + 1}`;
      return;
    }
    const filled = q.options.filter((o) => o.text.trim());
    if (filled.length < 2) {
      error.value = `Вопрос ${i + 1}: нужно минимум 2 непустых варианта`;
      return;
    }
    const correct = q.options.filter((o) => o.is_correct && o.text.trim());
    if (correct.length < 1) {
      error.value = `Вопрос ${i + 1}: отметьте хотя бы один правильный вариант`;
      return;
    }
    if (q.question_type === "single" && correct.length !== 1) {
      error.value = `Вопрос ${i + 1}: для одного ответа отметьте ровно один вариант`;
      return;
    }
  }

  wordPreviewSaving.value = true;
  error.value = "";
  try {
    const payload = {
      external_code: wordPreview.external_code.trim(),
      title: wordPreview.title.trim(),
      description: wordPreview.description.trim() || null,
      assignments: wordPreview.assignments,
      questions: wordPreview.questions.map((q) => ({
        text: q.text.trim(),
        question_type: q.question_type,
        options: q.options
          .filter((o) => o.text.trim())
          .map((o) => ({ text: o.text.trim(), is_correct: o.is_correct }))
      }))
    };
    const { data } = await api.post("/tests/import-apply", payload, {
      params: { dry_run: dryRun }
    });
    importReport.value = dryRun
      ? `Проверка пройдена: вопросов ${data.questions_count}, тест был бы ${data.mode === "created" ? "создан" : "обновлён"}. Нажмите «Сохранить», чтобы записать в базу.`
      : `Сохранено: вопросов ${data.questions_count}, тест ${data.mode === "created" ? "создан" : "обновлён"}.`;
    if (!dryRun) {
      wordPreviewOpen.value = false;
      await loadTests();
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail;
    if (Array.isArray(detail)) {
      error.value = detail.join(" | ");
    } else if (typeof detail === "string") {
      error.value = detail;
    } else {
      error.value = "Ошибка сохранения";
    }
  } finally {
    wordPreviewSaving.value = false;
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
  editForm.assignments = test.assignments.map((a) => ({
    restaurant_id: a.restaurant_id,
    job_title_id: a.job_title_id
  }));
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
  if (editForm.assignments.length === 0) {
    error.value = "Отметьте хотя бы одну пару «ресторан + роль»";
    return;
  }
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    await api.put(`/tests/${modalTest.value.id}`, {
      title: editForm.title,
      description: editForm.description || null,
      assignments: editForm.assignments,
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
  if (form.assignments.length === 0) {
    error.value = "Отметьте хотя бы одну пару «ресторан + роль»";
    return;
  }
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    await api.post("/tests", {
      title: form.title,
      description: form.description || null,
      assignments: form.assignments,
      questions: form.questions
    });
    success.value = "Тест успешно создан";
    form.title = "";
    form.description = "";
    form.assignments = [];
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
  <section class="card tests-page" v-if="auth.isSuperadmin">
    <div class="actions-row">
      <h2 style="margin: 0">Конструктор тестов</h2>
      <div class="actions-row" style="gap: 8px">
        <button type="button" class="ghost" @click="openCatalogModal">Рестораны и роли</button>
        <button type="button" class="ghost" @click="goToAnalytics">Аналитика прохождений</button>
      </div>
    </div>
    <p class="muted page-desc">Выберите ресторан и роль, затем добавьте вопросы и варианты ответов.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="muted">{{ success }}</p>
    <p v-if="importReport" class="muted">{{ importReport }}</p>

    <hr class="card-divider" />

    <div class="test-import-card card">
      <h3>Импорт из Excel</h3>
      <p class="muted" style="margin: 0 0 14px 0">Загрузите файл по шаблону для массового создания тестов.</p>
      <div class="test-import-row">
        <button type="button" class="ghost" @click="downloadImportTemplate">Скачать шаблон</button>
        <input type="file" accept=".xlsx" @change="onImportFileChange" class="test-file-input" />
      </div>
      <label class="test-checkbox-label">
        <input type="checkbox" v-model="importDryRun" />
        Dry-run (только проверка, без сохранения)
      </label>
      <button type="button" class="test-import-btn" @click="uploadImportFile" :disabled="saving">Загрузить</button>
    </div>

    <hr class="card-divider" />

    <div class="test-import-card card">
      <h3>Импорт из Word (.docx)</h3>
      <p class="muted" style="margin: 0 0 14px 0">
        Вопросы с номерами «1.», «2.», варианты «A)», «B)» … Правильные ответы выделите <strong>жирным</strong> в Word.
        Формат описан в <code>docs/word_tests_format.md</code>.
      </p>
      <p class="muted" style="margin: 0 0 10px 0">
        Рестораны и роли вы отметите галочками в окне предпросмотра после разбора файла.
      </p>
      <div class="test-form-grid" style="margin-bottom: 12px">
        <div class="test-form-field">
          <label>Код теста (external_code)</label>
          <input v-model="importWordCode" placeholder="например waiter_menu_01" class="test-question-input" />
        </div>
        <div class="test-form-field">
          <label>Название теста</label>
          <input v-model="importWordTitle" placeholder="Название для списка" class="test-question-input" />
        </div>
      </div>
      <div class="test-form-field" style="margin-bottom: 12px">
        <label>Описание (необязательно)</label>
        <input v-model="importWordDescription" placeholder="Краткое описание" class="test-question-input" />
      </div>
      <div class="test-import-row">
        <input type="file" accept=".docx" @change="onImportWordFileChange" class="test-file-input" />
      </div>
      <div class="test-form-actions" style="margin-top: 8px; flex-wrap: wrap; gap: 10px">
        <button
          type="button"
          class="test-import-btn"
          @click="parseWordForPreview"
          :disabled="saving || wordPreviewSaving"
        >
          Разобрать и открыть предпросмотр
        </button>
      </div>
      <p class="muted" style="margin: 10px 0 0 0; font-size: 0.9em">
        После разбора откроется окно: можно править вопросы, варианты и тип (один или несколько правильных), затем
        «Проверить без сохранения» или «Сохранить в базу».
      </p>
    </div>

    <hr class="card-divider" />

    <form class="test-create-form card" @submit.prevent="createTest">
      <h3>Новый тест</h3>
      <div class="test-form-field">
        <label>Кому назначить тест</label>
        <AssignmentPicker v-model="form.assignments" :restaurants="restaurants" />
      </div>
      <div class="test-form-field">
        <label>Название теста</label>
        <input v-model="form.title" required placeholder="Например: Базовый тест официанта" />
      </div>
      <div class="test-form-field">
        <label>Описание (опционально)</label>
        <input v-model="form.description" placeholder="Краткое описание теста" />
      </div>

      <div class="test-questions-block">
        <h4>Вопросы</h4>
        <div v-for="(question, qIdx) in form.questions" :key="qIdx" class="test-question-card">
          <div class="test-question-header">
            <span class="test-question-num">Вопрос {{ qIdx + 1 }}</span>
            <button type="button" class="ghost test-question-remove" @click="removeQuestion(qIdx)">Удалить</button>
          </div>
          <div class="test-form-field">
            <label>Текст вопроса</label>
            <textarea v-model="question.text" required rows="2" placeholder="Введите текст вопроса" class="test-question-text"></textarea>
          </div>
          <div class="test-form-field test-type-select">
            <label>Тип ответа</label>
            <select v-model="question.question_type" @change="onQuestionTypeChange(question)">
              <option value="single">Один правильный вариант</option>
              <option value="multiple">Несколько правильных вариантов</option>
            </select>
          </div>

          <div class="test-options-block">
            <label>Варианты ответов</label>
            <div v-for="(option, oIdx) in question.options" :key="oIdx" class="test-option-row">
              <input
                v-if="question.question_type === 'single'"
                type="radio"
                :name="`q-${qIdx}`"
                :checked="option.is_correct"
                @change="setCorrectSingle(question, oIdx)"
                class="test-option-radio"
              />
              <input
                v-else
                type="checkbox"
                v-model="option.is_correct"
                class="test-option-checkbox"
              />
              <input v-model="option.text" placeholder="Вариант ответа" required class="test-option-input" />
              <button type="button" class="ghost test-option-remove" @click="removeOption(question, oIdx)" title="Удалить">×</button>
            </div>
            <button type="button" class="ghost test-add-option" @click="addOption(question)">+ Добавить вариант</button>
          </div>
        </div>
        <button type="button" class="ghost test-add-question" @click="addQuestion">+ Добавить вопрос</button>
      </div>

      <div class="test-form-actions">
        <button type="submit" class="test-submit-btn" :disabled="saving">Создать тест</button>
      </div>
    </form>

    <hr class="card-divider" />

    <div class="card test-list-card">
      <div class="test-list-header">
        <h3>Созданные тесты</h3>
        <button type="button" class="ghost" @click="loadTests">Обновить</button>
      </div>
      <p v-if="loading">Загрузка...</p>
      <p v-else-if="tests.length === 0" class="muted">Тестов пока нет. Создайте первый тест выше.</p>
      <div v-else class="test-list">
        <button
          v-for="test in tests"
          :key="test.id"
          type="button"
          class="test-list-item"
          @click="openTestModal(test)"
        >
          <div class="test-list-item-title">{{ test.title }}</div>
          <div class="test-list-item-meta">
            <span v-if="test.assignments.length === 0" class="muted">Без привязки</span>
            <template v-else>
              {{ test.assignments.length }} {{ test.assignments.length === 1 ? "назначение" : "назначений" }}
            </template>
            <span v-if="test.external_code" class="test-list-item-code">{{ test.external_code }}</span>
          </div>
          <div v-if="test.assignments.length > 0" class="test-list-item-assignments">
            <span v-for="a in test.assignments" :key="a.restaurant_id + a.job_title_id" class="role-chip">
              {{ a.restaurant_name }} · {{ a.job_title_name }}
            </span>
          </div>
        </button>
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
      <div class="catalog-roles" style="margin-bottom: 10px">
        <span v-for="a in modalTest.assignments" :key="a.restaurant_id + a.job_title_id" class="role-chip">
          {{ a.restaurant_name }} · {{ a.job_title_name }}
        </span>
        <span v-if="modalTest.assignments.length === 0" class="muted">Без привязки</span>
      </div>

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
        <div class="test-form-field">
          <label>Название теста</label>
          <input v-model="editForm.title" required />
        </div>
        <div class="test-form-field">
          <label>Описание теста</label>
          <input v-model="editForm.description" />
        </div>
        <div class="test-form-field">
          <label>Кому назначен тест</label>
          <AssignmentPicker v-model="editForm.assignments" :restaurants="restaurants" />
        </div>

        <div v-for="(question, qIdx) in editForm.questions" :key="qIdx" class="test-question-card">
          <div class="test-question-header">
            <span class="test-question-num">Вопрос {{ qIdx + 1 }}</span>
            <button type="button" class="ghost test-question-remove" @click="removeEditQuestion(qIdx)">Удалить</button>
          </div>
          <div class="test-form-field">
            <label>Текст вопроса</label>
            <textarea v-model="question.text" required rows="2" class="test-question-text"></textarea>
          </div>
          <div class="test-form-field test-type-select">
            <label>Тип ответа</label>
            <select v-model="question.question_type" @change="onEditQuestionTypeChange(question)">
              <option value="single">Один правильный вариант</option>
              <option value="multiple">Несколько правильных вариантов</option>
            </select>
          </div>

          <div class="test-options-block">
            <label>Варианты ответов</label>
            <div v-for="(option, oIdx) in question.options" :key="oIdx" class="test-option-row">
              <input
                v-if="question.question_type === 'single'"
                type="radio"
                :name="`edit-q-${qIdx}`"
                :checked="option.is_correct"
                @change="setEditCorrectSingle(question, oIdx)"
                class="test-option-radio"
              />
              <input
                v-else
                type="checkbox"
                v-model="option.is_correct"
                class="test-option-checkbox"
              />
              <input v-model="option.text" placeholder="Вариант ответа" required class="test-option-input" />
              <button type="button" class="ghost test-option-remove" @click="removeEditOption(question, oIdx)">×</button>
            </div>
            <button type="button" class="ghost test-add-option" @click="addEditOption(question)">+ Добавить вариант</button>
          </div>
        </div>

        <div class="test-form-actions">
          <button type="button" class="ghost" @click="addEditQuestion">+ Добавить вопрос</button>
          <button type="button" class="ghost" @click="editMode = false">Отмена</button>
          <button type="button" @click="saveEditedTest" :disabled="saving" class="test-submit-btn">Сохранить</button>
        </div>
      </template>
    </div>
  </div>

  <div v-if="wordPreviewOpen" class="modal-backdrop" @click.self="closeWordPreview">
    <div class="card modal-card word-preview-modal">
      <div class="actions-row">
        <h3 style="margin: 0">Предпросмотр: импорт из Word</h3>
        <button type="button" class="ghost" @click="closeWordPreview" :disabled="wordPreviewSaving">Закрыть</button>
      </div>
      <p class="muted" style="margin-top: 0">
        Проверьте разобранные данные. При необходимости измените код, название, ресторан, роль и сами вопросы.
      </p>

      <div class="test-form-grid">
        <div class="test-form-field">
          <label>Код теста (external_code)</label>
          <input v-model="wordPreview.external_code" class="test-question-input" />
        </div>
        <div class="test-form-field">
          <label>Название теста</label>
          <input v-model="wordPreview.title" class="test-question-input" />
        </div>
      </div>
      <div class="test-form-field" style="margin-bottom: 12px">
        <label>Описание (необязательно)</label>
        <input v-model="wordPreview.description" class="test-question-input" />
      </div>
      <div class="test-form-field" style="margin-bottom: 8px">
        <label>Кому назначить тест</label>
        <AssignmentPicker v-model="wordPreview.assignments" :restaurants="restaurants" />
      </div>

      <h4 style="margin: 12px 0 8px 0">Вопросы</h4>
      <p v-if="wordPreview.questions.length === 0" class="muted" style="margin: 0 0 10px 0">
        В файле не найдено вопросов по формату — добавьте их вручную кнопкой ниже.
      </p>
      <div class="test-questions-block">
        <div v-for="(question, qIdx) in wordPreview.questions" :key="qIdx" class="test-question-card">
          <div class="test-question-header">
            <span class="test-question-num">Вопрос {{ qIdx + 1 }}</span>
            <button
              type="button"
              class="ghost test-question-remove"
              @click="removeWordPreviewQuestion(qIdx)"
              :disabled="wordPreviewSaving"
            >
              Удалить
            </button>
          </div>
          <div class="test-form-field">
            <label>Текст вопроса</label>
            <textarea
              v-model="question.text"
              required
              rows="2"
              placeholder="Текст вопроса"
              class="test-question-text"
              :disabled="wordPreviewSaving"
            />
          </div>
          <div class="test-form-field test-type-select">
            <label>Тип ответа</label>
            <select
              v-model="question.question_type"
              @change="onWordPreviewQuestionTypeChange(question)"
              :disabled="wordPreviewSaving"
            >
              <option value="single">Один правильный вариант</option>
              <option value="multiple">Несколько правильных вариантов</option>
            </select>
          </div>

          <div class="test-options-block">
            <label>Варианты ответов</label>
            <div v-for="(option, oIdx) in question.options" :key="oIdx" class="test-option-row">
              <input
                v-if="question.question_type === 'single'"
                type="radio"
                :name="`word-preview-q-${qIdx}`"
                :checked="option.is_correct"
                :disabled="wordPreviewSaving"
                @change="setWordPreviewCorrectSingle(question, oIdx)"
                class="test-option-radio"
              />
              <input
                v-else
                type="checkbox"
                v-model="option.is_correct"
                class="test-option-checkbox"
                :disabled="wordPreviewSaving"
              />
              <input
                v-model="option.text"
                placeholder="Вариант ответа"
                required
                class="test-option-input"
                :disabled="wordPreviewSaving"
              />
              <button
                type="button"
                class="ghost test-option-remove"
                @click="removeWordPreviewOption(question, oIdx)"
                title="Удалить"
                :disabled="wordPreviewSaving"
              >
                ×
              </button>
            </div>
            <button
              type="button"
              class="ghost test-add-option"
              @click="addWordPreviewOption(question)"
              :disabled="wordPreviewSaving"
            >
              + Добавить вариант
            </button>
          </div>
        </div>
        <button
          type="button"
          class="ghost test-add-question"
          @click="addWordPreviewQuestion"
          :disabled="wordPreviewSaving"
        >
          + Добавить вопрос
        </button>
      </div>

      <div class="test-form-actions" style="margin-top: 16px; flex-wrap: wrap">
        <button type="button" class="ghost" @click="closeWordPreview" :disabled="wordPreviewSaving">Закрыть</button>
        <button type="button" class="ghost" @click="applyWordImport(true)" :disabled="wordPreviewSaving">
          Проверить без сохранения
        </button>
        <button type="button" class="test-submit-btn" @click="applyWordImport(false)" :disabled="wordPreviewSaving">
          Сохранить в базу
        </button>
      </div>
    </div>
  </div>

  <div v-if="catalogModalOpen" class="modal-backdrop" @click.self="closeCatalogModal">
    <div class="card modal-card">
      <div class="actions-row">
        <h3 style="margin: 0">Управление ресторанами и ролями</h3>
        <button type="button" class="ghost" @click="closeCatalogModal">Закрыть</button>
      </div>
      <p class="muted" style="margin-top: 0">
        Создавайте и удаляйте рестораны, добавляйте к ним роли (должности) — затем назначайте на них тесты галочками.
      </p>
      <RestaurantRolesManager @changed="onCatalogChanged" />
    </div>
  </div>
</template>
