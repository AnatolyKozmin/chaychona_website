<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();

const loginForm = reactive({
  login: "",
  password: ""
});

const registerForm = reactive({
  first_name: "",
  last_name: "",
  restaurant: "",
  job_title: "",
  desired_login: "",
  password: ""
});
const registrationSent = reactive({ value: false });
const restaurants = ref<Array<{ id: string; name: string }>>([]);
const jobTitles = ref<string[]>([]);
const selectedRestaurantId = ref<string | null>(null);

async function loadCatalogs() {
  const restaurantsRes = await api.get<Array<{ id: string; name: string }>>("/users/catalog/restaurants");
  restaurants.value = restaurantsRes.data;
}

async function loadJobTitlesForRestaurant() {
  const restaurantId = selectedRestaurantId.value;
  if (!restaurantId) {
    jobTitles.value = [];
    return;
  }
  const jobTitlesRes = await api.get<Array<{ id: string; name: string }>>("/users/catalog/job-titles", {
    params: { restaurant_id: restaurantId }
  });
  jobTitles.value = jobTitlesRes.data.map((item) => item.name);
}

function onRestaurantChange() {
  const selected = restaurants.value.find((item) => item.name === registerForm.restaurant);
  selectedRestaurantId.value = selected?.id ?? null;
  void loadJobTitlesForRestaurant();
}

async function initCatalogs() {
  await loadCatalogs();
  const selected = restaurants.value.find((item) => item.name === registerForm.restaurant);
  selectedRestaurantId.value = selected?.id ?? null;
  await loadJobTitlesForRestaurant();
}

async function onLogin() {
  await auth.login(loginForm);
  router.push({ name: "dashboard" });
}

async function onRegister() {
  await auth.register(registerForm);
  registrationSent.value = true;
  registerForm.first_name = "";
  registerForm.last_name = "";
  registerForm.restaurant = "";
  registerForm.job_title = "";
  registerForm.desired_login = "";
  registerForm.password = "";
  selectedRestaurantId.value = null;
  await loadJobTitlesForRestaurant();
}

onMounted(() => {
  void initCatalogs();
});
</script>

<template>
  <section class="auth-grid">
    <form class="card" @submit.prevent="onLogin">
      <h2>Вход</h2>
      <label>Логин</label>
      <input v-model="loginForm.login" required />
      <label>Пароль</label>
      <input v-model="loginForm.password" type="password" required />
      <p class="error" v-if="auth.errorMessage">{{ auth.errorMessage }}</p>
      <button type="submit" :disabled="auth.loading">Войти</button>
    </form>

    <form class="card" @submit.prevent="onRegister">
      <h2>Заявка на доступ</h2>
      <label>Имя</label>
      <input v-model="registerForm.first_name" required />
      <label>Фамилия</label>
      <input v-model="registerForm.last_name" required />
      <label>Ресторан</label>
      <input v-model="registerForm.restaurant" list="restaurants-options" required @input="onRestaurantChange" />
      <datalist id="restaurants-options">
        <option v-for="restaurant in restaurants" :key="restaurant.id" :value="restaurant.name" />
      </datalist>
      <label>Роль в ресторане (должность)</label>
      <input v-model="registerForm.job_title" list="job-title-options" required />
      <datalist id="job-title-options">
        <option v-for="jobTitle in jobTitles" :key="jobTitle" :value="jobTitle" />
      </datalist>
      <label>Желаемый логин</label>
      <input v-model="registerForm.desired_login" required />
      <label>Желаемый пароль</label>
      <input v-model="registerForm.password" type="password" required />
      <p class="muted" v-if="registrationSent.value">
        Заявка отправлена. После одобрения супер-админом можно войти.
      </p>
      <button type="submit" :disabled="auth.loading">Зарегистрироваться</button>
    </form>
  </section>
</template>
