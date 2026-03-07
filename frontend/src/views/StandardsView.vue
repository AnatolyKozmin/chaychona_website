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
const activeCourseIdx = ref(0);
const activeBlockIdx = ref(0);
const adminEditingId = ref<number | null>(null);
const restaurants = ref<RestaurantWithRoles[]>([]);
const tests = ref<TestShort[]>([]);

const adminAllowed = computed(() => auth.isAdmin || auth.isSuperadmin);
const activeCourse = computed(() => courses.value[activeCourseIdx.value] ?? null);
const activeBlock = computed(() => activeCourse.value?.blocks[activeBlockIdx.value] ?? null);
const blockOffsetX = ref(0);
let dragStartX = 0;
let dragging = false;

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
    const endpoint = adminAllowed.value ? "/courses/admin" : "/courses/my";
    const { data } = await api.get<Course[]>(endpoint);
    courses.value = data;
    activeCourseIdx.value = 0;
    activeBlockIdx.value = 0;
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

function nextBlock() {
  if (!activeCourse.value) return;
  if (activeBlockIdx.value < activeCourse.value.blocks.length - 1) {
    activeBlockIdx.value += 1;
  }
}

function prevBlock() {
  if (activeBlockIdx.value > 0) {
    activeBlockIdx.value -= 1;
  }
}

function selectCourse(index: number) {
  activeCourseIdx.value = index;
  activeBlockIdx.value = 0;
  blockOffsetX.value = 0;
}

function openLinkedTest() {
  if (!activeCourse.value?.linked_test) return;
  router.push({ name: "my-tests" });
}

function onBlockPointerDown(event: PointerEvent) {
  dragging = true;
  dragStartX = event.clientX;
}

function onBlockPointerMove(event: PointerEvent) {
  if (!dragging) return;
  blockOffsetX.value = event.clientX - dragStartX;
}

function onBlockPointerUp() {
  if (!dragging) return;
  const threshold = 80;
  if (blockOffsetX.value <= -threshold) nextBlock();
  if (blockOffsetX.value >= threshold) prevBlock();
  blockOffsetX.value = 0;
  dragging = false;
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
      <p v-if="courses.length === 0" class="muted">Стандарты пока не заполнены.</p>
      <template v-else>
        <div class="clean-list">
          <button
            v-for="(course, idx) in courses"
            :key="course.id"
            type="button"
            class="ghost clean-item"
            :class="{ selected: idx === activeCourseIdx }"
            style="text-align: left"
            @click="selectCourse(idx)"
          >
            <div>{{ course.title }}</div>
            <div class="muted" style="font-size: 12px">
              {{ course.restaurant_name || "Все рестораны" }} • {{ course.job_title_name || "Все роли" }}
            </div>
          </button>
        </div>

        <div
          v-if="activeCourse && activeBlock"
          class="tinder-card"
          style="margin-top: 12px"
          :style="{ transform: `translateX(${blockOffsetX}px) rotate(${blockOffsetX / 18}deg)` }"
          @pointerdown="onBlockPointerDown"
          @pointermove="onBlockPointerMove"
          @pointerup="onBlockPointerUp"
          @pointercancel="onBlockPointerUp"
          @pointerleave="onBlockPointerUp"
        >
          <p class="muted" style="margin-top: 0">
            Блок {{ activeBlockIdx + 1 }} из {{ activeCourse.blocks.length }}
          </p>
          <h3 style="margin-top: 0">{{ activeBlock.heading || activeCourse.title }}</h3>
          <img
            v-if="activeBlock.image_path"
            :src="toMediaUrl(activeBlock.image_path) || undefined"
            alt="block image"
            style="width: 100%; border-radius: 12px; margin-bottom: 10px"
          />
          <p class="long-text">{{ activeBlock.text }}</p>
          <div
            v-for="subblock in activeBlock.subblocks"
            :key="subblock.id"
            class="clean-item"
            style="margin-top: 10px"
          >
            <h4 v-if="subblock.heading" style="margin-top: 0">{{ subblock.heading }}</h4>
            <img
              v-if="subblock.image_path"
              :src="toMediaUrl(subblock.image_path) || undefined"
              alt="subblock image"
              style="width: 100%; border-radius: 10px; margin-bottom: 8px"
            />
            <p class="long-text" style="margin-bottom: 0">{{ subblock.text }}</p>
          </div>
          <div class="actions-row" style="margin-top: 10px">
            <button type="button" class="ghost" :disabled="activeBlockIdx === 0" @click="prevBlock">Назад</button>
            <button
              type="button"
              :disabled="activeBlockIdx >= activeCourse.blocks.length - 1"
              @click="nextBlock"
            >
              Вперед
            </button>
          </div>

          <div v-if="activeBlockIdx === activeCourse.blocks.length - 1 && activeCourse.linked_test" class="card">
            <p><strong>Проверка знаний:</strong> {{ activeCourse.linked_test.title }}</p>
            <button type="button" @click="openLinkedTest">Перейти к тестам</button>
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
