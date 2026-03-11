<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const mobileMenuOpen = ref(false);
const usersDropdownOpen = ref(false);

onMounted(async () => {
  if (auth.isAuthenticated) {
    try {
      await auth.fetchMe();
    } catch {
      await auth.refresh();
    }
  }
});

function handleLogout() {
  mobileMenuOpen.value = false;
  auth.logout();
  router.push({ name: "login" });
}

function openMobileMenu() {
  mobileMenuOpen.value = true;
}

function closeMobileMenu() {
  mobileMenuOpen.value = false;
}

watch(
  () => route.fullPath,
  () => {
    mobileMenuOpen.value = false;
    usersDropdownOpen.value = false;
  }
);

const isUsersSection = computed(() =>
  route.path.startsWith("/users")
);
</script>

<template>
  <div class="layout">
    <header class="header">
      <h1>Обучение персонала</h1>
      <button
        v-if="auth.isAuthenticated"
        type="button"
        class="ghost mobile-menu-toggle"
        @click="openMobileMenu"
      >
        Меню
      </button>
      <nav v-if="auth.isAuthenticated" class="menu desktop-menu">
        <RouterLink to="/">Главная</RouterLink>
        <RouterLink to="/standards">Стандарты</RouterLink>
        <RouterLink to="/my-tests">Мои тесты</RouterLink>
        <RouterLink to="/my-checklists">Чек-листы</RouterLink>
        <RouterLink to="/tasty-notebook">Вкусная тетрадь</RouterLink>
        <RouterLink v-if="!auth.isSuperadmin && !auth.isAdmin" to="/statistics">Статистика</RouterLink>
        <RouterLink v-if="auth.isSuperadmin" to="/tests">Тесты</RouterLink>
        <RouterLink v-if="auth.isSuperadmin" to="/tests-analytics">Аналитика</RouterLink>
        <RouterLink v-if="auth.isAdmin || auth.isSuperadmin" to="/checklists">Чек-листы</RouterLink>
        <div v-if="auth.isAdmin || auth.isSuperadmin" class="menu-dropdown">
          <button type="button" class="menu-dropdown-trigger" :class="{ active: usersDropdownOpen || isUsersSection }" @click="usersDropdownOpen = !usersDropdownOpen">
            Пользователи ▾
          </button>
          <div v-show="usersDropdownOpen" class="menu-dropdown-panel">
            <RouterLink to="/users/access" @click="usersDropdownOpen = false">Доступы</RouterLink>
            <RouterLink to="/users/people" @click="usersDropdownOpen = false">Список лиц</RouterLink>
          </div>
        </div>
        <button type="button" class="ghost" @click="handleLogout">Выйти</button>
      </nav>
    </header>
    <div v-if="auth.isAuthenticated && mobileMenuOpen" class="mobile-menu-overlay" @click="closeMobileMenu" />
    <aside v-if="auth.isAuthenticated" class="mobile-sidebar" :class="{ open: mobileMenuOpen }">
      <div class="mobile-sidebar-header">
        <strong>Навигация</strong>
        <button type="button" class="ghost" @click="closeMobileMenu">Закрыть</button>
      </div>
      <nav class="mobile-sidebar-nav">
        <RouterLink to="/" @click="closeMobileMenu">Главная</RouterLink>
        <RouterLink to="/standards" @click="closeMobileMenu">Стандарты</RouterLink>
        <RouterLink to="/my-tests" @click="closeMobileMenu">Мои тесты</RouterLink>
        <RouterLink to="/my-checklists" @click="closeMobileMenu">Чек-листы</RouterLink>
        <RouterLink to="/tasty-notebook" @click="closeMobileMenu">Вкусная тетрадь</RouterLink>
        <RouterLink v-if="!auth.isSuperadmin && !auth.isAdmin" to="/statistics" @click="closeMobileMenu">Статистика</RouterLink>
        <RouterLink v-if="auth.isSuperadmin" to="/tests" @click="closeMobileMenu">Тесты</RouterLink>
        <RouterLink v-if="auth.isSuperadmin" to="/tests-analytics" @click="closeMobileMenu">Аналитика</RouterLink>
        <RouterLink v-if="auth.isAdmin || auth.isSuperadmin" to="/checklists" @click="closeMobileMenu">Чек-листы</RouterLink>
        <RouterLink v-if="auth.isAdmin || auth.isSuperadmin" to="/users/access" @click="closeMobileMenu">Доступы</RouterLink>
        <RouterLink v-if="auth.isAdmin || auth.isSuperadmin" to="/users/people" @click="closeMobileMenu">Список лиц</RouterLink>
        <button type="button" class="ghost mobile-logout" @click="handleLogout">Выйти</button>
      </nav>
    </aside>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>
