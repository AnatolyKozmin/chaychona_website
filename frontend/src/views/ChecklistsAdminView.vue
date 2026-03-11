<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

interface ShiftType {
  id: number;
  name: string;
  is_active: boolean;
  sort_order: number;
}

interface ChecklistItem {
  id?: number;
  title: string;
  requires_photo: boolean;
  sort_order: number;
}

interface ChecklistAdmin {
  id: number;
  title: string;
  shift_type_id: number | null;
  shift_type_name: string | null;
  restaurant_id: string | null;
  restaurant_name: string | null;
  job_title_id: string | null;
  job_title_name: string | null;
  is_active: boolean;
  sort_order: number;
  items_count: number;
  created_at: string;
  items?: ChecklistItem[];
}

interface RestaurantWithRoles {
  id: string;
  name: string;
  roles: { id: string; name: string }[];
}

interface CompletionItem {
  checklist_item_id: number;
  checklist_item_title: string;
  requires_photo: boolean;
  photo_path: string | null;
  photo_url: string | null;
}

interface Completion {
  id: number;
  checklist_id: number;
  checklist_title: string;
  user_id: string;
  user_name: string;
  completed_at: string;
  items_count: number;
}

interface UserOption {
  id: string;
  full_name: string;
  email: string;
}

interface CompletionDetail extends Completion {
  shift_type_name: string | null;
  user_email: string;
  user_restaurant: string | null;
  user_job_title: string | null;
  item_completions: CompletionItem[];
}

const route = useRoute();
const auth = useAuthStore();
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const success = ref("");
const shiftTypes = ref<ShiftType[]>([]);
const checklists = ref<ChecklistAdmin[]>([]);
const restaurantsWithRoles = ref<RestaurantWithRoles[]>([]);
const editingId = ref<number | null>(null);
const adminTab = ref<"checklists" | "reports">("checklists");
const completions = ref<Completion[]>([]);
const completionsLoading = ref(false);
const completionFilter = ref("");
const completionUserFilter = ref("");
const reportUsers = ref<UserOption[]>([]);
const selectedCompletion = ref<CompletionDetail | null>(null);
const completionDetailLoading = ref(false);
const form = reactive({
  title: "",
  shift_type_id: "" as string | number,
  restaurant_id: "",
  job_title_id: "",
  is_active: true,
  sort_order: 0,
  items: [] as ChecklistItem[]
});

const availableRoles = ref<{ id: string; name: string }[]>([]);

function extractError(e: any, fallback: string): string {
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item: any) => item?.msg || JSON.stringify(item)).join(" | ");
  }
  if (typeof detail === "string" && detail.trim()) return detail;
  return fallback;
}

function updateAvailableRoles() {
  const r = restaurantsWithRoles.value.find((x) => x.id === form.restaurant_id);
  availableRoles.value = r?.roles ?? [];
  if (form.job_title_id && !availableRoles.value.some((role) => role.id === form.job_title_id)) {
    form.job_title_id = availableRoles.value[0]?.id ?? "";
  }
}

function addItem() {
  form.items.push({
    title: "",
    requires_photo: false,
    sort_order: form.items.length
  });
}

function removeItem(index: number) {
  form.items.splice(index, 1);
}

function resetForm() {
  editingId.value = null;
  form.title = "";
  form.shift_type_id = "";
  form.restaurant_id = "";
  form.job_title_id = "";
  form.is_active = true;
  form.sort_order = 0;
  form.items = [{ title: "", requires_photo: false, sort_order: 0 }];
}

async function loadShiftTypes() {
  const { data } = await api.get<ShiftType[]>("/checklists/admin/shift-types");
  shiftTypes.value = data;
}

async function loadRestaurants() {
  const { data } = await api.get<RestaurantWithRoles[]>("/users/catalog/restaurants-with-roles");
  restaurantsWithRoles.value = data;
}

async function loadChecklists() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<ChecklistAdmin[]>("/checklists/admin");
    checklists.value = data;
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить чек-листы");
  } finally {
    loading.value = false;
  }
}

