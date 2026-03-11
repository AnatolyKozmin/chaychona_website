<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "./stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const mobileMenuOpen = ref(false);
const mobileChecklistsExpanded = ref(false);
const mobileUsersExpanded = ref(false);
const usersDropdownOpen = ref(false);
const checklistsDropdownOpen = ref(false);
const checklistsDropdownRef = ref<HTMLElement | null>(null);
const usersDropdownRef = ref<HTMLElement | null>(null);

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
  if (isChecklistsSection.value) mobileChecklistsExpanded.value = true;
  if (isUsersSection.value) mobileUsersExpanded.value = true;
}

function closeMobileMenu() {
  mobileMenuOpen.value = false;
  mobileChecklistsExpanded.value = false;
  mobileUsersExpanded.value = false;
}

watch(
  () => route.fullPath,
  () => {
    mobileMenuOpen.value = false;
    usersDropdownOpen.value = false;
    checklistsDropdownOpen.value = false;
    mobileChecklistsExpanded.value = false;
    mobileUsersExpanded.value = false;
  }
);

const isUsersSection = computed(() =>
  route.path.startsWith("/users")
);

const isChecklistsSection = computed(() =>
  route.path === "/my-checklists" || route.path === "/checklists"
);

function handleClickOutside(e: MouseEvent) {
  const target = e.target as Node;
  if (
    (checklistsDropdownOpen.value && checklistsDropdownRef.value && !checklistsDropdownRef.value.contains(target)) ||
    (usersDropdownOpen.value && usersDropdownRef.value && !usersDropdownRef.value.contains(target))
  ) {
    checklistsDropdownOpen.value = false;
    usersDropdownOpen.value = false;
  }
}

onMounted(() => {
  document.addEventListener("click", handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener("click", handleClickOutside);
});
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
        <RouterLink v-if="!auth.isAdmin && !auth.isSuperadmin" to="/my-checklists">Чек-листы</RouterLink>
        <div v-else ref="checklistsDropdownRef" class="menu-dropdown">
          <button type="button" class="menu-dropdown-trigger" :class="{ active: checklistsDropdownOpen || isChecklistsSection }" @click="checklistsDropdownOpen = !checklistsDropdownOpen">
            Чек-листы ▾
          </button>
          <div v-show="checklistsDropdownOpen" class="menu-dropdown-panel">
            <RouterLink to="/my-checklists" @click="checklistsDropdownOpen = false">Чек-листы</RouterLink>
            <RouterLink to="/checklists" @click="checklistsDropdownOpen = false">Настройка чек-листов</RouterLink>
            <RouterLink :to="{ path: '/checklists', query: { tab: 'reports' } }" @click="checklistsDropdownOpen = false">Отчёты</RouterLink>
          </div>
        </div>
        <RouterLink to="/tasty-notebook">Вкусная тетрадь</RouterLink>
        <RouterLink v-if="!auth.isSuperadmin && !auth.isAdmin" to="/statistics">Статистика</RouterLink>
        <RouterLink v-if="auth.isSuperadmin" to="/tests">Тесты</RouterLink>
        <RouterLink v-if="auth.isSuperadmin" to="/tests-analytics">Аналитика</RouterLink>
        <div v-if="auth.isAdmin || auth.isSuperadmin" ref="usersDropdownRef" class="menu-dropdown">
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

        <template v-if="!auth.isAdmin && !auth.isSuperadmin">
          <RouterLink to="/my-checklists" @click="closeMobileMenu">Чек-листы</RouterLink>
        </template>
        <div v-else class="mobile-nav-group">
          <button
            type="button"
            class="mobile-nav-trigger"
            :class="{ active: mobileChecklistsExpanded || isChecklistsSection }"
            @click="mobileChecklistsExpanded = !mobileChecklistsExpanded"
          >
            Чек-листы {{ mobileChecklistsExpanded ? "▴" : "▾" }}
          </button>
          <div v-show="mobileChecklistsExpanded" class="mobile-nav-sub">
            <RouterLink to="/my-checklists" @click="closeMobileMenu">Чек-листы</RouterLink>
            <RouterLink to="/checklists" @click="closeMobileMenu">Настройка чек-листов</RouterLink>
            <RouterLink :to="{ path: '/checklists', query: { tab: 'reports' } }" @click="closeMobileMenu">Отчёты</RouterLink>
          </div>
        </div>

        <RouterLink to="/tasty-notebook" @click="closeMobileMenu">Вкусная тетрадь</RouterLink>
        <RouterLink v-if="!auth.isSuperadmin && !auth.isAdmin" to="/statistics" @click="closeMobileMenu">Статистика</RouterLink>
        <RouterLink v-if="auth.isSuperadmin" to="/tests" @click="closeMobileMenu">Тесты</RouterLink>
        <RouterLink v-if="auth.isSuperadmin" to="/tests-analytics" @click="closeMobileMenu">Аналитика</RouterLink>

        <div v-if="auth.isAdmin || auth.isSuperadmin" class="mobile-nav-group">
          <button
            type="button"
            class="mobile-nav-trigger"
            :class="{ active: mobileUsersExpanded || isUsersSection }"
            @click="mobileUsersExpanded = !mobileUsersExpanded"
          >
            Пользователи {{ mobileUsersExpanded ? "▴" : "▾" }}
          </button>
          <div v-show="mobileUsersExpanded" class="mobile-nav-sub">
            <RouterLink to="/users/access" @click="closeMobileMenu">Доступы</RouterLink>
            <RouterLink to="/users/people" @click="closeMobileMenu">Список лиц</RouterLink>
          </div>
        </div>

        <button type="button" class="ghost mobile-logout" @click="handleLogout">Выйти</button>
      </nav>
    </aside>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>
