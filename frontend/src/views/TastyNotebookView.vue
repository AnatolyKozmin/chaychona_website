<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { api } from "../api/client";
import { useBodyScrollLock } from "../composables/useBodyScrollLock";
import { useAuthStore } from "../stores/auth";

interface DishCategory {
  id: number;
  name: string;
  restaurant_id?: string | null;
  branch_id?: number | null;
  menu_type: string | null;
  description?: string | null;
  is_active?: boolean;
}

interface MenuBranch {
  id: number;
  name: string;
  is_active: boolean;
  sort_order: number;
}

interface DishCard {
  id: number;
  name: string;
  ingredients: string | null;
  description: string | null;
  price: number;
  price_rubles: string | null;
  category: DishCategory | null;
  image_url: string | null;
  video_url: string | null;
  audio_url: string | null;
}

interface RestaurantItem {
  id: string;
  name: string;
}

interface DishAdminItem {
  id: number;
  name: string;
  ingredients: string | null;
  description: string | null;
  price: number;
  price_rubles: string | null;
  restaurant_id: string | null;
  category_id: number | null;
  category: DishCategory | null;
  is_available: boolean;
  is_active: boolean;
  photo_dish_path: string | null;
  photo_ingredients_path: string | null;
  audio_path: string | null;
  video_path: string | null;
}

const auth = useAuthStore();
const dishes = ref<DishCard[]>([]);
const categories = ref<DishCategory[]>([]);
const selectedCategory = ref("");
const loading = ref(false);
const error = ref("");
const currentIndex = ref(0);
const showVideo = ref(false);
const cardOffsetX = ref(0);
let dragStartX = 0;
let dragging = false;
const adminLoading = ref(false);
const adminError = ref("");
const adminSuccess = ref("");
const restaurants = ref<RestaurantItem[]>([]);
const adminCategories = ref<DishCategory[]>([]);
const adminDishes = ref<DishAdminItem[]>([]);
const menuBranches = ref<MenuBranch[]>([]);
const editingDishId = ref<number | null>(null);
const editingCategoryId = ref<number | null>(null);
const editingBranchId = ref<number | null>(null);
const categoryModalOpen = ref(false);
const dishModalOpen = ref(false);
const branchModalOpen = ref(false);
const selectedRestaurantTab = ref("all");
const openedCategoryIds = ref<Array<number | string>>([]);
const selectedCategorySubmenu = ref("all");
const categoriesPanelOpen = ref(false);
const categorySearch = ref("");

const categoryForm = reactive({
  name: "",
  restaurant_id: "",
  branch_id: "",
  menu_type: "",
  description: "",
  is_active: true
});

const branchForm = reactive({
  name: "",
  is_active: true,
  sort_order: 0
});

const dishForm = reactive({
  name: "",
  ingredients: "",
  description: "",
  price: 0,
  price_rubles: "",
  restaurant_id: "",
  category_id: "",
  is_available: true,
  is_active: true,
  photo_dish_path: "",
  photo_ingredients_path: "",
  audio_path: "",
  video_path: ""
});

