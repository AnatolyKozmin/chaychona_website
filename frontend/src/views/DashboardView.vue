<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
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
const learnerOverview = ref<{
  total_trainings: number;
  completed_trainings: number;
  completed_percent: number;
  total_tests: number;
  attempts_count: number;
} | null>(null);
const canSeeDashboard = computed(() => auth.user?.role === "superadmin" || auth.user?.role === "admin");
const isLearner = computed(() => auth.user?.role === "learner");

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
      learnerOverview.value = null;
    } else if (isLearner.value) {
      const { data } = await api.get("/dashboard/me-overview");
      learnerOverview.value = {
        total_trainings: data.total_trainings,
        completed_trainings: data.completed_trainings,
        completed_percent: data.completed_percent,
        total_tests: data.total_tests,
        attempts_count: data.attempts_count
      };
      overview.value = null;
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

watch(
  () => auth.user?.role,
  () => {
    loadOverview();
  }
);
</script>

<template>
  <section class="card card-welcome">
    <h2 class="welcome-title">Добро пожаловать, {{ auth.user?.full_name }}</h2>
    <p class="welcome-subtitle"><strong>Ресторан:</strong> {{ auth.user?.restaurant || "Не указан" }}</p>
  </section>

  <hr v-if="canSeeDashboard" class="section-divider" />

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

  <template v-else>
    <hr class="section-divider" />
    <section class="card learner-dashboard">
    <div v-if="learnerOverview && !loading" class="learner-progress-preview">
      <div class="progress-preview-item">
        <span class="progress-preview-value">{{ learnerOverview.completed_trainings }} из {{ learnerOverview.total_trainings }}</span>
        <span class="progress-preview-label">обучений пройдено</span>
      </div>
      <div class="progress-preview-divider"></div>
      <div class="progress-preview-item">
        <span class="progress-preview-value">{{ learnerOverview.total_tests }}</span>
        <span class="progress-preview-label">тестов доступно</span>
      </div>
      <div class="progress-preview-divider"></div>
      <div class="progress-preview-item">
        <span class="progress-preview-value">{{ learnerOverview.attempts_count }}</span>
        <span class="progress-preview-label">попыток пройдено</span>
      </div>
    </div>

    <h2 class="section-title">Доступные разделы</h2>
    <div class="learner-menu-grid">
      <RouterLink to="/standards" class="learner-menu-card learner-menu-card--standards">
        <div class="learner-menu-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
            <path d="M8 7h8"/>
            <path d="M8 11h8"/>
          </svg>
        </div>
        <div class="learner-menu-content">
          <span class="learner-menu-title">Стандарты</span>
          <span class="learner-menu-desc">Обучение по стандартам и процедурам</span>
        </div>
        <span class="learner-menu-arrow">→</span>
      </RouterLink>

      <RouterLink to="/my-checklists" class="learner-menu-card learner-menu-card--checklists">
        <div class="learner-menu-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
            <rect x="9" y="3" width="6" height="4" rx="2"/>
            <path d="M9 12l2 2 4-4"/>
          </svg>
        </div>
        <div class="learner-menu-content">
          <span class="learner-menu-title">Чек-листы</span>
          <span class="learner-menu-desc">Открытие и закрытие смены</span>
        </div>
        <span class="learner-menu-arrow">→</span>
      </RouterLink>

      <RouterLink to="/my-tests" class="learner-menu-card learner-menu-card--tests">
        <div class="learner-menu-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 11l3 3L22 4"/>
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
          </svg>
        </div>
        <div class="learner-menu-content">
          <span class="learner-menu-title">Мои тесты</span>
          <span class="learner-menu-desc">Проверьте знания, пройдите тесты</span>
        </div>
        <span class="learner-menu-arrow">→</span>
      </RouterLink>

      <RouterLink to="/tasty-notebook" class="learner-menu-card learner-menu-card--notebook">
        <div class="learner-menu-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
          </svg>
        </div>
        <div class="learner-menu-content">
          <span class="learner-menu-title">Вкусная тетрадь</span>
          <span class="learner-menu-desc">Справочник блюд и продукции</span>
        </div>
        <span class="learner-menu-arrow">→</span>
      </RouterLink>

      <RouterLink to="/statistics" class="learner-menu-card learner-menu-card--stats">
        <div class="learner-menu-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 3v18h18"/>
            <path d="m19 9-5 5-4-4-3 3"/>
          </svg>
        </div>
        <div class="learner-menu-content">
          <span class="learner-menu-title">Статистика</span>
          <span class="learner-menu-desc">Ваш прогресс и результаты</span>
        </div>
        <span class="learner-menu-arrow">→</span>
      </RouterLink>
    </div>
    </section>
  </template>
</template>