async function startEdit(cl: ChecklistAdmin) {
  editingId.value = cl.id;
  const { data } = await api.get<ChecklistAdmin & { items: ChecklistItem[] }>(`/checklists/admin/${cl.id}`);
  form.title = data.title;
  form.shift_type_id = data.shift_type_id ?? "";
  form.restaurant_id = data.restaurant_id ?? "";
  form.job_title_id = data.job_title_id ?? "";
  form.is_active = data.is_active;
  form.sort_order = data.sort_order;
  form.items = (data.items ?? []).map((i) => ({
    id: i.id,
    title: i.title,
    requires_photo: i.requires_photo,
    sort_order: i.sort_order ?? 0
  }));
  if (form.items.length === 0) form.items = [{ title: "", requires_photo: false, sort_order: 0 }];
  updateAvailableRoles();
}

async function saveChecklist() {
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    const payload = {
      title: form.title.trim(),
      shift_type_id: form.shift_type_id ? Number(form.shift_type_id) : null,
      restaurant_id: form.restaurant_id || null,
      job_title_id: form.job_title_id || null,
      is_active: form.is_active,
      sort_order: form.sort_order,
      items: form.items
        .filter((i) => i.title.trim())
        .map((i, idx) => ({
          title: i.title.trim(),
          requires_photo: i.requires_photo,
          sort_order: idx
        }))
    };
    if (payload.items.length === 0) {
      error.value = "Добавьте хотя бы один пункт";
      return;
    }
    if (editingId.value) {
      await api.put(`/checklists/admin/${editingId.value}`, payload);
      success.value = "Чек-лист обновлён";
    } else {
      await api.post("/checklists/admin", payload);
      success.value = "Чек-лист создан";
    }
    await loadChecklists();
    resetForm();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось сохранить");
  } finally {
    saving.value = false;
  }
}

async function deleteChecklist(id: number) {
  if (!window.confirm("Удалить чек-лист?")) return;
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    await api.delete(`/checklists/admin/${id}`);
    success.value = "Чек-лист удалён";
    await loadChecklists();
    if (editingId.value === id) resetForm();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось удалить");
  } finally {
    saving.value = false;
  }
}

async function loadReportUsers() {
  try {
    const { data } = await api.get<UserOption[]>("/users");
    reportUsers.value = data;
  } catch {
    reportUsers.value = [];
  }
}

async function loadCompletions() {
  completionsLoading.value = true;
  error.value = "";
  try {
    const params: Record<string, string | number> = { limit: 100 };
    if (completionFilter.value) params.checklist_id = completionFilter.value;
    if (completionUserFilter.value) params.user_id = completionUserFilter.value;
    const { data } = await api.get<Completion[]>("/checklists/admin/completions", { params });
    completions.value = data;
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить отчёты");
  } finally {
    completionsLoading.value = false;
  }
}

async function openCompletionDetail(id: number) {
  completionDetailLoading.value = true;
  selectedCompletion.value = null;
  try {
    const { data } = await api.get<CompletionDetail>(`/checklists/admin/completions/${id}`);
    selectedCompletion.value = data;
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить детали");
  } finally {
    completionDetailLoading.value = false;
  }
}

function closeCompletionModal() {
  selectedCompletion.value = null;
}

function toMediaUrl(path: string | null): string | null {
  if (!path) return null;
  const base = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const origin = new URL(base).origin;
  return `${origin}/api/v1/menu/media?path=${encodeURIComponent(path)}`;
}

watch(
  () => route.query.tab,
  (tab) => {
    if (tab === "reports") {
      adminTab.value = "reports";
      loadReportUsers();
      loadCompletions();
    }
  },
  { immediate: true }
);

watch(
  () => route.query.user_id,
  (id) => {
    if (id) completionUserFilter.value = id;
  },
  { immediate: true }
);