const currentDish = computed(() => dishes.value[currentIndex.value] ?? null);
const hasNext = computed(() => currentIndex.value < dishes.value.length - 1);
const hasPrev = computed(() => currentIndex.value > 0);
const isSuperadmin = computed(() => auth.isSuperadmin);
const restaurantTabs = computed(() => [{ id: "all", name: "Все рестораны" }, ...restaurants.value]);
const restaurantNameById = computed(() => {
  const map = new Map<string, string>();
  for (const restaurant of restaurants.value) {
    map.set(restaurant.id, restaurant.name);
  }
  return map;
});
const dishesForSelectedRestaurant = computed(() =>
  adminDishes.value.filter((dish) => selectedRestaurantTab.value === "all" || dish.restaurant_id === selectedRestaurantTab.value)
);
const selectedRestaurantStats = computed(() => {
  const total = dishesForSelectedRestaurant.value.length;
  const active = dishesForSelectedRestaurant.value.filter((dish) => dish.is_active).length;
  const inactive = total - active;
  return { total, active, inactive };
});
const filteredAdminCategories = computed(() => {
  const query = categorySearch.value.trim().toLowerCase();
  if (!query) {
    return adminCategories.value;
  }
  return adminCategories.value.filter((category) => {
    const name = category.name.toLowerCase();
    const type = (category.menu_type || "").toLowerCase();
    return name.includes(query) || type.includes(query);
  });
});
const categoryBranchOptions = computed(() => menuBranches.value.filter((branch) => branch.is_active || branch.id === Number(categoryForm.branch_id)));
const categoriesForDishForm = computed(() =>
  adminCategories.value.filter((category) => {
    if (!dishForm.restaurant_id) {
      return true;
    }
    return !category.restaurant_id || category.restaurant_id === dishForm.restaurant_id;
  })
);
const groupedDishes = computed(() => {
  const groups = new Map<
    number | string,
    { id: number | string; name: string; dishes: DishAdminItem[]; activeCount: number; inactiveCount: number }
  >();
  for (const dish of dishesForSelectedRestaurant.value) {
    const key = dish.category_id ?? "uncategorized";
    const name = dish.category?.name || "Без категории";
    if (!groups.has(key)) {
      groups.set(key, { id: key, name, dishes: [], activeCount: 0, inactiveCount: 0 });
    }
    const group = groups.get(key)!;
    group.dishes.push(dish);
    if (dish.is_active) {
      group.activeCount += 1;
    } else {
      group.inactiveCount += 1;
    }
  }
  return Array.from(groups.values()).sort((a, b) => a.name.localeCompare(b.name));
});
const categorySubmenuItems = computed(() =>
  groupedDishes.value.map((group) => ({ key: String(group.id), name: group.name, count: group.dishes.length }))
);
const visibleGroups = computed(() => {
  if (selectedCategorySubmenu.value === "all") {
    return groupedDishes.value;
  }
  return groupedDishes.value.filter((group) => String(group.id) === selectedCategorySubmenu.value);
});

function toMediaUrl(path: string | null): string | null {
  if (!path) {
    return null;
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const backendOrigin = new URL(baseUrl).origin;
  return `${backendOrigin}${path}`;
}

async function loadCategories() {
  try {
    const { data } = await api.get<DishCategory[]>("/menu/categories");
    categories.value = data;
  } catch {
    categories.value = [];
  }
}

async function loadDishes() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<{ total: number; items: DishCard[] }>("/menu/feed", {
      params: { limit: 100, category: selectedCategory.value || undefined }
    });
    dishes.value = data.items;
    currentIndex.value = 0;
    showVideo.value = false;
  } catch (e: any) {
    const detail = e?.response?.data?.detail;
    error.value = Array.isArray(detail)
      ? "Ошибка параметров запроса ленты блюд."
      : detail ?? "Не удалось загрузить блюда";
  } finally {
    loading.value = false;
  }
}

async function loadRestaurants() {
  const { data } = await api.get<RestaurantItem[]>("/users/catalog/restaurants");
  restaurants.value = data;
  if (!dishForm.restaurant_id && data.length > 0) {
    dishForm.restaurant_id = data[0].id;
  }
}

async function loadAdminCategories() {
  const { data } = await api.get<DishCategory[]>("/menu/admin/categories");
  adminCategories.value = data;
  if (!dishForm.category_id && data.length > 0) {
    dishForm.category_id = String(data[0].id);
  }
}

async function loadMenuBranches() {
  const { data } = await api.get<MenuBranch[]>("/menu/admin/branches");
  menuBranches.value = data;
  if (!categoryForm.branch_id) {
    const firstActive = data.find((branch) => branch.is_active);
    categoryForm.branch_id = firstActive ? String(firstActive.id) : "";
  }
}

async function loadAdminDishes() {
  const { data } = await api.get<DishAdminItem[]>("/menu/admin/dishes");
  adminDishes.value = data;
  const availableIds = new Set(groupedDishes.value.map((group) => group.id));
  openedCategoryIds.value = openedCategoryIds.value.filter((id) => availableIds.has(id));
}

function resetCategoryForm() {
  editingCategoryId.value = null;
  categoryForm.name = "";
  categoryForm.restaurant_id = "";
  categoryForm.branch_id = "";
  categoryForm.menu_type = "";
  categoryForm.description = "";
  categoryForm.is_active = true;
}

