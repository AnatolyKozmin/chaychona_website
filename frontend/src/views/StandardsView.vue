<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

interface CourseBlock {
  id: number;
  heading: string | null;
  text: string;
  image_path: string | null;
  image_url: string | null;
  sort_order: number;
  subblocks: CourseSubBlock[];
}

interface CourseSubBlock {
  id: number;
  heading: string | null;
  text: string;
  image_path: string | null;
  image_url: string | null;
  sort_order: number;
}

interface Course {
  id: number;
  title: string;
  description: string | null;
  restaurant_id: string | null;
  restaurant_name: string | null;
  job_title_id: string | null;
  job_title_name: string | null;
  linked_test: { id: number; title: string } | null;
  is_active: boolean;
  created_at: string;
  blocks: CourseBlock[];
}

interface LearnerBlockProgress {
  block_id: number;
  title: string;
  sort_order: number;
  is_completed: boolean;
  completed_at: string | null;
  is_unlocked: boolean;
}

interface LearnerLinkedTestStats {
  test_id: number;
  test_title: string;
  attempts_count: number;
  best_score_percent: number | null;
  last_score_percent: number | null;
  last_attempt_at: string | null;
}

interface LearnerCourseOverview {
  id: number;
  title: string;
  description: string | null;
  restaurant_name: string | null;
  job_title_name: string | null;
  total_blocks: number;
  completed_blocks: number;
  progress_percent: number;
  is_completed: boolean;
  blocks: LearnerBlockProgress[];
  linked_test_stats: LearnerLinkedTestStats | null;
}

interface RestaurantWithRoles {
  id: string;
  name: string;
  roles: Array<{ id: string; name: string }>;
}

interface TestShort {
  id: number;
  title: string;
  restaurant_id: string;
  job_title_id: string;
}

const auth = useAuthStore();
const router = useRouter();
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const success = ref("");
const courses = ref<Course[]>([]);
const learnerCourses = ref<LearnerCourseOverview[]>([]);
const adminEditingId = ref<number | null>(null);
const restaurants = ref<RestaurantWithRoles[]>([]);
const tests = ref<TestShort[]>([]);

const adminAllowed = computed(() => auth.isAdmin || auth.isSuperadmin);

const form = reactive({
  title: "",
  description: "",
  restaurant_id: "",
  job_title_id: "",
  linked_test_id: "",
  is_active: true,
  blocks: [{ heading: "", text: "", image_path: "", sort_order: 0, subblocks: [] as Array<{ heading: string; text: string; image_path: string; sort_order: number }> }]
});

const availableRoles = computed(
  () => restaurants.value.find((item) => item.id === form.restaurant_id)?.roles ?? []
);

function toMediaUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const backendOrigin = new URL(baseUrl).origin;
  return `${backendOrigin}/api/v1/menu/media?path=${path}`;
}

function extractError(e: any, fallback: string): string {
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        const loc = Array.isArray(item?.loc) ? item.loc.join(".") : "";
        const msg = item?.msg || JSON.stringify(item);
        return loc ? `${loc}: ${msg}` : msg;
      })
      .join(" | ");
  }
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return fallback;
}

async function loadCourses() {
  loading.value = true;
  error.value = "";
  try {
    if (adminAllowed.value) {
      const { data } = await api.get<Course[]>("/courses/admin");
      courses.value = data;
      learnerCourses.value = [];
      return;
    }
    const { data } = await api.get<LearnerCourseOverview[]>("/courses/my-overview");
    learnerCourses.value = data;
    courses.value = [];
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить стандарты");
  } finally {
    loading.value = false;
  }
}

async function loadAdminRefs() {
  if (!adminAllowed.value) return;
  const [restaurantsRes, testsRes] = await Promise.all([
    api.get<RestaurantWithRoles[]>("/users/catalog/restaurants-with-roles"),
    api.get<TestShort[]>("/tests")
  ]);
  restaurants.value = restaurantsRes.data;
  tests.value = testsRes.data.map((item: any) => ({
    id: item.id,
    title: item.title,
    restaurant_id: item.restaurant_id,
    job_title_id: item.job_title_id
  }));
  if (!form.restaurant_id && restaurants.value.length > 0) {
    form.restaurant_id = restaurants.value[0].id;
    form.job_title_id = restaurants.value[0].roles[0]?.id ?? "";
  }
}

