<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

type UserRole = "superadmin" | "admin" | "learner";

interface UserRecord {
  id: string;
  email: string;
  full_name: string;
  restaurant: string | null;
  role: UserRole;
  job_title: string | null;
  is_active: boolean;
  created_at: string;
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

interface RegistrationRequest {
  id: string;
  first_name: string;
  last_name: string;
  restaurant: string;
  desired_job_title: string | null;
  desired_login: string;
  status: "pending" | "approved" | "rejected";
  rejection_reason: string | null;
  created_at: string;
  processed_at: string | null;
}

const auth = useAuthStore();
const users = ref<UserRecord[]>([]);
const restaurantsWithRoles = ref<RestaurantWithRoles[]>([]);
const loading = ref(false);
const error = ref("");
const requests = ref<RegistrationRequest[]>([]);
const learnerEdits = reactive<Record<string, { restaurant: string; job_title: string }>>({});

function extractError(e: any, fallback: string): string {
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item: any) => item?.msg || JSON.stringify(item)).join(" | ");
  }
  if (typeof detail === "string" && detail.trim()) return detail;
  return fallback;
}

function getRolesForRestaurant(restaurantName: string): CatalogItem[] {
  const selected = restaurantsWithRoles.value.find((item) => item.name === restaurantName);
  return selected?.roles ?? [];
}

async function loadCatalogs() {
  const { data } = await api.get<RestaurantWithRoles[]>("/users/catalog/restaurants-with-roles");
  restaurantsWithRoles.value = data;
}

async function loadUsers() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<UserRecord[]>("/users");
    users.value = data;
    for (const user of data) {
      learnerEdits[user.id] = {
        restaurant: user.restaurant ?? "",
        job_title: user.job_title ?? ""
      };
    }
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить пользователей");
  } finally {
    loading.value = false;
  }
}

async function updateRole(user: UserRecord, role: UserRole) {
  await api.patch(`/users/${user.id}/role`, { role });
  await loadUsers();
}

async function updateJobTitle(user: UserRecord, jobTitle: string) {
  await api.patch(`/users/${user.id}/job-title`, { job_title: jobTitle || null });
  await loadUsers();
}

async function saveLearnerProfile(user: UserRecord) {
  const edit = learnerEdits[user.id];
  if (!edit) return;
  await api.patch(`/users/${user.id}/learner-profile`, {
    restaurant: edit.restaurant,
    job_title: edit.job_title
  });
  await loadUsers();
}

async function loadRequests() {
  if (!auth.isSuperadmin) {
    requests.value = [];
    return;
  }
  try {
    const { data } = await api.get<RegistrationRequest[]>("/users/registration-requests");
    requests.value = data;
  } catch {
    requests.value = [];
  }
}

async function approveRequest(requestId: string) {
  await api.post(`/users/registration-requests/${requestId}/approve`);
  await Promise.all([loadUsers(), loadRequests()]);
}

async function rejectRequest(requestId: string) {
  await api.post(`/users/registration-requests/${requestId}/reject`);
  await loadRequests();
}

onMounted(async () => {
  await loadCatalogs();
  await loadUsers();
  await loadRequests();
});
</script>

<template>
  <section class="card">
    <h2>Доступы</h2>
    <p class="page-desc">Управление ролями, ресторанами и должностями пользователей.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>
    <div v-else class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Имя</th>
            <th>Ресторан</th>
            <th>Логин</th>
            <th>Роль</th>
            <th>Должность</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.full_name }}</td>
            <td>{{ user.restaurant || "-" }}</td>
            <td>{{ user.email }}</td>
            <td>
              <select
                :value="user.role"
                :disabled="!auth.isSuperadmin || user.id === auth.user?.id"
                @change="updateRole(user, ($event.target as HTMLSelectElement).value as UserRole)"
              >
                <option value="superadmin">Суперадмин</option>
                <option value="admin">Админ</option>
                <option value="learner">Обучающийся</option>
              </select>
            </td>
            <td>
              <div v-if="user.role === 'learner'" class="actions-row" style="flex-wrap: wrap; gap: 8px">
                <select v-model="learnerEdits[user.id].restaurant">
                  <option value="" disabled>Ресторан</option>
                  <option v-for="r in restaurantsWithRoles" :key="r.id" :value="r.name">{{ r.name }}</option>
                </select>
                <select v-model="learnerEdits[user.id].job_title">
                  <option value="" disabled>Должность</option>
                  <option
                    v-for="role in getRolesForRestaurant(learnerEdits[user.id].restaurant)"
                    :key="role.id"
                    :value="role.name"
                  >
                    {{ role.name }}
                  </option>
                </select>
                <button type="button" @click="saveLearnerProfile(user)">Сохранить</button>
              </div>
              <span v-else>—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="auth.isSuperadmin" class="card" style="margin-top: 24px">
      <div class="actions-row">
        <h3 style="margin: 0">Заявки на доступ</h3>
        <button type="button" class="ghost" @click="loadRequests">Обновить</button>
      </div>
      <p class="muted" style="margin: 8px 0 0 0">Пользователи, которые хотят получить доступ к системе. Одобрите или отклоните заявку.</p>
      <div class="table-wrap" style="margin-top: 14px">
        <table>
          <thead>
            <tr>
              <th>Имя</th>
              <th>Фамилия</th>
              <th>Ресторан</th>
              <th>Роль</th>
              <th>Желаемый логин</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="req in requests" :key="req.id">
              <td>{{ req.first_name }}</td>
              <td>{{ req.last_name }}</td>
              <td>{{ req.restaurant }}</td>
              <td>{{ req.desired_job_title || "-" }}</td>
              <td>{{ req.desired_login }}</td>
              <td>
                {{
                  req.status === "pending"
                    ? "Ожидает"
                    : req.status === "approved"
                      ? "Одобрена"
                      : "Отклонена"
                }}
              </td>
              <td>
                <div v-if="req.status === 'pending'" class="actions-row">
                  <button type="button" @click="approveRequest(req.id)">Разрешить</button>
                  <button type="button" class="ghost" @click="rejectRequest(req.id)">Отклонить</button>
                </div>
                <span v-else>—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="requests.length === 0" class="muted" style="margin-top: 10px">Заявок пока нет.</p>
    </div>
  </section>
</template>
