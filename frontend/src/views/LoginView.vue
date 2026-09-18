<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();

// На телефоне обе формы в одну колонку не помещаются осмысленно — показываем
// одну, а переключатель наверху. Новичок чаще всего приходит регистрироваться.
const mode = ref<"login" | "register">("login");

const loginForm = reactive({
  login: "",
  password: ""
});

const registerForm = reactive({
  first_name: "",
  last_name: "",
  restaurant_id: "",
  job_title: "",
  desired_login: "",
  password: ""
});

const restaurants = ref<Array<{ id: string; name: string }>>([]);
const jobTitles = ref<string[]>([]);
const catalogError = ref("");
const showLoginPassword = ref(false);
const showRegisterPassword = ref(false);

async function loadCatalogs() {
  try {
    const { data } = await api.get<Array<{ id: string; name: string }>>("/users/catalog/restaurants");
    restaurants.value = data;
    catalogError.value = "";
  } catch {
    catalogError.value = "Не удалось загрузить список ресторанов. Обновите страницу.";
  }
}

async function onRestaurantChange() {
  registerForm.job_title = "";
  jobTitles.value = [];
  if (!registerForm.restaurant_id) {
    return;
  }
  const { data } = await api.get<Array<{ id: string; name: string }>>("/users/catalog/job-titles", {
    params: { restaurant_id: registerForm.restaurant_id }
  });
  jobTitles.value = data.map((item) => item.name);
  if (jobTitles.value.length === 1) {
    registerForm.job_title = jobTitles.value[0];
  }
}

async function onLogin() {
  try {
    await auth.login({ login: loginForm.login.trim(), password: loginForm.password });
  } catch {
    return;
  }
  router.push({ name: "dashboard" });
}

async function onRegister() {
  const restaurant = restaurants.value.find((item) => item.id === registerForm.restaurant_id);
  try {
    await auth.register({
      first_name: registerForm.first_name.trim(),
      last_name: registerForm.last_name.trim(),
      restaurant: restaurant?.name ?? "",
      job_title: registerForm.job_title,
      desired_login: registerForm.desired_login.trim(),
      password: registerForm.password
    });
  } catch {
    return;
  }
  router.push({ name: "dashboard" });
}

onMounted(() => {
  void loadCatalogs();
});
</script>

<template>
  <section class="auth-single">
    <div class="auth-switch" role="tablist">
      <button
        type="button"
        role="tab"
        :class="{ active: mode === 'login' }"
        :aria-selected="mode === 'login'"
        @click="mode = 'login'"
      >
        Вход
      </button>
      <button
        type="button"
        role="tab"
        :class="{ active: mode === 'register' }"
        :aria-selected="mode === 'register'"
        @click="mode = 'register'"
      >
        Регистрация
      </button>
    </div>

    <form v-if="mode === 'login'" class="card" @submit.prevent="onLogin">
      <h2>Вход</h2>
      <label for="login-name">Логин</label>
      <input
        id="login-name"
        v-model="loginForm.login"
        autocomplete="username"
        autocapitalize="none"
        autocorrect="off"
        spellcheck="false"
        required
      />
      <label for="login-password">Пароль</label>
      <div class="password-field">
        <input
          id="login-password"
          v-model="loginForm.password"
          :type="showLoginPassword ? 'text' : 'password'"
          autocomplete="current-password"
          required
        />
        <button type="button" class="ghost password-toggle" @click="showLoginPassword = !showLoginPassword">
          {{ showLoginPassword ? "Скрыть" : "Показать" }}
        </button>
      </div>
      <p class="error" v-if="auth.errorMessage">{{ auth.errorMessage }}</p>
      <button type="submit" :disabled="auth.loading">Войти</button>
      <p class="muted auth-hint">
        Нет аккаунта?
        <a href="#" @click.prevent="mode = 'register'">Зарегистрируйтесь</a> — это минута, одобрения ждать не нужно.
        Забыли пароль — обратитесь к управляющему.
      </p>
    </form>

    <form v-else class="card" @submit.prevent="onRegister">
      <h2>Регистрация</h2>
      <p class="muted auth-hint">Аккаунт заработает сразу после регистрации.</p>

      <label for="reg-first">Имя</label>
      <input id="reg-first" v-model="registerForm.first_name" autocomplete="given-name" required />
      <label for="reg-last">Фамилия</label>
      <input id="reg-last" v-model="registerForm.last_name" autocomplete="family-name" required />

      <label for="reg-restaurant">Ресторан</label>
      <select id="reg-restaurant" v-model="registerForm.restaurant_id" required @change="onRestaurantChange">
        <option value="" disabled>Выберите ресторан</option>
        <option v-for="restaurant in restaurants" :key="restaurant.id" :value="restaurant.id">
          {{ restaurant.name }}
        </option>
      </select>
      <p class="error" v-if="catalogError">{{ catalogError }}</p>

      <label for="reg-job">Должность</label>
      <select id="reg-job" v-model="registerForm.job_title" :disabled="!registerForm.restaurant_id" required>
        <option value="" disabled>
          {{ registerForm.restaurant_id ? "Выберите должность" : "Сначала выберите ресторан" }}
        </option>
        <option v-for="jobTitle in jobTitles" :key="jobTitle" :value="jobTitle">{{ jobTitle }}</option>
      </select>

      <label for="reg-login">Логин</label>
      <input
        id="reg-login"
        v-model="registerForm.desired_login"
        autocomplete="username"
        autocapitalize="none"
        autocorrect="off"
        spellcheck="false"
        minlength="3"
        required
      />
      <p class="field-hint">
        Минимум 3 символа, без пробелов. Можно латиницей или по-русски, например <em>ivanova</em>
        или номер телефона. Большие и маленькие буквы не различаются.
      </p>

      <label for="reg-password">Пароль</label>
      <div class="password-field">
        <input
          id="reg-password"
          v-model="registerForm.password"
          :type="showRegisterPassword ? 'text' : 'password'"
          autocomplete="new-password"
          minlength="6"
          required
        />
        <button type="button" class="ghost password-toggle" @click="showRegisterPassword = !showRegisterPassword">
          {{ showRegisterPassword ? "Скрыть" : "Показать" }}
        </button>
      </div>
      <p class="field-hint">
        Минимум 6 символов. Любые буквы и цифры, русские тоже. Здесь большие и маленькие буквы
        различаются — запомните, как набрали. Нажмите «Показать», чтобы проверить.
      </p>

      <p class="error" v-if="auth.registerError">{{ auth.registerError }}</p>
      <button type="submit" :disabled="auth.loading">Зарегистрироваться и войти</button>
    </form>
  </section>
</template>
