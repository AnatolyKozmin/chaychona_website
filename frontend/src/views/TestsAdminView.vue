<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
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

/** Способ внесения теста: вкладки */
type CreateTab = "manual" | "word" | "excel";
const createTab = ref<CreateTab>("word");
const wordWarnings = ref<string[]>([]);
const wordDragOver = ref(false);
const excelDragOver = ref(false);
const wordFileInput = ref<HTMLInputElement | null>(null);
const excelFileInput = ref<HTMLInputElement | null>(null);

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
    testsPage.value = 1;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить тесты";
  } finally {
    loading.value = false;
  }
}

// Поиск + постраничный список тестов
const testSearch = ref("");
const testsPage = ref(1);
const TESTS_PAGE_SIZE = 10;

const filteredTests = computed(() => {
  const query = testSearch.value.trim().toLowerCase();
  if (!query) {
    return tests.value;
  }
  return tests.value.filter((test) => {
    const haystack = [
      test.title,
      test.external_code ?? "",
      ...test.assignments.map((a) => `${a.restaurant_name} ${a.job_title_name}`)
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
});

const testsTotalPages = computed(() =>
  Math.max(1, Math.ceil(filteredTests.value.length / TESTS_PAGE_SIZE))
);
const pagedTests = computed(() => {
  const start = (testsPage.value - 1) * TESTS_PAGE_SIZE;
  return filteredTests.value.slice(start, start + TESTS_PAGE_SIZE);
});
const testsRangeFrom = computed(() =>
  filteredTests.value.length === 0 ? 0 : (testsPage.value - 1) * TESTS_PAGE_SIZE + 1
);
const testsRangeTo = computed(() =>
  Math.min(testsPage.value * TESTS_PAGE_SIZE, filteredTests.value.length)
);
const testPageTabs = computed<Array<number | "gap">>(() => {
  const total = testsTotalPages.value;
  const current = testsPage.value;
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
function goTestsPage(page: number) {
  testsPage.value = Math.min(Math.max(1, page), testsTotalPages.value);
}
// Поиск сбрасывает на первую страницу
watch(testSearch, () => {
  testsPage.value = 1;
});

async function deleteTest(test: TestPublic) {
  const confirmed = window.confirm(`Удалить тест «${test.title}»? Действие необратимо.`);
  if (!confirmed) {
    return;
  }
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    await api.delete(`/tests/${test.id}`);
    success.value = `Тест «${test.title}» удалён`;
    await loadTests();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось удалить тест";
  } finally {
    saving.value = false;
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

function pickExcelFile() {
  excelFileInput.value?.click();
}

function onExcelDrop(event: DragEvent) {
  excelDragOver.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (!file) {
    return;
  }
  if (!file.name.toLowerCase().endsWith(".xlsx")) {
    error.value = "Нужен файл Excel (.xlsx)";
    return;
  }
  error.value = "";
  importFile.value = file;
}

function pickWordFile() {
  wordFileInput.value?.click();
}

function onWordDrop(event: DragEvent) {
  wordDragOver.value = false;
  const file = event.dataTransfer?.files?.[0];
  if (!file) {
    return;
  }
  if (!file.name.toLowerCase().endsWith(".docx")) {
    error.value = "Нужен файл Word (.docx)";
    return;
  }
  error.value = "";
  importWordFile.value = file;
}

/** Код теста из имени файла: транслит + snake_case, чтобы поле можно было не заполнять. */
function slugFromFilename(name: string): string {
  const translit: Record<string, string> = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z", и: "i",
    й: "i", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t",
    у: "u", ф: "f", х: "h", ц: "c", ч: "ch", ш: "sh", щ: "sch", ъ: "", ы: "y", ь: "",
    э: "e", ю: "yu", я: "ya"
  };
  const base = name.replace(/\.docx$/i, "").toLowerCase();
  const slug = base
    .split("")
    .map((ch) => translit[ch] ?? ch)
    .join("")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);
  return slug || "test";
}

/** Проблемы вопроса для подсветки в предпросмотре (та же логика, что и валидация перед сохранением). */
function questionIssues(question: TestQuestion): string[] {
  const issues: string[] = [];
  if (!question.text.trim()) {
    issues.push("нет текста вопроса");
  }
  const filled = question.options.filter((o) => o.text.trim());
  if (filled.length < 2) {
    issues.push("нужно минимум 2 варианта ответа");
  }
  const correct = question.options.filter((o) => o.is_correct && o.text.trim());
  if (correct.length < 1) {
    issues.push("не отмечен правильный ответ");
  } else if (question.question_type === "single" && correct.length !== 1) {
    issues.push("для типа «один ответ» отметьте ровно один вариант");
  }
  return issues;
}

const wordPreviewIssueCount = computed(
  () => wordPreview.questions.filter((q) => questionIssues(q).length > 0).length
);

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
    importReport.value = data.dry_run
      ? `Проверка пройдена. Тестов в файле: ${data.tests_in_file} (было бы создано: ${data.created}, обновлено: ${data.updated}). Снимите галочку проверки и загрузите ещё раз, чтобы сохранить.`
      : `Готово. Тестов в файле: ${data.tests_in_file}, создано: ${data.created}, обновлено: ${data.updated}.`;
    if (!importDryRun.value) {
      importFile.value = null;
      if (excelFileInput.value) {
        excelFileInput.value.value = "";
      }
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
  saving.value = true;
  error.value = "";
  importReport.value = "";
  try {
    const formData = new FormData();
    formData.append("file", importWordFile.value);
    const { data } = await api.post<{ questions: TestQuestion[]; warnings?: string[] }>(
      "/tests/parse-docx",
      formData
    );
    const fileName = importWordFile.value.name;
    wordPreview.title = importWordTitle.value.trim() || fileName.replace(/\.docx$/i, "").trim();
    wordPreview.external_code = importWordCode.value.trim() || slugFromFilename(fileName);
    wordPreview.description = importWordDescription.value.trim();
    wordPreview.assignments = [];
    wordPreview.questions = cloneQuestions(data.questions);
    wordWarnings.value = data.warnings ?? [];
    wordPreviewOpen.value = true;
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
    const issues = questionIssues(wordPreview.questions[i]);
    if (issues.length > 0) {
      error.value = `Вопрос ${i + 1}: ${issues.join(", ")}`;
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
      importWordFile.value = null;
      importWordCode.value = "";
      importWordTitle.value = "";
      importWordDescription.value = "";
      wordWarnings.value = [];
      if (wordFileInput.value) {
        wordFileInput.value.value = "";
      }
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
    <p class="muted page-desc">Добавьте тест удобным способом: загрузите готовый файл или создайте вручную.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="success">{{ success }}</p>
    <p v-if="importReport" class="success">{{ importReport }}</p>

    <div class="create-tabs" role="tablist">
      <button
        type="button"
        class="create-tab"
        :class="{ 'create-tab--active': createTab === 'word' }"
        @click="createTab = 'word'"
      >
        📄 Из Word
      </button>
      <button
        type="button"
        class="create-tab"
        :class="{ 'create-tab--active': createTab === 'excel' }"
        @click="createTab = 'excel'"
      >
        📊 Из Excel
      </button>
      <button
        type="button"
        class="create-tab"
        :class="{ 'create-tab--active': createTab === 'manual' }"
        @click="createTab = 'manual'"
      >
        ✏️ Вручную
      </button>
    </div>

    <div v-if="createTab === 'word'" class="test-import-card card">
      <h3>Импорт из Word (.docx)</h3>
      <p class="muted" style="margin: 0 0 14px 0">
        Вопросы с номерами «1.», «2.», варианты «A)», «B)» … Правильные ответы выделите <strong>жирным</strong> в Word.
        После разбора откроется предпросмотр: там можно всё поправить, выбрать рестораны и роли и только потом сохранить.
      </p>
      <div
        class="file-drop"
        :class="{ 'file-drop--active': wordDragOver, 'file-drop--filled': !!importWordFile }"
        @click="pickWordFile"
        @dragover.prevent="wordDragOver = true"
        @dragleave="wordDragOver = false"
        @drop.prevent="onWordDrop"
      >
        <input
          ref="wordFileInput"
          type="file"
          accept=".docx"
          @change="onImportWordFileChange"
          class="file-drop-input"
        />
        <template v-if="importWordFile">
          <span class="file-drop-icon">📄</span>
          <span class="file-drop-name">{{ importWordFile.name }}</span>
          <span class="muted">Нажмите, чтобы выбрать другой файл</span>
        </template>
        <template v-else>
          <span class="file-drop-icon">⬆️</span>
          <span class="file-drop-name">Перетащите файл .docx сюда или нажмите для выбора</span>
        </template>
      </div>
      <details class="import-optional">
        <summary class="muted">Код, название и описание (необязательно — подставятся из имени файла)</summary>
        <div class="test-form-grid" style="margin-top: 12px">
          <div class="test-form-field">
            <label>Код теста (external_code)</label>
            <input v-model="importWordCode" placeholder="например waiter_menu_01" class="test-question-input" />
          </div>
          <div class="test-form-field">
            <label>Название теста</label>
            <input v-model="importWordTitle" placeholder="Название для списка" class="test-question-input" />
          </div>
        </div>
        <div class="test-form-field" style="margin-bottom: 0">
          <label>Описание (необязательно)</label>
          <input v-model="importWordDescription" placeholder="Краткое описание" class="test-question-input" />
        </div>
      </details>
      <div class="test-form-actions" style="margin-top: 14px; border-top: none; padding-top: 0">
        <button
          type="button"
          class="test-submit-btn"
          @click="parseWordForPreview"
          :disabled="saving || wordPreviewSaving || !importWordFile"
        >
          {{ saving ? "Разбираем..." : "Разобрать и открыть предпросмотр" }}
        </button>
      </div>
    </div>

    <div v-else-if="createTab === 'excel'" class="test-import-card card">
      <h3>Импорт из Excel</h3>
      <p class="muted" style="margin: 0 0 14px 0">
        Массовое создание тестов по шаблону: одна строка — один вопрос, колонка «Код_теста» объединяет вопросы в тест.
      </p>
      <div class="test-import-row">
        <button type="button" class="ghost" @click="downloadImportTemplate">⬇️ Скачать шаблон</button>
      </div>
      <div
        class="file-drop"
        :class="{ 'file-drop--active': excelDragOver, 'file-drop--filled': !!importFile }"
        @click="pickExcelFile"
        @dragover.prevent="excelDragOver = true"
        @dragleave="excelDragOver = false"
        @drop.prevent="onExcelDrop"
      >
        <input
          ref="excelFileInput"
          type="file"
          accept=".xlsx"
          @change="onImportFileChange"
          class="file-drop-input"
        />
        <template v-if="importFile">
          <span class="file-drop-icon">📊</span>
          <span class="file-drop-name">{{ importFile.name }}</span>
          <span class="muted">Нажмите, чтобы выбрать другой файл</span>
        </template>
        <template v-else>
          <span class="file-drop-icon">⬆️</span>
          <span class="file-drop-name">Перетащите файл .xlsx сюда или нажмите для выбора</span>
        </template>
      </div>
      <label class="test-checkbox-label">
        <input type="checkbox" v-model="importDryRun" />
        Сначала только проверить, без сохранения (dry-run)
      </label>
      <button type="button" class="test-submit-btn" @click="uploadImportFile" :disabled="saving || !importFile">
        {{ saving ? "Загружаем..." : importDryRun ? "Проверить файл" : "Загрузить в базу" }}
      </button>
    </div>

    <form v-else class="test-create-form card" @submit.prevent="createTest">
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
      <div class="test-search-row">
        <input
          v-model="testSearch"
          class="test-search-input"
          type="search"
          placeholder="Поиск: название, код, ресторан или роль"
        />
        <span v-if="tests.length" class="pager-info">
          {{ testsRangeFrom }}–{{ testsRangeTo }} из {{ filteredTests.length }}
        </span>
      </div>

      <p v-if="loading">Загрузка...</p>
      <p v-else-if="tests.length === 0" class="muted">Тестов пока нет. Создайте первый тест выше.</p>
      <p v-else-if="filteredTests.length === 0" class="muted">Ничего не найдено по запросу «{{ testSearch }}».</p>
      <template v-else>
        <div v-if="testsTotalPages > 1" class="pager" style="margin-bottom: 12px">
          <button type="button" class="pager-btn" :disabled="testsPage === 1" @click="goTestsPage(testsPage - 1)">‹</button>
          <template v-for="(tab, i) in testPageTabs" :key="i">
            <span v-if="tab === 'gap'" class="pager-ellipsis">…</span>
            <button
              v-else
              type="button"
              class="pager-btn"
              :class="{ 'pager-btn--active': tab === testsPage }"
              @click="goTestsPage(tab)"
            >
              {{ tab }}
            </button>
          </template>
          <button type="button" class="pager-btn" :disabled="testsPage === testsTotalPages" @click="goTestsPage(testsPage + 1)">›</button>
        </div>

        <div class="test-list">
          <div v-for="test in pagedTests" :key="test.id" class="test-list-row">
            <button
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
            <button
              type="button"
              class="test-del-btn"
              title="Удалить тест"
              :disabled="saving"
              @click="deleteTest(test)"
            >
              Удалить
            </button>
          </div>
        </div>
      </template>
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

      <div class="preview-summary">
        <span class="role-chip">Вопросов: {{ wordPreview.questions.length }}</span>
        <span v-if="wordPreviewIssueCount > 0" class="role-chip preview-summary-issues">
          Требуют внимания: {{ wordPreviewIssueCount }}
        </span>
        <span v-else class="role-chip preview-summary-ok">Все вопросы в порядке ✓</span>
      </div>

      <div v-if="wordWarnings.length > 0" class="warning-box">
        <strong>Парсер не смог разобрать часть данных автоматически:</strong>
        <ul>
          <li v-for="(w, wIdx) in wordWarnings" :key="wIdx">{{ w }}</li>
        </ul>
        <p style="margin: 6px 0 0 0">Проблемные вопросы подсвечены ниже — поправьте их перед сохранением.</p>
      </div>

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
        <div
          v-for="(question, qIdx) in wordPreview.questions"
          :key="qIdx"
          class="test-question-card"
          :class="{ 'test-question-card--issue': questionIssues(question).length > 0 }"
        >
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
          <p v-if="questionIssues(question).length > 0" class="test-question-issue-note">
            ⚠ {{ questionIssues(question).join(" · ") }}
          </p>
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
        <button
          type="button"
          class="test-submit-btn"
          @click="applyWordImport(false)"
          :disabled="wordPreviewSaving || wordPreviewIssueCount > 0"
          :title="wordPreviewIssueCount > 0 ? 'Сначала поправьте подсвеченные вопросы' : ''"
        >
          {{ wordPreviewSaving ? "Сохраняем..." : "Сохранить в базу" }}
        </button>
      </div>
      <p v-if="wordPreviewIssueCount > 0" class="muted" style="margin: 8px 0 0 0; font-size: 13px">
        Кнопка «Сохранить в базу» станет доступна, когда все подсвеченные вопросы будут исправлены.
      </p>
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

<style scoped>
.test-search-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 4px 0 14px;
}
.test-search-input {
  flex: 1;
  min-width: 220px;
  margin: 0;
}

/* Строка списка: карточка теста + кнопка удаления в углу */
.test-list-row {
  position: relative;
}
.test-list-row .test-list-item {
  padding-right: 104px;
}
.test-del-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1;
  width: auto;
  margin: 0;
  padding: 6px 12px;
  border: 1px solid #f0c4c0;
  border-radius: 8px;
  background: #fff;
  color: #b42318;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.test-del-btn:hover:not(:disabled) {
  background: #fdecec;
  border-color: #e29b95;
}
.test-del-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

/* Постраничные язычки */
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
</style>
