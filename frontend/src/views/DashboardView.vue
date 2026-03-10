<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const loading = ref(false);
const error = ref("");

interface ProductBucket {
  bucket: string;
  items_count: number;
}

interface RestaurantStat {
  restaurant_id: string;
  restaurant_name: string;
  tests_count: number;
  learners_count: number;
}

interface TopResultItem {
  user_id: string;
  user_name: string;
  user_email: string;
  attempts_count: number;
  avg_score_percent: number;
  best_score_percent: number;
  last_attempt_at: string | null;
}

interface DashboardOverview {
  tests_created_total: number;
  products_total: number;
  attempts_day: number;
  attempts_week: number;
  attempts_month: number;
  products_by_bucket: ProductBucket[];
  restaurants: RestaurantStat[];
  top_results: TopResultItem[];
}

const overview = ref<DashboardOverview | null>(null);
const canSeeDashboard = computed(() => auth.user?.role === "superadmin" || auth.user?.role === "admin");
const isLearner = computed(() => auth.user?.role === "learner");

const roleLabel = computed(() => {
  switch (auth.user?.role) {
    case "superadmin":
      return "Суперадмин";
    case "admin":
      return "Админ";
    default:
      return "Обучающийся";
  }
});

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU");
}

async function loadOverview() {
  loading.value = true;
  error.value = "";
  try {
    if (canSeeDashboard.value) {
      const { data } = await api.get<DashboardOverview>("/dashboard/overview");
      overview.value = data;
    }
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить дашборд";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await loadOverview();
});
</script>

<template>
  <section class="card">
    <h2>Добро пожаловать, {{ auth.user?.full_name }}</h2>
    <p><strong>Роль:</strong> {{ roleLabel }}</p>
    <p><strong>Ресторан:</strong> {{ auth.user?.restaurant || "Не указан" }}</p>
    <p v-if="auth.user?.role === 'learner'">
      <strong>Должность:</strong> {{ auth.user?.job_title || "Не указана" }}
    </p>
    <p class="muted">
      Для обучающихся с разными должностями (официант, бармен и т.д.) уровень доступа одинаковый, но программа обучения может отличаться.
    </p>
  </section>

  <section v-if="canSeeDashboard" class="card">
    <div class="actions-row">
      <h2 style="margin: 0">Дашборд</h2>
      <button type="button" class="ghost" @click="loadOverview">Обновить</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>

    <template v-if="overview && !loading">
      <div class="dashboard-grid">
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Создано тестов</p>
          <h3 style="margin: 0">{{ overview.tests_created_total }}</h3>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Продукций в системе</p>
          <h3 style="margin: 0">{{ overview.products_total }}</h3>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Прохождений за день</p>
          <h3 style="margin: 0">{{ overview.attempts_day }}</h3>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Прохождений за неделю</p>
          <h3 style="margin: 0">{{ overview.attempts_week }}</h3>
        </div>
        <div class="clean-item">
          <p class="muted" style="margin: 0 0 6px">Прохождений за месяц</p>
          <h3 style="margin: 0">{{ overview.attempts_month }}</h3>
        </div>
      </div>

      <div class="card">
        <h3>Продукция по типам меню</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Тип</th>
                <th>Кол-во</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview.products_by_bucket" :key="item.bucket">
                <td>{{ item.bucket }}</td>
                <td>{{ item.items_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3>По ресторанам</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Ресторан</th>
                <th>Тестов</th>
                <th>Обучающихся</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="restaurant in overview.restaurants" :key="restaurant.restaurant_id">
                <td>{{ restaurant.restaurant_name }}</td>
                <td>{{ restaurant.tests_count }}</td>
                <td>{{ restaurant.learners_count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3>Топ по результатам</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Попыток</th>
                <th>Средний результат</th>
                <th>Лучший результат</th>
                <th>Последняя попытка</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview.top_results" :key="item.user_id">
                <td>
                  <div>{{ item.user_name }}</div>
                  <div class="muted" style="font-size: 12px">{{ item.user_email }}</div>
                </td>
                <td>{{ item.attempts_count }}</td>
                <td>{{ item.avg_score_percent.toFixed(1) }}%</td>
                <td>{{ item.best_score_percent.toFixed(1) }}%</td>
                <td>{{ formatDate(item.last_attempt_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </section>

  <section v-else-if="isLearner" class="card">
    <h2 style="margin: 0 0 16px 0">Меню</h2>
    <div class="menu-buttons-grid">
      <RouterLink to="/standards" class="menu-button">
        <span class="menu-button-title">Стандарты</span>
        <span class="muted">Обучение по стандартам</span>
      </RouterLink>
      <RouterLink to="/my-tests" class="menu-button">
        <span class="menu-button-title">Мои тесты</span>
        <span class="muted">Пройти тесты</span>
      </RouterLink>
      <RouterLink to="/tasty-notebook" class="menu-button">
        <span class="menu-button-title">Вкусная тетрадь</span>
        <span class="muted">Справочник продукции</span>
      </RouterLink>
      <RouterLink to="/statistics" class="menu-button">
        <span class="menu-button-title">Статистика</span>
        <span class="muted">Мой прогресс и результаты</span>
      </RouterLink>
    </div>
  </section>
</template>