function resetBranchForm() {
  editingBranchId.value = null;
  branchForm.name = "";
  branchForm.is_active = true;
  branchForm.sort_order = 0;
}

function resetDishForm() {
  editingDishId.value = null;
  dishForm.name = "";
  dishForm.ingredients = "";
  dishForm.description = "";
  dishForm.price = 0;
  dishForm.price_rubles = "";
  dishForm.restaurant_id = restaurants.value[0]?.id ?? "";
  dishForm.category_id = adminCategories.value[0] ? String(adminCategories.value[0].id) : "";
  dishForm.is_available = true;
  dishForm.is_active = true;
  dishForm.photo_dish_path = "";
  dishForm.photo_ingredients_path = "";
  dishForm.audio_path = "";
  dishForm.video_path = "";
}

function startEditCategory(category: DishCategory & { description?: string | null; is_active?: boolean }) {
  editingCategoryId.value = category.id;
  categoryForm.name = category.name;
  categoryForm.restaurant_id = category.restaurant_id || "";
  categoryForm.branch_id = category.branch_id ? String(category.branch_id) : "";
  categoryForm.menu_type = category.menu_type || "";
  categoryForm.description = category.description || "";
  categoryForm.is_active = category.is_active ?? true;
}

function startEditBranch(branch: MenuBranch) {
  editingBranchId.value = branch.id;
  branchForm.name = branch.name;
  branchForm.is_active = branch.is_active;
  branchForm.sort_order = branch.sort_order;
}

function openCreateCategoryModal() {
  resetCategoryForm();
  categoryModalOpen.value = true;
}

function openEditCategoryModal(category: DishCategory & { description?: string | null; is_active?: boolean }) {
  startEditCategory(category);
  categoryModalOpen.value = true;
}

function openCreateBranchModal() {
  resetBranchForm();
  branchModalOpen.value = true;
}

function openEditBranchModal(branch: MenuBranch) {
  startEditBranch(branch);
  branchModalOpen.value = true;
}

function openCreateDishModal() {
  resetDishForm();
  dishModalOpen.value = true;
}

function openEditDishModal(dish: DishAdminItem) {
  startEditDish(dish);
  dishModalOpen.value = true;
}

function startEditDish(dish: DishAdminItem) {
  editingDishId.value = dish.id;
  dishForm.name = dish.name;
  dishForm.ingredients = dish.ingredients || "";
  dishForm.description = dish.description || "";
  dishForm.price = dish.price;
  dishForm.price_rubles = dish.price_rubles || "";
  dishForm.restaurant_id = dish.restaurant_id || "";
  dishForm.category_id = dish.category_id ? String(dish.category_id) : "";
  dishForm.is_available = dish.is_available;
  dishForm.is_active = dish.is_active;
  dishForm.photo_dish_path = dish.photo_dish_path || "";
  dishForm.photo_ingredients_path = dish.photo_ingredients_path || "";
  dishForm.audio_path = dish.audio_path || "";
  dishForm.video_path = dish.video_path || "";
}

async function saveCategory() {
  adminLoading.value = true;
  adminError.value = "";
  adminSuccess.value = "";
  try {
    const payload = {
      name: categoryForm.name,
      restaurant_id: categoryForm.restaurant_id || null,
      branch_id: categoryForm.branch_id ? Number(categoryForm.branch_id) : null,
      menu_type: categoryForm.menu_type || null,
      description: categoryForm.description || null,
      is_active: categoryForm.is_active
    };
    if (editingCategoryId.value) {
      await api.put(`/menu/admin/categories/${editingCategoryId.value}`, payload);
      adminSuccess.value = "Категория обновлена";
    } else {
      await api.post("/menu/admin/categories", payload);
      adminSuccess.value = "Категория создана";
    }
    await loadCategories();
    await loadAdminCategories();
    await loadMenuBranches();
    resetCategoryForm();
    categoryModalOpen.value = false;
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось сохранить категорию";
  } finally {
    adminLoading.value = false;
  }
}

