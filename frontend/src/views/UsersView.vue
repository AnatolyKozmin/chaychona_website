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

interface CatalogItem {
  id: string;
  name: string;
}

interface RestaurantWithRoles {
  id: string;
  name: string;
  roles: CatalogItem[];
}

const auth = useAuthStore();
const users = ref<UserRecord[]>([]);
const requests = ref<RegistrationRequest[]>([]);
const restaurants = ref<CatalogItem[]>([]);
const restaurantsWithRoles = ref<RestaurantWithRoles[]>([]);
const loading = ref(false);
const error = ref("");
const restaurantName = ref("");
const jobTitleName = ref("");
const selectedRestaurantId = ref("");
const learnerEdits = reactive<Record<string, { restaurant: string; job_title: string }>>({});
const createForm = reactive({
  first_name: "",
  last_name: "",
  restaurant: "",
  login: "",
  password: "",
  role: "learner" as UserRole,
  job_title: ""
});

function getRolesForRestaurant(restaurantName: string): CatalogItem[] {
  const selected = restaurantsWithRoles.value.find((item) => item.name === restaurantName);
  return selected?.roles ?? [];
}

function onCreateRestaurantChange() {
  const roles = getRolesForRestaurant(createForm.restaurant);
  createForm.job_title = roles.length > 0 ? roles[0].name : "";
}

function onCreateAccessRoleChange() {
  if (createForm.role !== "learner") {
    createForm.restaurant = "";
    createForm.job_title = "";
    return;
  }
  onCreateRestaurantChange();
}

async function loadCatalogs() {
  const [restaurantRes, mapRes] = await Promise.all([
    api.get<CatalogItem[]>("/users/catalog/restaurants"),
    api.get<RestaurantWithRoles[]>("/users/catalog/restaurants-with-roles")
  ]);
  restaurants.value = restaurantRes.data;
  restaurantsWithRoles.value = mapRes.data;

  if (!selectedRestaurantId.value && restaurants.value.length > 0) {
    selectedRestaurantId.value = restaurants.value[0].id;
  }
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
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить пользователей";
  } finally {
    loading.value = false;
  }
}

async function loadRequests() {
  if (!auth.isSuperadmin) {
    requests.value = [];
    return;
  }
  const { data } = await api.get<RegistrationRequest[]>("/users/registration-requests");
  requests.value = data;
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
  if (!edit) {
    return;
  }
  await api.patch(`/users/${user.id}/learner-profile`, {
    restaurant: edit.restaurant,
    job_title: edit.job_title
  });
  await loadUsers();
}

async function createUser() {
  await api.post("/users", {
    ...createForm,
    restaurant: createForm.restaurant || null,
    job_title: createForm.role === "learner" ? createForm.job_title || null : null
  });
  createForm.first_name = "";
  createForm.last_name = "";
  createForm.restaurant = "";
  createForm.login = "";
  createForm.password = "";
  createForm.role = "learner";
  createForm.job_title = "";
  await loadUsers();
}

async function addRestaurant() {
  if (!restaurantName.value.trim()) {
    return;
  }
  await api.post("/users/catalog/restaurants", { name: restaurantName.value });
  restaurantName.value = "";
  await loadCatalogs();
}

async function addJobTitle() {
  if (!jobTitleName.value.trim() || !selectedRestaurantId.value) {
    return;
  }
  await api.post("/users/catalog/job-titles", {
    name: jobTitleName.value,
    restaurant_id: selectedRestaurantId.value
  });
  jobTitleName.value = "";
  await loadCatalogs();
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
  await Promise.all([loadUsers(), loadRequests(), loadCatalogs()]);
});
</script>