function resetForm() {
  adminEditingId.value = null;
  form.title = "";
  form.description = "";
  form.restaurant_id = restaurants.value[0]?.id ?? "";
  form.job_title_id = restaurants.value[0]?.roles[0]?.id ?? "";
  form.linked_test_id = "";
  form.is_active = true;
  form.blocks = [{ heading: "", text: "", image_path: "", sort_order: 0, subblocks: [] }];
}

function addBlock() {
  form.blocks.push({ heading: "", text: "", image_path: "", sort_order: form.blocks.length, subblocks: [] });
}

function removeBlock(index: number) {
  if (form.blocks.length <= 1) return;
  form.blocks.splice(index, 1);
}

async function uploadBlockImage(index: number, event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;
  saving.value = true;
  error.value = "";
  try {
    const fd = new FormData();
    fd.append("file", file);
    const { data } = await api.post<{ path: string }>("/menu/admin/media", fd);
    form.blocks[index].image_path = data.path;
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить картинку блока");
  } finally {
    saving.value = false;
    target.value = "";
  }
}

function addSubBlock(blockIndex: number) {
  form.blocks[blockIndex].subblocks.push({
    heading: "",
    text: "",
    image_path: "",
    sort_order: form.blocks[blockIndex].subblocks.length
  });
}

function removeSubBlock(blockIndex: number, subIndex: number) {
  form.blocks[blockIndex].subblocks.splice(subIndex, 1);
}

async function uploadSubBlockImage(blockIndex: number, subIndex: number, event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;
  saving.value = true;
  error.value = "";
  try {
    const fd = new FormData();
    fd.append("file", file);
    const { data } = await api.post<{ path: string }>("/menu/admin/media", fd);
    form.blocks[blockIndex].subblocks[subIndex].image_path = data.path;
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить картинку подблока");
  } finally {
    saving.value = false;
    target.value = "";
  }
}

function editCourse(course: Course) {
  adminEditingId.value = course.id;
  form.title = course.title;
  form.description = course.description || "";
  form.restaurant_id = course.restaurant_id || "";
  form.job_title_id = course.job_title_id || "";
  form.linked_test_id = course.linked_test ? String(course.linked_test.id) : "";
  form.is_active = course.is_active;
  form.blocks = course.blocks.map((block) => ({
    heading: block.heading || "",
    text: block.text,
    image_path: block.image_path || "",
    sort_order: block.sort_order,
    subblocks: block.subblocks.map((sub) => ({
      heading: sub.heading || "",
      text: sub.text,
      image_path: sub.image_path || "",
      sort_order: sub.sort_order
    }))
  }));
}

function openCourseStudy(courseId: number) {
  router.push({ name: "standards-study", params: { id: String(courseId) } });
}

async function saveCourse() {
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    const payload = {
      title: form.title,
      description: form.description || null,
      restaurant_id: form.restaurant_id || null,
      job_title_id: form.job_title_id || null,
      linked_test_id: form.linked_test_id ? Number(form.linked_test_id) : null,
      is_active: form.is_active,
      blocks: form.blocks.map((block, idx) => ({
        heading: block.heading || null,
        text: block.text,
        image_path: block.image_path || null,
        sort_order: idx,
        subblocks: block.subblocks.map((sub, subIdx) => ({
          heading: sub.heading || null,
          text: sub.text,
          image_path: sub.image_path || null,
          sort_order: subIdx
        }))
      }))
    };
    if (adminEditingId.value) {
      await api.put(`/courses/admin/${adminEditingId.value}`, payload);
      success.value = "Стандарт обновлен";
    } else {
      await api.post("/courses/admin", payload);
      success.value = "Стандарт создан";
    }
    await loadCourses();
    resetForm();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось сохранить стандарт");
  } finally {
    saving.value = false;
  }
}