async function saveBranch() {
  adminLoading.value = true;
  adminError.value = "";
  adminSuccess.value = "";
  try {
    const payload = {
      name: branchForm.name,
      is_active: branchForm.is_active,
      sort_order: Number(branchForm.sort_order) || 0
    };
    if (editingBranchId.value) {
      await api.put(`/menu/admin/branches/${editingBranchId.value}`, payload);
      adminSuccess.value = "Ветка обновлена";
    } else {
      await api.post("/menu/admin/branches", payload);
      adminSuccess.value = "Ветка создана";
    }
    await loadMenuBranches();
    await loadAdminCategories();
    resetBranchForm();
    branchModalOpen.value = false;
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось сохранить ветку";
  } finally {
    adminLoading.value = false;
  }
}

async function deleteBranch(branchId: number) {
  const ok = window.confirm("Удалить ветку? У категорий ветка будет очищена.");
  if (!ok) {
    return;
  }
  adminLoading.value = true;
  adminError.value = "";
  adminSuccess.value = "";
  try {
    await api.delete(`/menu/admin/branches/${branchId}`);
    adminSuccess.value = "Ветка удалена";
    await loadMenuBranches();
    await loadAdminCategories();
    if (editingBranchId.value === branchId) {
      resetBranchForm();
    }
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось удалить ветку";
  } finally {
    adminLoading.value = false;
  }
}

async function deleteCategory(categoryId: number) {
  const ok = window.confirm("Удалить категорию? У позиций категория будет очищена.");
  if (!ok) {
    return;
  }
  adminLoading.value = true;
  adminError.value = "";
  adminSuccess.value = "";
  try {
    await api.delete(`/menu/admin/categories/${categoryId}`);
    adminSuccess.value = "Категория удалена";
    await loadCategories();
    await loadAdminCategories();
    await loadAdminDishes();
    if (editingCategoryId.value === categoryId) {
      resetCategoryForm();
    }
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось удалить категорию";
  } finally {
    adminLoading.value = false;
  }
}

async function onUploadMedia(field: "photo_dish_path" | "photo_ingredients_path" | "audio_path" | "video_path", event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) {
    return;
  }
  adminLoading.value = true;
  adminError.value = "";
  try {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await api.post<{ path: string }>("/menu/admin/media", formData);
    dishForm[field] = data.path;
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось загрузить файл";
  } finally {
    adminLoading.value = false;
    target.value = "";
  }
}

async function saveDish() {
  adminLoading.value = true;
  adminError.value = "";
  adminSuccess.value = "";
  try {
    const payload = {
      name: dishForm.name,
      ingredients: dishForm.ingredients || null,
      description: dishForm.description || null,
      price: Number(dishForm.price) || 0,
      price_rubles: dishForm.price_rubles || null,
      restaurant_id: dishForm.restaurant_id || null,
      category_id: dishForm.category_id ? Number(dishForm.category_id) : null,
      is_available: dishForm.is_available,
      is_active: dishForm.is_active,
      photo_dish_path: dishForm.photo_dish_path || null,
      photo_ingredients_path: dishForm.photo_ingredients_path || null,
      audio_path: dishForm.audio_path || null,
      video_path: dishForm.video_path || null
    };
    if (editingDishId.value) {
      await api.put(`/menu/admin/dishes/${editingDishId.value}`, payload);
      adminSuccess.value = "Позиция обновлена";
    } else {
      await api.post("/menu/admin/dishes", payload);
      adminSuccess.value = "Позиция создана";
    }
    await loadAdminDishes();
    await loadDishes();
    resetDishForm();
    dishModalOpen.value = false;
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось сохранить позицию";
  } finally {
    adminLoading.value = false;
  }
}

async function deleteDish(dishId: number) {
  const ok = window.confirm("Удалить позицию?");
  if (!ok) {
    return;
  }
  adminLoading.value = true;
  adminError.value = "";
  adminSuccess.value = "";
  try {
    await api.delete(`/menu/admin/dishes/${dishId}`);
    adminSuccess.value = "Позиция удалена";
    await loadAdminDishes();
    await loadDishes();
    if (editingDishId.value === dishId) {
      resetDishForm();
    }
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось удалить позицию";
  } finally {
    adminLoading.value = false;
  }
}

function onCategoryChange() {
  void loadDishes();
}

function setRestaurantTab(tabId: string) {
  selectedRestaurantTab.value = tabId;
  selectedCategorySubmenu.value = "all";
  openedCategoryIds.value = [];
}