<template>
  <section class="card">
    <h2>Пользователи</h2>
    <p class="muted">Страница доступна только администратору и суперадмину.</p>
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
                <option value="superadmin">superadmin</option>
                <option value="admin">admin</option>
                <option value="learner">learner</option>
              </select>
            </td>
            <td>
              <div v-if="user.role === 'learner'" class="actions-row">
                <select v-model="learnerEdits[user.id].restaurant">
                  <option value="" disabled>Ресторан</option>
                  <option v-for="restaurant in restaurants" :key="restaurant.id" :value="restaurant.name">
                    {{ restaurant.name }}
                  </option>
                </select>
                <select v-model="learnerEdits[user.id].job_title">
                  <option value="" disabled>Роль</option>
                  <option
                    v-for="jobTitle in getRolesForRestaurant(learnerEdits[user.id].restaurant)"
                    :key="jobTitle.id"
                    :value="jobTitle.name"
                  >
                    {{ jobTitle.name }}
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

    <form v-if="auth.isSuperadmin" class="card create-user-form" @submit.prevent="createUser">
      <h3>Create user</h3>
      <label>Имя</label>
      <input v-model="createForm.first_name" required />
      <label>Фамилия</label>
      <input v-model="createForm.last_name" required />
      <label>Ресторан</label>
      <select v-model="createForm.restaurant" @change="onCreateRestaurantChange" :disabled="createForm.role !== 'learner'">
        <option value="" disabled>Выберите ресторан</option>
        <option v-for="restaurant in restaurants" :key="restaurant.id" :value="restaurant.name">
          {{ restaurant.name }}
        </option>
      </select>
      <label>Логин</label>
      <input v-model="createForm.login" required />
      <label>Пароль</label>
      <input v-model="createForm.password" type="password" required />
      <label>Роль</label>
      <select v-model="createForm.role" @change="onCreateAccessRoleChange">
        <option value="superadmin">суперадмин</option>
        <option value="admin">админ</option>
        <option value="learner">обучающийся</option>
      </select>
      <label>Должность (если learner)</label>
      <select v-model="createForm.job_title" :disabled="createForm.role !== 'learner'">
        <option value="" disabled>Выберите роль</option>
        <option v-for="jobTitle in getRolesForRestaurant(createForm.restaurant)" :key="jobTitle.id" :value="jobTitle.name">
          {{ jobTitle.name }}
        </option>
      </select>
      <button type="submit">Создать пользователя</button>
    </form>

    <div v-if="auth.isSuperadmin" class="card">
      <h3>Справочники</h3>
      <p class="muted">Добавляйте рестораны и роли в ресторане (должности), чтобы использовать их в формах.</p>
      <div class="auth-grid">
        <form class="card" @submit.prevent="addRestaurant">
          <h4>Рестораны</h4>
          <label>Новый ресторан</label>
          <input v-model="restaurantName" placeholder="Например: Чайхана Пушкина" />
          <button type="submit">Добавить ресторан</button>
        </form>
        <form class="card" @submit.prevent="addJobTitle">
          <h4>Роли в ресторане</h4>
          <label>Ресторан</label>
          <select v-model="selectedRestaurantId">
            <option value="" disabled>Выберите ресторан</option>
            <option v-for="restaurant in restaurants" :key="restaurant.id" :value="restaurant.id">
              {{ restaurant.name }}
            </option>
          </select>
          <label>Новая роль</label>
          <input v-model="jobTitleName" placeholder="Например: Официант" />
          <button type="submit">Добавить роль</button>
        </form>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ресторан</th>
              <th>Роли</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in restaurantsWithRoles" :key="item.id">
              <td>{{ item.name }}</td>
              <td>{{ item.roles.length ? item.roles.map((role) => role.name).join(", ") : "Пока нет ролей" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="auth.isSuperadmin" class="card requests-block">
      <h3>Заявки на регистрацию</h3>
      <div class="table-wrap">
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
            <tr v-for="request in requests" :key="request.id">
              <td>{{ request.first_name }}</td>
              <td>{{ request.last_name }}</td>
              <td>{{ request.restaurant }}</td>
              <td>{{ request.desired_job_title || "-" }}</td>
              <td>{{ request.desired_login }}</td>
              <td>
                {{
                  request.status === "pending"
                    ? "Ожидает"
                    : request.status === "approved"
                      ? "Одобрена"
                      : "Отклонена"
                }}
              </td>
              <td>
                <div v-if="request.status === 'pending'" class="actions-row">
                  <button type="button" @click="approveRequest(request.id)">Разрешить</button>
                  <button type="button" class="ghost" @click="rejectRequest(request.id)">Отклонить</button>
                </div>
                <span v-else>—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
