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
      if (!auth.isAuthenticated && route.name !== "login") {
        router.replace({ name: "login" });
      }
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

    <!-- Нижняя панель: до верха экрана большим пальцем не дотянуться, поэтому
         пять основных разделов живут внизу. Остальное (Статистика, разделы
         админа, выход) осталось в шторке под кнопкой «Меню». -->
    <nav v-if="auth.isAuthenticated" class="tabbar" aria-label="Основные разделы">
      <RouterLink to="/" class="tabbar-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M4 10.5L12 4l8 6.5V20a1 1 0 01-1 1h-4v-6H9v6H5a1 1 0 01-1-1z" />
        </svg>
        <span>Главная</span>
      </RouterLink>
      <RouterLink to="/standards" class="tabbar-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M5 4h11l3 3v13H5z" />
          <path d="M8.5 11h7M8.5 15h5" />
        </svg>
        <span>Стандарты</span>
      </RouterLink>
      <RouterLink to="/my-tests" class="tabbar-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M9 5h9v15H6V8z" />
          <path d="M9 12.5l2 2 4-4" />
        </svg>
        <span>Тесты</span>
      </RouterLink>
      <RouterLink to="/my-checklists" class="tabbar-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M4 6.5l2 2 3.5-3.5M4 15.5l2 2L9.5 14" />
          <path d="M13 7h7M13 16h7" />
        </svg>
        <span>Чек-листы</span>
      </RouterLink>
      <RouterLink to="/tasty-notebook" class="tabbar-item">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M7 4h10a1 1 0 011 1v15l-6-3-6 3V5a1 1 0 011-1z" />
        </svg>
        <span>Тетрадь</span>
      </RouterLink>
    </nav>
  </div>
</template>
