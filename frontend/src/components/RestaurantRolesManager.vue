<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
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
  if (n % 10 === 1 && n % 100 !== 11) return "должность";
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return "должности";
  return "должностей";
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

async function createRestaurant() {
  const name = newRestaurantName.value.trim();
  if (!name) return;
  error.value = "";
  success.value = "";
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

function startEditRestaurant(restaurant: RestaurantWithRoles) {
  editingRestaurantId.value = restaurant.id;
  editRestaurantName.value = restaurant.name;
  error.value = "";
  success.value = "";
}

function cancelEditRestaurant() {
  editingRestaurantId.value = null;
  editRestaurantName.value = "";
}

async function saveRestaurantName(restaurant: RestaurantWithRoles) {
  const name = editRestaurantName.value.trim();
  if (!name) return;
  error.value = "";
  success.value = "";
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
  error.value = "";
  success.value = "";
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
  error.value = "";
  success.value = "";
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
  error.value = "";
  success.value = "";
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
    <h3 style="margin: 0 0 14px 0">Рестораны и роли</h3>
    <div class="add-catalog-row">
      <input
        v-model="newRestaurantName"
        placeholder="Название нового ресторана"
        @keyup.enter="createRestaurant"
      />
      <button type="button" @click="createRestaurant">Добавить ресторан</button>
    </div>
    <p v-if="error" class="error" style="margin-top: 8px">{{ error }}</p>
    <p v-if="success" class="success" style="margin-top: 8px">{{ success }}</p>

    <p v-if="loading" class="muted" style="margin-top: 14px">Загрузка...</p>
    <div v-else class="catalog-list" style="margin-top: 14px">
      <div v-for="r in restaurants" :key="r.id" class="catalog-item">
        <div class="catalog-item-header">
          <template v-if="editingRestaurantId === r.id">
            <input
              v-model="editRestaurantName"
              class="catalog-edit-input"
              @keyup.enter="saveRestaurantName(r)"
              @keyup.esc="cancelEditRestaurant"
            />
            <button type="button" @click="saveRestaurantName(r)">Сохранить</button>
            <button type="button" class="ghost" @click="cancelEditRestaurant">Отмена</button>
          </template>
          <template v-else>
            <span class="catalog-item-name">{{ r.name }}</span>
            <span class="muted catalog-item-meta">{{ r.roles.length }} {{ pluralRoles(r.roles.length) }}</span>
            <button type="button" class="ghost" @click="startEditRestaurant(r)">Изменить</button>
            <button type="button" class="ghost danger" @click="deleteRestaurant(r)">Удалить</button>
          </template>
        </div>
        <div class="catalog-roles">
          <span v-for="role in r.roles" :key="role.id" class="role-chip">
            {{ role.name }}
            <button
              type="button"
              class="role-chip-remove"
              title="Удалить роль"
              @click="deleteRole(r, role)"
            >×</button>
          </span>
          <span v-if="r.roles.length === 0" class="muted">Должностей нет</span>
        </div>
        <div class="add-catalog-row">
          <input
            v-model="newRoleNameByRestaurant[r.id]"
            placeholder="Новая роль (должность)"
            @keyup.enter="addRole(r)"
          />
          <button type="button" @click="addRole(r)">Добавить роль</button>
        </div>
      </div>
      <p v-if="restaurants.length === 0" class="muted">Рестораны не добавлены.</p>
    </div>
  </div>
</template>

<style scoped>
.role-chip {
  gap: 6px;
}
.role-chip-remove {
  border: none;
  background: transparent;
  color: #2a4a8a;
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  padding: 0;
  margin-left: 2px;
}
.role-chip-remove:hover {
  color: #c0392b;
}
.ghost.danger {
  color: #c0392b;
}
</style>
