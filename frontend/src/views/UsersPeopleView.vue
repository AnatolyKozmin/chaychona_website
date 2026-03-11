<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";

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

interface UserAttempt {
  id: number;
  test_id: number;
  test_title: string;
  finished_at: string;
  total_questions: number;
  correct_answers: number;
  score_percent: number;
}

interface UserChecklistCompletion {
  id: number;
  checklist_id: number;
  checklist_title: string;
  completed_at: string;
  items_count: number;
}

interface UserActivity {
  attempts: UserAttempt[];
  checklist_completions: UserChecklistCompletion[];
}

const users = ref<UserRecord[]>([]);
const loading = ref(false);
const error = ref("");
const searchQuery = ref("");
const filterRole = ref("");
const filterRestaurant = ref("");
const selectedUser = ref<UserRecord | null>(null);
const activity = ref<UserActivity | null>(null);
const activityLoading = ref(false);

const filteredUsers = computed(() => {
  let list = users.value;
  const q = searchQuery.value.trim().toLowerCase();
  if (q) {
    list = list.filter(
      (u) =>
        u.full_name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        (u.restaurant || "").toLowerCase().includes(q) ||
        (u.job_title || "").toLowerCase().includes(q)
    );
  }
  if (filterRole.value) {
    list = list.filter((u) => u.role === filterRole.value);
  }
  if (filterRestaurant.value) {
    list = list.filter((u) => (u.restaurant || "") === filterRestaurant.value);
  }
  return list;
});

const restaurants = computed(() => {
  const set = new Set<string>();
  for (const u of users.value) {
    if (u.restaurant) set.add(u.restaurant);
  }
  return [...set].sort((a, b) => a.localeCompare(b));
});

function formatDate(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("ru-RU");
}

async function loadUsers() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<UserRecord[]>("/users");
    users.value = data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить список";
  } finally {
    loading.value = false;
  }
}

async function openUserDetail(user: UserRecord) {
  selectedUser.value = user;
  activity.value = null;
  activityLoading.value = true;
  try {
    const { data } = await api.get<UserActivity>(`/users/${user.id}/activity`);
    activity.value = data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить активность";
  } finally {
    activityLoading.value = false;
  }
}

function closeUserDetail() {
  selectedUser.value = null;
  activity.value = null;
}

function scorePercent(item: { total_questions: number; correct_answers: number }): number {
  if (!item.total_questions) return 0;
  return Math.round((item.correct_answers / item.total_questions) * 100);
}

onMounted(() => {
  loadUsers();
});
</script>

<template>
  <section class="card">
    <h2>Список лиц</h2>
    <p class="page-desc">Все пользователи системы. Нажмите на человека, чтобы посмотреть активность: тесты, чек-листы.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>

    <template v-if="!loading">
      <div class="menu-toolbar" style="margin-bottom: 16px">
        <div class="menu-toolbar-filters">
          <div class="filter-row">
            <label class="filter-label">Поиск</label>
            <input
              v-model="searchQuery"
              type="text"
              class="filter-select"
              placeholder="Имя, email, ресторан..."
            />
          </div>
          <div class="filter-row">
            <label class="filter-label">Роль</label>
            <select v-model="filterRole" class="filter-select">
              <option value="">Все</option>
              <option value="superadmin">Суперадмин</option>
              <option value="admin">Админ</option>
              <option value="learner">Обучающийся</option>
            </select>
          </div>
          <div class="filter-row">
            <label class="filter-label">Ресторан</label>
            <select v-model="filterRestaurant" class="filter-select">
              <option value="">Все</option>
              <option v-for="r in restaurants" :key="r" :value="r">{{ r }}</option>
            </select>
          </div>
        </div>
        <button type="button" class="ghost" @click="loadUsers">Обновить</button>
      </div>

      <p v-if="filteredUsers.length === 0" class="muted">Никого не найдено.</p>
      <div v-else class="people-list">
        <div
          v-for="user in filteredUsers"
          :key="user.id"
          class="people-card"
          @click="openUserDetail(user)"
        >
          <div class="people-card-main">
            <strong>{{ user.full_name }}</strong>
            <p class="muted" style="margin: 4px 0 0 0; font-size: 13px">{{ user.email }}</p>
            <p v-if="user.restaurant || user.job_title" class="muted" style="margin: 4px 0 0 0; font-size: 12px">
              {{ user.restaurant || "-" }} · {{ user.job_title || "-" }}
            </p>
          </div>
          <span class="people-card-role">{{ user.role }}</span>
          <span class="people-card-arrow">→</span>
        </div>
      </div>
    </template>
  </section>

  <Transition name="fade-scale">
    <div v-if="selectedUser" class="modal-backdrop" @click.self="closeUserDetail">
      <div class="modal-window modal-window-wide">
        <div class="actions-row">
          <h3 style="margin: 0">Активность: {{ selectedUser.full_name }}</h3>
          <button type="button" class="ghost" @click="closeUserDetail">Закрыть</button>
        </div>
        <p class="muted" style="margin: 0 0 6px 0">{{ selectedUser.email }}</p>
        <p v-if="selectedUser.restaurant" class="muted" style="margin: 0 0 16px 0">
          {{ selectedUser.restaurant }} · {{ selectedUser.job_title || "-" }}
        </p>

        <p v-if="activityLoading">Загрузка...</p>
        <template v-else-if="activity">
          <h4 style="margin: 16px 0 10px 0">Тесты</h4>
          <p v-if="activity.attempts.length === 0" class="muted">Попыток пока нет.</p>
          <div v-else class="attempt-result-list">
            <div
              v-for="a in activity.attempts"
              :key="a.id"
              class="test-result-card"
              :class="scorePercent(a) >= 70 ? 'test-result-card--correct' : 'test-result-card--incorrect'"
            >
              <div class="actions-row" style="flex-wrap: wrap; gap: 8px">
                <div>
                  <strong>{{ a.test_title }}</strong>
                  <p class="muted" style="margin: 4px 0 0 0">
                    {{ formatDate(a.finished_at) }} · {{ a.correct_answers }}/{{ a.total_questions }} ({{ a.score_percent }}%)
                  </p>
                </div>
                <RouterLink
                  :to="{ name: 'tests-analytics', query: { user: selectedUser?.full_name } }"
                  class="ghost"
                  @click="closeUserDetail"
                >
                  Подробнее
                </RouterLink>
              </div>
            </div>
          </div>

          <h4 style="margin: 20px 0 10px 0">Чек-листы</h4>
          <p v-if="activity.checklist_completions.length === 0" class="muted">Прохождений пока нет.</p>
          <div v-else class="attempt-result-list">
            <div
              v-for="c in activity.checklist_completions"
              :key="c.id"
              class="test-result-card test-result-card--correct"
            >
              <div class="actions-row">
                <div>
                  <strong>{{ c.checklist_title }}</strong>
                  <p class="muted" style="margin: 4px 0 0 0">
                    {{ formatDate(c.completed_at) }} · {{ c.items_count }} пунктов
                  </p>
                </div>
                <RouterLink
                  :to="{ name: 'checklists', query: { tab: 'reports', user_id: selectedUser?.id } }"
                  class="ghost"
                  @click="closeUserDetail"
                >
                  В отчёты
                </RouterLink>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </Transition>
</template>