function setCategorySubmenu(categoryKey: string) {
  selectedCategorySubmenu.value = categoryKey;
  openedCategoryIds.value = [];
}

function toggleCategoryGroup(groupId: number | string) {
  if (openedCategoryIds.value.includes(groupId)) {
    openedCategoryIds.value = openedCategoryIds.value.filter((item) => item !== groupId);
    return;
  }
  openedCategoryIds.value.push(groupId);
}

function isCategoryGroupOpen(groupId: number | string): boolean {
  return openedCategoryIds.value.includes(groupId);
}

function getRestaurantName(restaurantId: string | null): string {
  if (!restaurantId) {
    return "-";
  }
  return restaurantNameById.value.get(restaurantId) || "-";
}

function goNext() {
  if (!hasNext.value) {
    return;
  }
  currentIndex.value += 1;
  showVideo.value = false;
}

function goPrev() {
  if (!hasPrev.value) {
    return;
  }
  currentIndex.value -= 1;
  showVideo.value = false;
}

function onPointerDown(event: PointerEvent) {
  dragging = true;
  dragStartX = event.clientX;
}

function onPointerMove(event: PointerEvent) {
  if (!dragging) {
    return;
  }
  cardOffsetX.value = event.clientX - dragStartX;
}

function onPointerUp() {
  if (!dragging) {
    return;
  }
  const threshold = 90;
  if (cardOffsetX.value <= -threshold) {
    goNext();
  } else if (cardOffsetX.value >= threshold) {
    goPrev();
  }
  cardOffsetX.value = 0;
  dragging = false;
}

onMounted(() => {
  void loadCategories();
  void loadDishes();
  if (isSuperadmin.value) {
    void loadRestaurants();
    void loadMenuBranches();
    void loadAdminCategories();
    void loadAdminDishes();
  }
});

watch(
  () => isSuperadmin.value,
  (enabled) => {
    if (!enabled) {
      return;
    }
    void loadRestaurants();
    void loadMenuBranches();
    void loadAdminCategories();
    void loadAdminDishes();
  }
);

watch(
  () => groupedDishes.value.map((group) => String(group.id)).join("|"),
  () => {
    const existingIds = new Set(groupedDishes.value.map((group) => group.id));
    openedCategoryIds.value = openedCategoryIds.value.filter((id) => existingIds.has(id));
  }
);

watch(
  () => dishForm.restaurant_id,
  (restaurantId) => {
    if (!dishForm.category_id) {
      return;
    }
    const selected = adminCategories.value.find((item) => String(item.id) === dishForm.category_id);
    if (!selected) {
      dishForm.category_id = "";
      return;
    }
    if (restaurantId && selected.restaurant_id && selected.restaurant_id !== restaurantId) {
      dishForm.category_id = "";
    }
  }
);

useBodyScrollLock(computed(() => categoryModalOpen.value || dishModalOpen.value || branchModalOpen.value));
</script>