onMounted(async () => {
  await loadShiftTypes();
  await loadRestaurants();
  await loadChecklists();
  await loadCompletions();
  updateAvailableRoles();
});
</script>

<template>
  <section class="card">
    <div class="actions-row">
      <h2 style="margin: 0">Чек-листы</h2>
      <button type="button" class="ghost" @click="loadChecklists">Обновить</button>
    </div>
    <p class="page-desc">Настройте чек-листы для открытия и закрытия смены. Укажите пункты проверки и отметьте, где нужен фотоотчёт.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="success">{{ success }}</p>

    <div class="tests-tabs">
      <button type="button" class="tests-tab" :class="{ active: adminTab === 'checklists' }" @click="adminTab = 'checklists'">
        Чек-листы
      </button>
      <button type="button" class="tests-tab" :class="{ active: adminTab === 'reports' }" @click="adminTab = 'reports'; loadCompletions()">
        Отчёты
      </button>
    </div>

    <div v-show="adminTab === 'checklists'" class="card">
      <h3 style="margin: 0">{{ editingId ? "Редактирование" : "Новый чек-лист" }}</h3>
      <form @submit.prevent="saveChecklist">
        <label>Название</label>
        <input v-model="form.title" required placeholder="Например: Закрытие смены официанта" />

        <div class="auth-grid">
          <div>
            <label>Тип смены</label>
            <select v-model="form.shift_type_id">
              <option value="">—</option>
              <option v-for="st in shiftTypes" :key="st.id" :value="st.id">{{ st.name }}</option>
            </select>
          </div>
          <div>
            <label>Ресторан</label>
            <select v-model="form.restaurant_id" @change="updateAvailableRoles">
              <option value="">Все рестораны</option>
              <option v-for="r in restaurantsWithRoles" :key="r.id" :value="r.id">{{ r.name }}</option>
            </select>
          </div>
          <div>
            <label>Роль</label>
            <select v-model="form.job_title_id">
              <option value="">Все роли</option>
              <option v-for="role in availableRoles" :key="role.id" :value="role.id">{{ role.name }}</option>
            </select>
          </div>
        </div>

        <label>
          <input type="checkbox" v-model="form.is_active" />
          Активен
        </label>

        <hr class="card-divider" />
        <div class="actions-row">
          <h4 style="margin: 0">Пункты проверки</h4>
          <button type="button" class="ghost" @click="addItem">+ Добавить</button>
        </div>
        <div v-for="(item, idx) in form.items" :key="idx" class="checklist-item-edit">
          <div class="checklist-item-row">
            <input v-model="item.title" placeholder="Что проверить" class="checklist-item-input" />
            <label class="checklist-item-photo-label">
              <input type="checkbox" v-model="item.requires_photo" />
              Фото
            </label>
            <button type="button" class="ghost" @click="removeItem(idx)">Удалить</button>
          </div>
        </div>

        <div class="actions-row" style="margin-top: 16px">
          <button type="submit" :disabled="saving">{{ editingId ? "Сохранить" : "Создать" }}</button>
          <button type="button" class="ghost" @click="resetForm">Сброс</button>
        </div>
      </form>
    </div>

    <div v-show="adminTab === 'checklists'" class="table-wrap" style="margin-top: 20px">
      <table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Тип смены</th>
            <th>Для кого</th>
            <th>Пунктов</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="cl in checklists" :key="cl.id">
            <td>{{ cl.title }}</td>
            <td>{{ cl.shift_type_name ?? "—" }}</td>
            <td>{{ cl.restaurant_name ?? "Все" }} / {{ cl.job_title_name ?? "Все" }}</td>
            <td>{{ cl.items_count }}</td>
            <td>
              <button type="button" class="ghost" @click="startEdit(cl)">Редактировать</button>
              <button type="button" @click="deleteChecklist(cl.id)">Удалить</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-show="adminTab === 'reports'">
      <div class="menu-toolbar" style="margin-bottom: 14px">
        <div class="menu-toolbar-filters">
          <div class="filter-row">
            <label class="filter-label">Чек-лист</label>
            <select v-model="completionFilter" class="filter-select" @change="loadCompletions">
              <option value="">Все</option>
              <option v-for="cl in checklists" :key="cl.id" :value="String(cl.id)">{{ cl.title }}</option>
            </select>
          </div>
          <div class="filter-row">
            <label class="filter-label">Сотрудник</label>
            <select v-model="completionUserFilter" class="filter-select" @change="loadCompletions">
              <option value="">Все</option>
              <option v-for="u in reportUsers" :key="u.id" :value="u.id">{{ u.full_name }}</option>
            </select>
          </div>
        </div>
        <button type="button" class="ghost" @click="loadCompletions">Обновить</button>
      </div>
      <p v-if="completionsLoading">Загрузка...</p>
      <p v-else-if="completions.length === 0" class="muted">Прохождений пока нет.</p>
      <div v-else class="attempt-result-list">
        <div v-for="c in completions" :key="c.id" class="test-result-card test-result-card--correct">
          <div class="actions-row" style="flex-wrap: wrap; gap: 8px">
            <div>
              <strong>{{ c.checklist_title }}</strong>
              <p class="muted" style="margin: 4px 0 0 0">{{ c.user_name }}</p>
              <p class="muted" style="margin: 2px 0 0 0; font-size: 12px">
                {{ new Date(c.completed_at).toLocaleString("ru-RU") }} · {{ c.items_count }} пунктов
              </p>
            </div>
            <button type="button" class="ghost" @click="openCompletionDetail(c.id)">Подробнее</button>
          </div>
        </div>
      </div>
    </div>
  </section>

  <Transition name="fade-scale">
    <div v-if="selectedCompletion !== null" class="modal-backdrop" @click.self="closeCompletionModal">
      <div class="modal-window modal-window-wide">
        <div class="actions-row">
          <h3 style="margin: 0">Отчёт по чек-листу</h3>
          <button type="button" class="ghost" @click="closeCompletionModal">Закрыть</button>
        </div>
        <p v-if="completionDetailLoading">Загрузка...</p>
        <template v-else>
          <div class="attempt-header-grid">
            <div class="clean-item">
              <strong>Чек-лист</strong>
              <p style="margin: 6px 0 0 0">{{ selectedCompletion.checklist_title }}</p>
              <p v-if="selectedCompletion.shift_type_name" class="muted" style="margin: 2px 0 0 0">{{ selectedCompletion.shift_type_name }}</p>
            </div>
            <div class="clean-item">
              <strong>Сотрудник</strong>
              <p style="margin: 6px 0 0 0">{{ selectedCompletion.user_name }}</p>
              <p class="muted" style="margin: 2px 0 0 0; font-size: 12px">{{ selectedCompletion.user_email }}</p>
              <p v-if="selectedCompletion.user_restaurant" class="muted" style="margin: 2px 0 0 0">{{ selectedCompletion.user_restaurant }}</p>
              <p v-if="selectedCompletion.user_job_title" class="muted" style="margin: 2px 0 0 0">{{ selectedCompletion.user_job_title }}</p>
            </div>
            <div class="clean-item">
              <strong>Дата и время</strong>
              <p style="margin: 6px 0 0 0">{{ new Date(selectedCompletion.completed_at).toLocaleString("ru-RU") }}</p>
            </div>
          </div>
          <hr class="card-divider" />
          <h4 style="margin: 0 0 12px 0">Пункты</h4>
          <div class="attempt-result-list">
            <div v-for="ic in selectedCompletion.item_completions" :key="ic.checklist_item_id" class="test-result-card test-result-card--correct">
              <p class="test-result-question">{{ ic.checklist_item_title }}</p>
              <img
                v-if="ic.photo_path"
                :src="toMediaUrl(ic.photo_path) || undefined"
                alt=""
                class="checklist-fill-preview"
                style="margin-top: 10px; max-width: 300px"
              />
            </div>
          </div>
        </template>
      </div>
    </div>
  </Transition>
</template>
