<script setup lang="ts">
import { nextTick, onMounted, reactive, ref } from "vue";
import { api } from "../api/client";

interface CatalogItem {
  id: string;
  name: string;
}

interface RestaurantWithRoles {
  id: string;
  name: string;
  roles: CatalogItem[];
}

const emit = defineEmits<{ (e: "changed"): void }>();

const restaurants = ref<RestaurantWithRoles[]>([]);
const loading = ref(false);
const error = ref("");
const success = ref("");

const newRestaurantName = ref("");
const editingRestaurantId = ref<string | null>(null);
const editRestaurantName = ref("");
const editInput = ref<HTMLInputElement | null>(null);
const newRoleNameByRestaurant = reactive<Record<string, string>>({});

function extractError(e: any, fallback: string): string {
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item: any) => item?.msg || JSON.stringify(item)).join(" | ");
  }
  if (typeof detail === "string" && detail.trim()) return detail;
  return fallback;
}

function pluralRoles(n: number): string {
  if (n % 10 === 1 && n % 100 !== 11) return "роль";
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return "роли";
  return "ролей";
}

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get<RestaurantWithRoles[]>("/users/catalog/restaurants-with-roles");
    restaurants.value = data;
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить рестораны");
  } finally {
    loading.value = false;
  }
}

function notifyChanged() {
  emit("changed");
}

function clearMessages() {
  error.value = "";
  success.value = "";
}

async function createRestaurant() {
  const name = newRestaurantName.value.trim();
  if (!name) return;
  clearMessages();
  try {
    await api.post("/users/catalog/restaurants", { name });
    newRestaurantName.value = "";
    success.value = `Ресторан «${name}» добавлен`;
    await load();
    notifyChanged();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось создать ресторан");
  }
}

function setEditInput(el: Element | null, restaurantId: string) {
  // ref внутри v-for: сохраняем элемент только для редактируемого ресторана.
  if (el && editingRestaurantId.value === restaurantId) {
    editInput.value = el as HTMLInputElement;
  }
}

async function startEditRestaurant(restaurant: RestaurantWithRoles) {
  editingRestaurantId.value = restaurant.id;
  editRestaurantName.value = restaurant.name;
  clearMessages();
  await nextTick();
  editInput.value?.focus();
  editInput.value?.select();
}

function cancelEditRestaurant() {
  editingRestaurantId.value = null;
  editRestaurantName.value = "";
}

async function saveRestaurantName(restaurant: RestaurantWithRoles) {
  const name = editRestaurantName.value.trim();
  if (!name) {
    error.value = "Название не может быть пустым";
    return;
  }
  if (name === restaurant.name) {
    cancelEditRestaurant();
    return;
  }
  clearMessages();
  try {
    await api.put(`/users/catalog/restaurants/${restaurant.id}`, { name });
    success.value = `Ресторан переименован в «${name}»`;
    editingRestaurantId.value = null;
    await load();
    notifyChanged();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось переименовать ресторан");
  }
}

async function deleteRestaurant(restaurant: RestaurantWithRoles) {
  if (!window.confirm(`Удалить ресторан «${restaurant.name}» вместе со всеми его ролями?`)) return;
  clearMessages();
  try {
    await api.delete(`/users/catalog/restaurants/${restaurant.id}`);
    success.value = `Ресторан «${restaurant.name}» удалён`;
    await load();
    notifyChanged();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось удалить ресторан");
  }
}

async function addRole(restaurant: RestaurantWithRoles) {
  const name = (newRoleNameByRestaurant[restaurant.id] ?? "").trim();
  if (!name) return;
  clearMessages();
  try {
    await api.post("/users/catalog/job-titles", { name, restaurant_id: restaurant.id });
    newRoleNameByRestaurant[restaurant.id] = "";
    success.value = `Роль «${name}» добавлена в «${restaurant.name}»`;
    await load();
    notifyChanged();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось добавить роль");
  }
}

