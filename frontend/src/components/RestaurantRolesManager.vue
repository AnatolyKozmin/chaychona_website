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
  border: 1px solid #cdd8ec;
  border-radius: 8px;
  font-size: 14px;
  color: #1e293b;
  background: #fff;
  margin: 0;
}
.rrm-input:focus {
  outline: none;
  border-color: #2a4a8a;
  box-shadow: 0 0 0 3px rgba(42, 74, 138, 0.15);
}
.rrm-input-lg {
  font-size: 18px;
  font-weight: 600;
  padding: 12px 14px;
}

/* Кнопки */
.rrm-btn {
  border-radius: 8px;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  border: 1px solid transparent;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.rrm-btn-primary {
  background: #2a4a8a;
  color: #fff;
}
.rrm-btn-primary:hover {
  background: #213c72;
}
.rrm-btn-secondary {
  background: #e7edf9;
  color: #2a4a8a;
}
.rrm-btn-secondary:hover {
  background: #d7e1f4;
}
.rrm-btn-ghost {
  background: #fff;
  border-color: #cdd8ec;
  color: #2a4a8a;
}
.rrm-btn-ghost:hover {
  background: #f3f6fc;
}
.rrm-btn-danger {
  background: #fff;
  border-color: #f0c4c0;
  color: #c0392b;
}
.rrm-btn-danger:hover {
  background: #fceceb;
}

/* Блок добавления ресторана */
.rrm-add-card {
  border: 1px solid #e5ebf6;
  border-radius: 12px;
  padding: 14px 16px;
  background: #f8faff;
}
.rrm-add-label,
.rrm-edit-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
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
  border-radius: 8px;
  font-size: 14px;
}
.rrm-msg-error {
  background: #fceceb;
  color: #c0392b;
}
.rrm-msg-success {
  background: #e6f6ec;
  color: #1f8a4c;
}
.rrm-muted {
  color: #64748b;
  font-size: 14px;
  margin: 0;
}

/* Список ресторанов */
.rrm-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.rrm-card {
  border: 1px solid #e5ebf6;
  border-radius: 12px;
  padding: 16px;
  background: #fff;
}
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
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  word-break: break-word;
}
.rrm-count {
  font-size: 13px;
  color: #94a3b8;
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
  border-top: 1px dashed #e5ebf6;
}
.rrm-roles-label {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
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
  padding: 5px 6px 5px 12px;
  border-radius: 999px;
  background: #e7edf9;
  color: #2a4a8a;
  font-size: 14px;
}
.rrm-chip-x {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #2a4a8a;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}
.rrm-chip-x:hover {
  background: #c0392b;
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