async function removeCourse(courseId: number) {
  if (!window.confirm("Удалить стандарт?")) return;
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    await api.delete(`/courses/admin/${courseId}`);
    success.value = "Стандарт удален";
    await loadCourses();
    if (adminEditingId.value === courseId) resetForm();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось удалить стандарт");
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await loadCourses();
  await loadAdminRefs();
});

watch(
  () => adminAllowed.value,
  async (allowed) => {
    if (allowed) {
      await loadAdminRefs();
    }
  }
);
</script>

<template>
  <section class="card">
    <div class="actions-row">
      <h2 style="margin: 0">Стандарты</h2>
      <button type="button" class="ghost" @click="loadCourses">Обновить</button>
    </div>
    <p class="muted">Уроки с блоками: читаем по карточкам и листаем вправо/влево.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="muted">{{ success }}</p>
    <p v-if="loading">Загрузка...</p>

    <template v-if="!loading">
      <template v-if="adminAllowed">
        <p v-if="courses.length === 0" class="muted">Стандарты пока не заполнены.</p>
        <div v-else class="clean-list">
          <div v-for="course in courses" :key="course.id" class="clean-item">
            <div class="actions-row">
              <div>
                <div><strong>{{ course.title }}</strong></div>
                <div class="muted" style="font-size: 12px">
                  {{ course.restaurant_name || "Все рестораны" }} • {{ course.job_title_name || "Все роли" }}
                </div>
              </div>
              <div class="actions-row">
                <button type="button" class="ghost" @click="editCourse(course)">Редактировать</button>
                <button type="button" @click="removeCourse(course.id)">Удалить</button>
              </div>
            </div>
          </div>
        </div>
      </template>
      <template v-else>
        <p v-if="learnerCourses.length === 0" class="muted">Для вас пока нет назначенных обучений.</p>
        <div v-else class="clean-list">
          <div v-for="course in learnerCourses" :key="course.id" class="clean-item">
            <div class="actions-row">
              <div>
                <strong>{{ course.title }}</strong>
                <p class="muted" style="margin: 6px 0 0 0">
                  {{ course.restaurant_name || "Все рестораны" }} • {{ course.job_title_name || "Все роли" }}
                </p>
              </div>
              <span class="result-pill" :class="course.is_completed ? 'result-pill-success' : 'result-pill-error'">
                {{ course.is_completed ? "Изучено" : "В процессе" }}
              </span>
            </div>
            <p v-if="course.description" class="muted long-text" style="margin-top: 8px">{{ course.description }}</p>
            <div class="menu-stats-row">
              <span class="status-chip">Прогресс: {{ course.progress_percent }}%</span>
              <span class="status-chip">Блоков: {{ course.completed_blocks }}/{{ course.total_blocks }}</span>
              <span v-if="course.linked_test_stats" class="status-chip status-chip-success">
                Тест: {{ course.linked_test_stats.best_score_percent ?? 0 }}%
              </span>
            </div>
            <div class="clean-list" style="margin-top: 8px">
              <div v-for="block in course.blocks" :key="block.block_id" class="clean-item">
                <div class="actions-row">
                  <span class="long-text">{{ block.title }}</span>
                  <span class="result-pill" :class="block.is_completed ? 'result-pill-success' : 'result-pill-error'">
                    {{ block.is_completed ? "Понял" : "Не изучен" }}
                  </span>
                </div>
              </div>
            </div>
            <div class="actions-row" style="margin-top: 10px">
              <button type="button" @click="openCourseStudy(course.id)">Открыть обучение</button>
              <button
                v-if="course.linked_test_stats"
                type="button"
                class="ghost"
                @click="router.push({ name: 'my-tests', query: { test: String(course.linked_test_stats.test_id) } })"
              >
                Открыть тест
              </button>
            </div>
          </div>
        </div>
      </template>
    </template>
  </section>

  <section v-if="adminAllowed" class="card">
    <h2>Управление стандартами</h2>
    <form @submit.prevent="saveCourse">
      <label>Название</label>
      <input v-model="form.title" required />
      <label>Описание</label>
      <input v-model="form.description" />

      <div class="actions-row">
        <div style="flex: 1">
          <label>Ресторан (кому назначено)</label>
          <select v-model="form.restaurant_id">
            <option value="">Все рестораны</option>
            <option v-for="item in restaurants" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
        </div>
        <div style="flex: 1">
          <label>Роль (кому назначено)</label>
          <select v-model="form.job_title_id">
            <option value="">Все роли</option>
            <option v-for="role in availableRoles" :key="role.id" :value="role.id">{{ role.name }}</option>
          </select>
        </div>
      </div>

      <label>Тест в конце курса (опционально)</label>
      <select v-model="form.linked_test_id">
        <option value="">Без теста</option>
        <option v-for="test in tests" :key="test.id" :value="String(test.id)">{{ test.title }}</option>
      </select>
      <label>
        <input type="checkbox" v-model="form.is_active" />
        Активный стандарт
      </label>

      <div class="card">
        <div class="actions-row">
          <h3 style="margin: 0">Блоки</h3>
          <button type="button" class="ghost" @click="addBlock">Добавить блок</button>
        </div>
        <div v-for="(block, index) in form.blocks" :key="index" class="clean-item" style="margin-top: 10px">
          <div class="actions-row">
            <strong>Блок {{ index + 1 }}</strong>
            <button type="button" class="ghost" @click="removeBlock(index)">Удалить</button>
          </div>
          <label>Заголовок блока</label>
          <input v-model="block.heading" />
          <label>Текст блока</label>
          <textarea v-model="block.text" rows="5" required style="width: 100%; border: 1px solid #d0d8e5; border-radius: 10px; padding: 10px 12px;" />
          <label>Картинка блока (опционально)</label>
          <div class="actions-row">
            <input v-model="block.image_path" placeholder="uploads/..." />
            <input type="file" accept="image/*" @change="uploadBlockImage(index, $event)" />
          </div>
          <div class="card" style="margin-top: 10px">
            <div class="actions-row">
              <strong>Подблоки</strong>
              <button type="button" class="ghost" @click="addSubBlock(index)">Добавить подблок</button>
            </div>
            <div
              v-for="(subblock, subIndex) in block.subblocks"
              :key="subIndex"
              class="clean-item"
              style="margin-top: 8px"
            >
              <div class="actions-row">
                <span>Подблок {{ subIndex + 1 }}</span>
                <button type="button" class="ghost" @click="removeSubBlock(index, subIndex)">Удалить</button>
              </div>
              <label>Заголовок подблока</label>
              <input v-model="subblock.heading" />
              <label>Текст подблока</label>
              <textarea
                v-model="subblock.text"
                rows="4"
                required
                style="width: 100%; border: 1px solid #d0d8e5; border-radius: 10px; padding: 10px 12px;"
              />
              <label>Картинка подблока (опционально)</label>
              <div class="actions-row">
                <input v-model="subblock.image_path" placeholder="uploads/..." />
                <input type="file" accept="image/*" @change="uploadSubBlockImage(index, subIndex, $event)" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="actions-row" style="margin-top: 12px">
        <button type="submit" :disabled="saving">{{ adminEditingId ? "Сохранить" : "Создать" }}</button>
        <button type="button" class="ghost" @click="resetForm">Сброс</button>
      </div>
    </form>

    <div class="table-wrap" style="margin-top: 12px">
      <table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Для кого</th>
            <th>Блоков</th>
            <th>Тест</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="course in courses" :key="course.id">
            <td>{{ course.title }}</td>
            <td>{{ course.restaurant_name || "Все" }} / {{ course.job_title_name || "Все" }}</td>
            <td>{{ course.blocks.length }}</td>
            <td>{{ course.linked_test?.title || "-" }}</td>
            <td>
              <div class="actions-row">
                <button type="button" class="ghost" @click="editCourse(course)">Редактировать</button>
                <button type="button" @click="removeCourse(course.id)">Удалить</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