async function renameRole(restaurant: RestaurantWithRoles, role: CatalogItem) {
  const name = (window.prompt(`Новое название роли «${role.name}»:`, role.name) ?? "").trim();
  if (!name || name === role.name) return;
  clearMessages();
  try {
    await api.put(`/users/catalog/job-titles/${role.id}`, { name });
    success.value = `Роль «${role.name}» переименована в «${name}» — у сотрудников должность обновлена автоматически`;
    await load();
    notifyChanged();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось переименовать роль");
  }
}

async function deleteRole(restaurant: RestaurantWithRoles, role: CatalogItem) {
  if (!window.confirm(`Удалить роль «${role.name}» из «${restaurant.name}»?`)) return;
  clearMessages();
  try {
    await api.delete(`/users/catalog/job-titles/${role.id}`);
    success.value = `Роль «${role.name}» удалена`;
    await load();
    notifyChanged();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось удалить роль");
  }
}

onMounted(load);
defineExpose({ reload: load });
</script>

<template>
  <div class="rrm">
    <!-- Добавить ресторан -->
    <div class="rrm-add-card">
      <label class="rrm-add-label">Новый ресторан</label>
      <div class="rrm-add-row">
        <input
          v-model="newRestaurantName"
          class="rrm-input"
          placeholder="Например: Чайхона на Тверской"
          @keyup.enter="createRestaurant"
        />
        <button type="button" class="rrm-btn rrm-btn-primary" @click="createRestaurant">Добавить</button>
      </div>
    </div>

    <p v-if="error" class="rrm-msg rrm-msg-error">{{ error }}</p>
    <p v-if="success" class="rrm-msg rrm-msg-success">{{ success }}</p>

    <p v-if="loading" class="rrm-muted">Загрузка...</p>
    <p v-else-if="restaurants.length === 0" class="rrm-muted">
      Пока нет ни одного ресторана. Добавьте первый выше.
    </p>

    <div v-else class="rrm-list">
      <div v-for="r in restaurants" :key="r.id" class="rrm-card">
        <!-- Заголовок / переименование -->
        <div v-if="editingRestaurantId === r.id" class="rrm-edit">
          <label class="rrm-edit-label">Новое название ресторана</label>
          <input
            :ref="(el) => setEditInput(el as Element | null, r.id)"
            v-model="editRestaurantName"
            class="rrm-input rrm-input-lg"
            @keyup.enter="saveRestaurantName(r)"
            @keyup.esc="cancelEditRestaurant"
          />
          <div class="rrm-edit-actions">
            <button type="button" class="rrm-btn rrm-btn-primary" @click="saveRestaurantName(r)">Сохранить</button>
            <button type="button" class="rrm-btn rrm-btn-ghost" @click="cancelEditRestaurant">Отмена</button>
          </div>
        </div>
        <div v-else class="rrm-card-head">
          <div class="rrm-title-wrap">
            <span class="rrm-title">{{ r.name }}</span>
            <span class="rrm-count">{{ r.roles.length }} {{ pluralRoles(r.roles.length) }}</span>
          </div>
          <div class="rrm-actions">
            <button type="button" class="rrm-btn rrm-btn-ghost" @click="startEditRestaurant(r)">
              Переименовать
            </button>
            <button type="button" class="rrm-btn rrm-btn-danger" @click="deleteRestaurant(r)">Удалить</button>
          </div>
        </div>

        <!-- Роли -->
        <div class="rrm-roles">
          <div class="rrm-roles-label">Роли (должности)</div>
          <div class="rrm-chips">
            <span v-for="role in r.roles" :key="role.id" class="rrm-chip">
              <span class="rrm-chip-name">{{ role.name }}</span>
              <button
                type="button"
                class="rrm-chip-x"
                title="Переименовать роль"
                @click="renameRole(r, role)"
              >✎</button>
              <button
                type="button"
                class="rrm-chip-x"
                title="Удалить роль"
                @click="deleteRole(r, role)"
              >×</button>
            </span>
            <span v-if="r.roles.length === 0" class="rrm-muted">Пока нет ролей</span>
          </div>
          <div class="rrm-add-role">
            <input
              v-model="newRoleNameByRestaurant[r.id]"
              class="rrm-input"
              placeholder="Например: Официант, Бармен, Повар…"
              @keyup.enter="addRole(r)"
            />
            <button type="button" class="rrm-btn rrm-btn-secondary" @click="addRole(r)">+ Роль</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rrm {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Поля ввода */
.rrm-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--line-hard);
  border-radius: var(--r);
  font-size: 0.92rem;
  color: var(--ink);
  background: var(--surface);
  margin: 0;
}
.rrm-input:focus {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
  border-color: var(--accent);
}
.rrm-input-lg {
  font-size: 1.05rem;
  font-weight: 600;
  padding: 12px 14px;
}

