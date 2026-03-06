<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

interface DishCategory {
  id: number;
  name: string;
  menu_type: string | null;
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
const dishFilterRestaurant = ref("");
const dishFilterCategory = ref("");
const editingDishId = ref<number | null>(null);
const editingCategoryId = ref<number | null>(null);

const categoryForm = reactive({
  name: "",
  menu_type: "",
  description: "",
  is_active: true
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

async function loadAdminDishes() {
  const { data } = await api.get<DishAdminItem[]>("/menu/admin/dishes", {
    params: {
      restaurant_id: dishFilterRestaurant.value || undefined,
      category_id: dishFilterCategory.value || undefined
    }
  });
  adminDishes.value = data;
}

function resetCategoryForm() {
  editingCategoryId.value = null;
  categoryForm.name = "";
  categoryForm.menu_type = "";
  categoryForm.description = "";
  categoryForm.is_active = true;
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
  categoryForm.menu_type = category.menu_type || "";
  categoryForm.description = category.description || "";
  categoryForm.is_active = category.is_active ?? true;
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
    resetCategoryForm();
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось сохранить категорию";
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
    void loadAdminCategories();
    void loadAdminDishes();
  }
});
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
      <h3>Категории</h3>
      <form @submit.prevent="saveCategory">
        <label>Название категории</label>
        <input v-model="categoryForm.name" required />
        <label>Тип меню</label>
        <input v-model="categoryForm.menu_type" placeholder="kitchen / bar" />
        <label>Описание</label>
        <input v-model="categoryForm.description" />
        <label>
          <input type="checkbox" v-model="categoryForm.is_active" />
          Активная
        </label>
        <div class="actions-row" style="margin-top: 10px">
          <button type="submit" :disabled="adminLoading">{{ editingCategoryId ? "Сохранить" : "Создать" }}</button>
          <button type="button" class="ghost" @click="resetCategoryForm">Сброс</button>
        </div>
      </form>
      <div class="table-wrap" style="margin-top: 10px">
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Тип</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="cat in adminCategories" :key="cat.id">
              <td>{{ cat.name }}</td>
              <td>{{ cat.menu_type || "-" }}</td>
              <td>
                <div class="actions-row">
                  <button type="button" class="ghost" @click="startEditCategory(cat)">Редактировать</button>
                  <button type="button" @click="deleteCategory(cat.id)">Удалить</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="actions-row">
        <h3 style="margin: 0">Позиции</h3>
        <button type="button" class="ghost" @click="resetDishForm">Новая позиция</button>
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
          <option v-for="cat in adminCategories" :key="cat.id" :value="String(cat.id)">{{ cat.name }}</option>
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
          <button type="button" class="ghost" @click="resetDishForm">Сброс</button>
        </div>
      </form>

      <div class="actions-row" style="margin-top: 12px">
        <div style="flex: 1">
          <label>Фильтр по ресторану</label>
          <select v-model="dishFilterRestaurant" @change="loadAdminDishes">
            <option value="">Все рестораны</option>
            <option v-for="r in restaurants" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
        </div>
        <div style="flex: 1">
          <label>Фильтр по категории</label>
          <select v-model="dishFilterCategory" @change="loadAdminDishes">
            <option value="">Все категории</option>
            <option v-for="cat in adminCategories" :key="cat.id" :value="String(cat.id)">{{ cat.name }}</option>
          </select>
        </div>
      </div>

      <div class="table-wrap" style="margin-top: 10px">
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Ресторан</th>
              <th>Категория</th>
              <th>Медиа</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="dish in adminDishes" :key="dish.id">
              <td>{{ dish.name }}</td>
              <td>{{ restaurants.find((r) => r.id === dish.restaurant_id)?.name || "-" }}</td>
              <td>{{ dish.category?.name || "-" }}</td>
              <td>
                фото: {{ dish.photo_dish_path ? "да" : "нет" }},
                аудио: {{ dish.audio_path ? "да" : "нет" }},
                видео: {{ dish.video_path ? "да" : "нет" }}
              </td>
              <td>
                <div class="actions-row">
                  <button type="button" class="ghost" @click="startEditDish(dish)">Редактировать</button>
                  <button type="button" @click="deleteDish(dish.id)">Удалить</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