<template>
  <section class="card">
    <h2>Вкусная тетрадь</h2>
    <label>Категория</label>
    <select v-model="selectedCategory" @change="onCategoryChange">
      <option value="">Все категории</option>
      <option v-for="category in categories" :key="category.id" :value="category.name">
        {{ category.name }}
      </option>
    </select>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>
    <p v-else-if="!currentDish">Блюда пока не импортированы.</p>

    <div
      v-else
      class="tinder-card"
      :style="{ transform: `translateX(${cardOffsetX}px) rotate(${cardOffsetX / 18}deg)` }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @pointerleave="onPointerUp"
    >
      <div class="media-box" :class="{ 'media-box-video': showVideo }">
        <div v-if="currentDish.video_url" class="media-switch">
          <button type="button" class="media-tab" :class="{ active: !showVideo }" @click="showVideo = false">
            Фото
          </button>
          <button type="button" class="media-tab" :class="{ active: showVideo }" @click="showVideo = true">
            Видео
          </button>
        </div>
        <img
          v-if="!showVideo && currentDish.image_url"
          :src="toMediaUrl(currentDish.image_url) || undefined"
          :alt="currentDish.name"
        />
        <video
          v-else-if="showVideo && currentDish.video_url"
          :src="toMediaUrl(currentDish.video_url) || undefined"
          controls
          playsinline
          preload="metadata"
        />
        <div v-else class="media-placeholder">Медиа недоступно</div>
      </div>

      <h3>{{ currentDish.name }}</h3>
      <p class="muted" v-if="currentDish.category">{{ currentDish.category.name }}</p>
      <p>{{ currentDish.description || "Описание пока не заполнено." }}</p>
      <p class="muted"><strong>Состав:</strong> {{ currentDish.ingredients || "—" }}</p>
      <audio
        v-if="currentDish.audio_url && !showVideo"
        :src="toMediaUrl(currentDish.audio_url) || undefined"
        controls
        preload="none"
        style="width: 100%; margin-top: 10px"
      />
    </div>

    <div v-if="currentDish" class="tinder-actions">
      <button type="button" class="ghost" :disabled="!hasPrev" @click="goPrev">Предыдущее</button>
      <button type="button" :disabled="!hasNext" @click="goNext">Следующее</button>
    </div>
  </section>

  <section v-if="isSuperadmin" class="card">
    <h2>Заполнение вкусной тетради</h2>
    <p class="muted">Фото и аудио обязательны по процессу. Видео можно прикрепить отдельно (если уже собрано).</p>
    <p v-if="adminError" class="error">{{ adminError }}</p>
    <p v-if="adminSuccess" class="muted">{{ adminSuccess }}</p>

    <div class="card">
      <div class="category-actions-header">
        <h3 style="margin: 0">Категории</h3>
        <div class="category-actions-buttons">
          <button type="button" class="ghost" @click="categoriesPanelOpen = !categoriesPanelOpen">
            {{ categoriesPanelOpen ? "Скрыть список" : "Показать список" }}
          </button>
          <button type="button" class="ghost" @click="openCreateBranchModal">Ветки меню</button>
          <button type="button" @click="openCreateCategoryModal">Создать категорию</button>
        </div>
      </div>
      <Transition name="fade-slide">
        <div v-if="categoriesPanelOpen" class="menu-category-panel">
          <label>Поиск по категориям</label>
          <input v-model="categorySearch" placeholder="Название или ветка" />
          <div class="menu-category-list">
            <div class="menu-category-item" v-for="cat in filteredAdminCategories" :key="cat.id">
              <div>
                <strong>{{ cat.name }}</strong>
                <p class="muted" style="margin: 4px 0 0 0">
                  {{ cat.menu_type || "без ветки" }} · {{ getRestaurantName(cat.restaurant_id || null) }}
                </p>
              </div>
              <div class="actions-row">
                <button type="button" class="ghost" @click="openEditCategoryModal(cat)">Редактировать</button>
                <button type="button" @click="deleteCategory(cat.id)">Удалить</button>
              </div>
            </div>
            <p v-if="filteredAdminCategories.length === 0" class="muted">Категории не найдены.</p>
          </div>
        </div>
      </Transition>
    </div>

    <div class="card">
      <h3 style="margin: 0">Позиции</h3>

      <div class="menu-toolbar">
        <div class="menu-toolbar-filters">
          <div class="filter-row">
            <label class="filter-label">Ресторан</label>
            <select v-model="selectedRestaurantTab" class="filter-select">
              <option v-for="tab in restaurantTabs" :key="tab.id" :value="tab.id">
                {{ tab.name }}
              </option>
            </select>
          </div>
          <div class="filter-row">
            <label class="filter-label">Категория</label>
            <select v-model="selectedCategorySubmenu" class="filter-select">
              <option value="all">Все категории</option>
              <option v-for="item in categorySubmenuItems" :key="item.key" :value="item.key">
                {{ item.name }} ({{ item.count }})
              </option>
            </select>
          </div>
        </div>
        <button type="button" class="menu-add-btn" @click="openCreateDishModal">+ Новая позиция</button>
      </div>
      <div class="menu-stats-row">
        <span class="status-chip">Всего: {{ selectedRestaurantStats.total }}</span>
        <span class="status-chip status-chip-success">Активных: {{ selectedRestaurantStats.active }}</span>
        <span class="status-chip status-chip-muted">Неактивных: {{ selectedRestaurantStats.inactive }}</span>
      </div>

      <div class="menu-accordion" style="margin-top: 10px">
        <div class="menu-group" v-for="group in visibleGroups" :key="group.id">
          <button type="button" class="menu-group-header" @click="toggleCategoryGroup(group.id)">
            <span>{{ group.name }}</span>
            <span class="menu-group-meta">
              <span class="status-chip">{{ group.dishes.length }} поз.</span>
              <span class="status-chip status-chip-success">{{ group.activeCount }} акт.</span>
              <span class="status-chip status-chip-muted">{{ group.inactiveCount }} неакт.</span>
            </span>
          </button>
          <Transition name="accordion">
            <div v-if="isCategoryGroupOpen(group.id)" class="menu-group-body">
              <div class="menu-dish-row" v-for="dish in group.dishes" :key="dish.id">
                <div>
                  <strong>{{ dish.name }}</strong>
                  <p class="muted" style="margin: 4px 0 0 0">
                    {{ getRestaurantName(dish.restaurant_id) }} · фото:
                    {{ dish.photo_dish_path ? "да" : "нет" }} · аудио: {{ dish.audio_path ? "да" : "нет" }} · видео:
                    {{ dish.video_path ? "да" : "нет" }}
                  </p>
                </div>
                <div class="actions-row">
                  <button type="button" class="ghost" @click="openEditDishModal(dish)">Редактировать</button>
                  <button type="button" @click="deleteDish(dish.id)">Удалить</button>
                </div>
              </div>
            </div>
          </Transition>
        </div>
        <p v-if="groupedDishes.length === 0" class="muted">Для выбранного ресторана пока нет позиций.</p>
        <p v-else-if="visibleGroups.length === 0" class="muted">В выбранной категории пока нет позиций.</p>
      </div>
    </div>
  </section>

  <Transition name="fade-scale">
    <div v-if="categoryModalOpen" class="modal-backdrop" @click.self="categoryModalOpen = false">
      <div class="modal-window">
      <div class="actions-row">
        <h3 style="margin: 0">{{ editingCategoryId ? "Редактирование категории" : "Новая категория" }}</h3>
        <button type="button" class="ghost" @click="categoryModalOpen = false">Закрыть</button>
      </div>
      <form @submit.prevent="saveCategory">
        <label>Название категории</label>
        <input v-model="categoryForm.name" required />
        <label>Ресторан</label>
        <select v-model="categoryForm.restaurant_id">
          <option value="">Все рестораны</option>
          <option v-for="r in restaurants" :key="r.id" :value="r.id">{{ r.name }}</option>
        </select>
        <label>Ветка меню</label>
        <div class="inline-select-actions">
          <select v-model="categoryForm.branch_id">
            <option value="">Без ветки</option>
            <option v-for="branch in categoryBranchOptions" :key="branch.id" :value="String(branch.id)">
              {{ branch.name }}
            </option>
          </select>
          <button type="button" class="ghost" @click="openCreateBranchModal">Управлять ветками</button>
        </div>
        <label>Описание</label>
        <input v-model="categoryForm.description" />
        <label>
          <input type="checkbox" v-model="categoryForm.is_active" />
          Активная
        </label>
        <div class="actions-row" style="margin-top: 10px">
          <button type="submit" :disabled="adminLoading">{{ editingCategoryId ? "Сохранить" : "Создать" }}</button>
          <button type="button" class="ghost" @click="openCreateCategoryModal">Очистить</button>
        </div>
      </form>
      </div>
    </div>
  </Transition>

  <Transition name="fade-scale">
    <div v-if="dishModalOpen" class="modal-backdrop" @click.self="dishModalOpen = false">
      <div class="modal-window modal-window-wide">
      <div class="actions-row">
        <h3 style="margin: 0">{{ editingDishId ? "Редактирование позиции" : "Новая позиция" }}</h3>
        <button type="button" class="ghost" @click="dishModalOpen = false">Закрыть</button>
      </div>
      <form @submit.prevent="saveDish">
        <label>Название</label>
        <input v-model="dishForm.name" required />
        <label>Ресторан</label>
        <select v-model="dishForm.restaurant_id">
          <option value="" disabled>Выберите ресторан</option>
          <option v-for="r in restaurants" :key="r.id" :value="r.id">{{ r.name }}</option>
        </select>
        <label>Категория</label>
        <select v-model="dishForm.category_id">
          <option value="">Без категории</option>
          <option v-for="cat in categoriesForDishForm" :key="cat.id" :value="String(cat.id)">
            {{ cat.name }}{{ cat.menu_type ? ` (${cat.menu_type})` : "" }}
          </option>
        </select>
        <label>Описание</label>
        <input v-model="dishForm.description" />
        <label>Состав</label>
        <input v-model="dishForm.ingredients" />
        <div class="actions-row">
          <div style="flex: 1">
            <label>Цена (число)</label>
            <input v-model.number="dishForm.price" type="number" min="0" />
          </div>
          <div style="flex: 1">
            <label>Цена (текст)</label>
            <input v-model="dishForm.price_rubles" placeholder="1 250 руб." />
          </div>
        </div>
        <label>
          <input type="checkbox" v-model="dishForm.is_available" />
          Доступна
        </label>
        <label>
          <input type="checkbox" v-model="dishForm.is_active" />
          Активна
        </label>

        <div class="card">
          <h4>Медиа</h4>
          <label>Фото блюда</label>
          <div class="actions-row">
            <input v-model="dishForm.photo_dish_path" placeholder="uploads/..." />
            <input type="file" accept="image/*" @change="onUploadMedia('photo_dish_path', $event)" />
          </div>
          <label>Фото ингредиентов</label>
          <div class="actions-row">
            <input v-model="dishForm.photo_ingredients_path" placeholder="uploads/..." />
            <input type="file" accept="image/*" @change="onUploadMedia('photo_ingredients_path', $event)" />
          </div>
          <label>Аудио</label>
          <div class="actions-row">
            <input v-model="dishForm.audio_path" placeholder="uploads/..." />
            <input type="file" accept="audio/*" @change="onUploadMedia('audio_path', $event)" />
          </div>
          <label>Видео (опционально)</label>
          <div class="actions-row">
            <input v-model="dishForm.video_path" placeholder="uploads/..." />
            <input type="file" accept="video/*" @change="onUploadMedia('video_path', $event)" />
          </div>
        </div>

        <div class="actions-row" style="margin-top: 10px">
          <button type="submit" :disabled="adminLoading">{{ editingDishId ? "Сохранить" : "Создать" }}</button>
          <button type="button" class="ghost" @click="openCreateDishModal">Очистить</button>
        </div>
      </form>
      </div>
    </div>
  </Transition>

  <Transition name="fade-scale">
    <div v-if="branchModalOpen" class="modal-backdrop" @click.self="branchModalOpen = false">
      <div class="modal-window">
      <div class="actions-row">
        <h3 style="margin: 0">{{ editingBranchId ? "Редактирование ветки" : "Новая ветка меню" }}</h3>
        <button type="button" class="ghost" @click="branchModalOpen = false">Закрыть</button>
      </div>
      <form @submit.prevent="saveBranch">
        <label>Название ветки</label>
        <input v-model="branchForm.name" placeholder="Кухня, Бар, Десерты..." required />
        <label>Порядок</label>
        <input v-model.number="branchForm.sort_order" type="number" min="0" />
        <label>
          <input type="checkbox" v-model="branchForm.is_active" />
          Активная
        </label>
        <div class="actions-row" style="margin-top: 10px">
          <button type="submit" :disabled="adminLoading">{{ editingBranchId ? "Сохранить" : "Создать" }}</button>
          <button type="button" class="ghost" @click="openCreateBranchModal">Очистить</button>
        </div>
      </form>
      <div class="menu-category-list" style="margin-top: 12px">
        <div class="menu-category-item" v-for="branch in menuBranches" :key="branch.id">
          <div>
            <strong>{{ branch.name }}</strong>
            <p class="muted" style="margin: 4px 0 0 0">Порядок: {{ branch.sort_order }}</p>
          </div>
          <div class="actions-row">
            <button type="button" class="ghost" @click="openEditBranchModal(branch)">Редактировать</button>
            <button type="button" @click="deleteBranch(branch.id)">Удалить</button>
          </div>
        </div>
        <p v-if="menuBranches.length === 0" class="muted">Пока нет веток меню.</p>
      </div>
      </div>
    </div>
  </Transition>
</template>