/* Кнопки */
.rrm-btn {
  border-radius: var(--r);
  padding: 10px 16px;
  font-size: 0.9rem;
  font-weight: 550;
  cursor: pointer;
  white-space: nowrap;
  border: 1px solid transparent;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}
.rrm-btn-primary {
  background: var(--ink);
  color: var(--surface);
  border-color: var(--ink);
}
.rrm-btn-primary:hover {
  background: var(--n800);
  border-color: var(--n800);
}
.rrm-btn-secondary {
  background: var(--n100);
  color: var(--ink);
  border-color: var(--line-hard);
}
.rrm-btn-secondary:hover {
  background: var(--n150);
}
.rrm-btn-ghost {
  background: var(--surface);
  border-color: var(--line-hard);
  color: var(--ink);
}
.rrm-btn-ghost:hover {
  background: var(--n100);
}
.rrm-btn-danger {
  background: var(--surface);
  border-color: var(--bad-line);
  color: var(--bad);
}
.rrm-btn-danger:hover {
  background: var(--bad-bg);
}

/* Блок добавления ресторана */
.rrm-add-card {
  border: 1px solid var(--line);
  border-radius: var(--r);
  padding: 14px 16px;
  background: var(--surface-2);
}
.rrm-add-label,
.rrm-edit-label {
  display: block;
  font-family: var(--mono);
  font-size: 0.72rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin-bottom: 6px;
}
.rrm-add-row {
  display: flex;
  gap: 10px;
}

/* Сообщения */
.rrm-msg {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--r);
  font-size: 0.9rem;
  border: 1px solid;
}
.rrm-msg-error {
  background: var(--bad-bg);
  color: var(--bad);
  border-color: var(--bad-line);
}
.rrm-msg-success {
  background: var(--good-bg);
  color: var(--good);
  border-color: var(--good-line);
}
.rrm-muted {
  color: var(--muted);
  font-size: 0.9rem;
  margin: 0;
}

/* Список ресторанов */
.rrm-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid var(--line);
}
.rrm-card {
  border: 0;
  border-bottom: 1px solid var(--line-soft);
  border-radius: 0;
  padding: 16px;
  background: var(--surface);
}
.rrm-card:last-child { border-bottom: 0; }
.rrm-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.rrm-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}
.rrm-title {
  font-size: 1.05rem;
  font-weight: 620;
  color: var(--ink);
  letter-spacing: -0.01em;
  word-break: break-word;
}
.rrm-count {
  font-family: var(--mono);
  font-size: 0.75rem;
  color: var(--muted);
  white-space: nowrap;
}
.rrm-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* Режим переименования */
.rrm-edit {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.rrm-edit-actions {
  display: flex;
  gap: 8px;
}

/* Роли */
.rrm-roles {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--line-soft);
}
.rrm-roles-label {
  font-family: var(--mono);
  font-size: 0.72rem;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
  margin-bottom: 8px;
}
.rrm-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.rrm-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px 4px 10px;
  border-radius: var(--r);
  background: var(--n100);
  color: var(--ink-2);
  border: 1px solid var(--line);
  font-size: 0.85rem;
}
.rrm-chip-x {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: var(--r);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  margin: 0;
  padding: 0;
}
.rrm-chip-x:hover {
  background: var(--bad);
  color: #fff;
}
.rrm-add-role {
  display: flex;
  gap: 10px;
}

@media (max-width: 600px) {
  .rrm-add-row,
  .rrm-add-role {
    flex-direction: column;
  }
  .rrm-card-head {
    align-items: flex-start;
  }
}
</style>
