<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { api } from "../api/client";
import { useBodyScrollLock } from "../composables/useBodyScrollLock";
import { analyzeIngredients, splitIngredients } from "../lib/allergens";
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
  /** Заполняет шеф-повар. Пусто — значит не заполнено, блок не показываем. */
  allergens: string | null;
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
  allergens: string | null;
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
/** Всё меню ресторана целиком: фильтруем и ищем на клиенте, чтобы поиск
 *  отзывался мгновенно и не бил в API на каждую букву. */
const dishes = ref<DishCard[]>([]);
const categories = ref<DishCategory[]>([]);
const publicRestaurants = ref<RestaurantItem[]>([]);
const selectedPublicRestaurant = ref<string>("");
const selectedCategory = ref(""); // "" — все разделы
const searchQuery = ref("");
const loading = ref(false);
const error = ref("");
/** Индекс открытой карточки внутри visibleDishes; null — открыта сетка. */
const openedDishIndex = ref<number | null>(null);
const showVideo = ref(false);
const cardOffsetX = ref(0);
let dragStartX = 0;
let dragStartY = 0;
let dragAxis: "x" | "y" | null = null;
let dragging = false;
const adminLoading = ref(false);
const adminError = ref("");
const adminSuccess = ref("");

interface VideoJobsSummary {
  pending: number;
  processing: number;
  done: number;
  error: number;
  total: number;
}
const videoBusy = ref(false);
const videoJobs = ref<VideoJobsSummary | null>(null);
let videoPollTimer: number | null = null;

interface ImportPreviewRow {
  row_number: number;
  name: string;
  category: string | null;
  ingredients: string | null;
  description: string | null;
  has_photo_dish: boolean;
  has_photo_ingredients: boolean;
  has_audio: boolean;
  exists: boolean;
}

interface ImportPreview {
  file_name: string;
  total_rows: number;
  will_create: number;
  will_update: number;
  new_categories: string[];
  will_generate_images: number;
  will_generate_audio: number;
  will_generate_videos: number;
  rows: ImportPreviewRow[];
}

interface ImportRow {
  row_number: number;
  dish_name: string | null;
  category_name: string | null;
  dish_id: number | null;
  status: string;
  error: string | null;
}

interface ImportJob {
  id: number;
  dish_id: number;
  dish_name: string | null;
  kind: string;
  status: string;
  error: string | null;
}

interface ImportSession {
  id: number;
  file_name: string;
  restaurant_id: string | null;
  restaurant_name: string | null;
  status: string;
  error: string | null;
  total_rows: number;
  created_dishes: number;
  updated_dishes: number;
  failed_rows: number;
  created_at: string;
  finished_at: string | null;
  jobs_total: number;
  jobs_pending: number;
  jobs_processing: number;
  jobs_done: number;
  jobs_error: number;
  rows?: ImportRow[];
  failed_jobs?: ImportJob[];
}

const importFile = ref<File | null>(null);
const importDragOver = ref(false);
const importFileInput = ref<HTMLInputElement | null>(null);
/** «existing» — залить в выбранный ресторан, «new» — создать по названию. */
const importRestaurantMode = ref<"existing" | "new">("existing");
const importRestaurantId = ref("");
const importNewRestaurantName = ref("");
const importGenerateImage = ref(true);
const importGenerateAudio = ref(true);
const importGenerateVideo = ref(true);
const importBusy = ref(false);
const importPreview = ref<ImportPreview | null>(null);
// Ключи провайдеров живут на сервере: узнать, что их нет, можно только из ответа.
const importWarnings = ref<string[]>([]);
const importSession = ref<ImportSession | null>(null);
const importSessions = ref<ImportSession[]>([]);
let importPollTimer: number | null = null;
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
  allergens: "",
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

/** Нормализация под поиск: регистр и «ё» не должны мешать найти блюдо. */
function normalize(value: string): string {
  return value.toLowerCase().replace(/ё/g, "е");
}

const visibleDishes = computed(() => {
  const terms = normalize(searchQuery.value).trim().split(/\s+/).filter(Boolean);
  return dishes.value.filter((dish) => {
    if (selectedCategory.value && dish.category?.name !== selectedCategory.value) {
      return false;
    }
    if (terms.length === 0) {
      return true;
    }
    // Ищем и по составу: гость спрашивает «а что с креветками?», а не название.
    const haystack = normalize(
      [dish.name, dish.ingredients ?? "", dish.description ?? "", dish.category?.name ?? ""].join(" ")
    );
    return terms.every((term) => haystack.includes(term));
  });
});

const categoryTabs = computed(() => {
  const counts = new Map<string, number>();
  for (const dish of dishes.value) {
    const name = dish.category?.name;
    if (name) {
      counts.set(name, (counts.get(name) ?? 0) + 1);
    }
  }
  return categories.value
    .filter((category) => counts.has(category.name))
    .map((category) => ({ name: category.name, count: counts.get(category.name) ?? 0 }));
});

const currentDish = computed(() =>
  openedDishIndex.value === null ? null : visibleDishes.value[openedDishIndex.value] ?? null
);
const currentIngredients = computed(() => splitIngredients(currentDish.value?.ingredients));
const currentAllergens = computed(() => parseAllergens(currentDish.value?.allergens));
const hasNext = computed(
  () => openedDishIndex.value !== null && openedDishIndex.value < visibleDishes.value.length - 1
);
const hasPrev = computed(() => openedDishIndex.value !== null && openedDishIndex.value > 0);
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

function dishWordForm(count: number): string {
  const lastTwo = count % 100;
  const last = count % 10;
  if (last === 1 && lastTwo !== 11) {
    return "блюдо";
  }
  if (last >= 2 && last <= 4 && (lastTwo < 10 || lastTwo >= 20)) {
    return "блюда";
  }
  return "блюд";
}

const allergenHint = ref("");

/**
 * Черновик по составу: подставляет найденные по ключевым словам аллергены,
 * чтобы шефу не набирать список с нуля. Это именно подсказка — результат
 * попадает в обычное поле, и шеф правит его до сохранения.
 */
function suggestAllergens() {
  const found = analyzeIngredients(dishForm.ingredients, dishForm.name);
  const suggested = found.isHot ? ["острое", ...found.allergens] : [...found.allergens];
  if (suggested.length === 0) {
    allergenHint.value = "По составу ничего не нашлось — проверьте вручную.";
    return;
  }
  const existing = parseAllergens(dishForm.allergens);
  const merged = [...existing];
  for (const item of suggested) {
    if (!merged.includes(item)) {
      merged.push(item);
    }
  }
  dishForm.allergens = merged.join(", ");
  allergenHint.value = "Подставлено по ключевым словам — проверьте и поправьте.";
}

/**
 * Аллергены блюда — то, что вручную заполнил шеф-повар, через запятую.
 * Пустая строка означает «не заполнено», а не «аллергенов нет», поэтому
 * официанту в этом случае вообще ничего не показываем.
 */
function parseAllergens(raw: string | null | undefined): string[] {
  if (!raw) {
    return [];
  }
  return raw
    .split(",")
    .map((part) => part.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

/** Пометки на плитке: не больше двух, иначе плитка перестаёт читаться. */
function dishTags(dish: DishCard): string[] {
  return parseAllergens(dish.allergens).slice(0, 2);
}

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

async function loadPublicRestaurants() {
  try {
    const { data } = await api.get<RestaurantItem[]>("/menu/restaurants");
    publicRestaurants.value = data;
    if (data.length > 0 && !data.some((r) => r.id === selectedPublicRestaurant.value)) {
      selectedPublicRestaurant.value = data[0].id;
    }
  } catch {
    publicRestaurants.value = [];
  }
}

function selectPublicRestaurant(restaurantId: string) {
  if (selectedPublicRestaurant.value === restaurantId) {
    return;
  }
  selectedPublicRestaurant.value = restaurantId;
  selectedCategory.value = "";
  searchQuery.value = "";
  openedDishIndex.value = null;
  void loadCategories();
  void loadDishes();
}

async function loadCategories() {
  try {
    const { data } = await api.get<DishCategory[]>("/menu/categories", {
      params: { restaurant_id: selectedPublicRestaurant.value || undefined }
    });
    categories.value = data;
  } catch {
    categories.value = [];
  }
}

const FEED_PAGE_SIZE = 100; // потолок limit на бэкенде
const FEED_MAX_PAGES = 20; // страховка от бесконечного цикла

/**
 * Тянет всё меню ресторана разом. Официант в зале ищет конкретное блюдо, и
 * запрос на сервер под каждую букву поиска был бы и медленнее, и бесполезнее:
 * меню целиком — это сотни записей, они спокойно живут в памяти и фильтруются
 * мгновенно.
 */
async function loadDishes() {
  loading.value = true;
  error.value = "";
  try {
    const collected: DishCard[] = [];
    for (let page = 0; page < FEED_MAX_PAGES; page += 1) {
      const { data } = await api.get<{ total: number; items: DishCard[] }>("/menu/feed", {
        params: {
          limit: FEED_PAGE_SIZE,
          offset: page * FEED_PAGE_SIZE,
          restaurant_id: selectedPublicRestaurant.value || undefined
        }
      });
      collected.push(...data.items);
      if (data.items.length < FEED_PAGE_SIZE || collected.length >= data.total) {
        break;
      }
    }
    dishes.value = collected;
    openedDishIndex.value = null;
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
  dishForm.allergens = "";
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
  dishForm.allergens = dish.allergens || "";
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

async function refreshVideoJobs() {
  try {
    const { data } = await api.get<VideoJobsSummary>("/menu/admin/dishes/import-jobs", {
      params: { limit: 1 }
    });
    videoJobs.value = {
      pending: data.pending,
      processing: data.processing,
      done: data.done,
      error: data.error,
      total: data.total
    };
    const active = data.pending + data.processing;
    if (active > 0) {
      if (videoPollTimer === null) {
        videoPollTimer = window.setInterval(refreshVideoJobs, 5000);
      }
    } else if (videoPollTimer !== null) {
      window.clearInterval(videoPollTimer);
      videoPollTimer = null;
      await loadAdminDishes(); // подтянуть проставленные video_path
    }
  } catch {
    // тихо: статус очереди не критичен
  }
}

function pickImportFile() {
  importFileInput.value?.click();
}

function setImportFile(file: File | null) {
  importFile.value = file;
  // Старый разбор относится к прошлому файлу — показывать его рядом с новым
  // именем нельзя, иначе легко залить не то, что смотрел.
  importPreview.value = null;
  importSession.value = null;
  importWarnings.value = [];
}

function onImportFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  setImportFile(input.files?.[0] ?? null);
}

function onImportDrop(event: DragEvent) {
  importDragOver.value = false;
  setImportFile(event.dataTransfer?.files?.[0] ?? null);
}

function buildImportForm(dryRun: boolean): FormData | null {
  if (!importFile.value) {
    adminError.value = "Выберите файл реестра (.xlsx или .zip)";
    return null;
  }
  const form = new FormData();
  form.append("file", importFile.value);
  if (importRestaurantMode.value === "new") {
    const name = importNewRestaurantName.value.trim();
    if (!name) {
      adminError.value = "Введите название нового ресторана";
      return null;
    }
    form.append("restaurant_name", name);
  } else {
    if (!importRestaurantId.value) {
      adminError.value = "Выберите ресторан-получатель";
      return null;
    }
    form.append("restaurant_id", importRestaurantId.value);
  }
  form.append("generate_image", String(importGenerateImage.value));
  form.append("generate_audio", String(importGenerateAudio.value));
  form.append("generate_video", String(importGenerateVideo.value));
  form.append("dry_run", String(dryRun));
  return form;
}

async function previewImport() {
  adminError.value = "";
  adminSuccess.value = "";
  const form = buildImportForm(true);
  if (!form) {
    return;
  }
  importBusy.value = true;
  try {
    const { data } = await api.post<{ preview: ImportPreview | null; warnings?: string[] }>(
      "/menu/admin/import",
      form,
    );
    importPreview.value = data.preview;
    importWarnings.value = data.warnings ?? [];
    importSession.value = null;
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось разобрать файл";
  } finally {
    importBusy.value = false;
  }
}

async function runImport() {
  adminError.value = "";
  adminSuccess.value = "";
  const form = buildImportForm(false);
  if (!form) {
    return;
  }
  importBusy.value = true;
  try {
    const { data } = await api.post<{ session: ImportSession | null; warnings?: string[] }>(
      "/menu/admin/import",
      form,
    );
    importSession.value = data.session;
    importWarnings.value = data.warnings ?? [];
    importPreview.value = null;
    adminSuccess.value = data.session
      ? `Залив #${data.session.id}: создано ${data.session.created_dishes}, обновлено ${data.session.updated_dishes}.`
      : "Залив выполнен";
    await Promise.all([loadAdminCategories(), loadAdminDishes(), loadDishes(), loadImportSessions()]);
    scheduleImportPoll();
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось залить файл";
  } finally {
    importBusy.value = false;
  }
}

async function loadImportSessions() {
  try {
    const { data } = await api.get<ImportSession[]>("/menu/admin/import", { params: { limit: 20 } });
    importSessions.value = data;
  } catch {
    // тихо: история заливов не критична для работы страницы
  }
}

/** Тянуть статус залива, пока его очередь не опустеет. */
function scheduleImportPoll() {
  const session = importSession.value;
  const active = session ? session.jobs_pending + session.jobs_processing : 0;
  if (!session || active === 0) {
    if (importPollTimer !== null) {
      window.clearInterval(importPollTimer);
      importPollTimer = null;
    }
    return;
  }
  if (importPollTimer === null) {
    importPollTimer = window.setInterval(refreshImportSession, 5000);
  }
}

async function refreshImportSession() {
  const current = importSession.value;
  if (!current) {
    return;
  }
  try {
    const { data } = await api.get<ImportSession>(`/menu/admin/import/${current.id}`);
    importSession.value = data;
    if (data.jobs_pending + data.jobs_processing === 0) {
      // Очередь опустела — подтянуть проставленные пути к медиа.
      await Promise.all([loadAdminDishes(), loadDishes()]);
    }
    scheduleImportPoll();
  } catch {
    // тихо: следующий тик попробует снова
  }
}

async function retryImportSession() {
  const current = importSession.value;
  if (!current) {
    return;
  }
  adminError.value = "";
  adminSuccess.value = "";
  importBusy.value = true;
  try {
    const { data } = await api.post<ImportSession>(`/menu/admin/import/${current.id}/retry`);
    importSession.value = data;
    adminSuccess.value = "Упавшие задания перезапущены";
    scheduleImportPoll();
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось перезапустить задания";
  } finally {
    importBusy.value = false;
  }
}

async function openImportSession(sessionId: number) {
  adminError.value = "";
  try {
    const { data } = await api.get<ImportSession>(`/menu/admin/import/${sessionId}`);
    importSession.value = data;
    importPreview.value = null;
    scheduleImportPoll();
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось открыть отчёт";
  }
}

async function generateAllVideos() {
  const ok = window.confirm(
    "Поставить генерацию видео для всех блюд с фото и аудио, но без видео?"
  );
  if (!ok) {
    return;
  }
  videoBusy.value = true;
  adminError.value = "";
  adminSuccess.value = "";
  try {
    const { data } = await api.post<{
      total_considered: number;
      enqueued: number;
      skipped_no_media: number;
      skipped_has_video: number;
      skipped_already_queued: number;
    }>("/menu/admin/dishes/generate-videos", {});
    adminSuccess.value =
      `В очередь: ${data.enqueued}. Пропущено — без медиа: ${data.skipped_no_media}, ` +
      `уже с видео: ${data.skipped_has_video}, уже в очереди: ${data.skipped_already_queued}.`;
    await refreshVideoJobs();
  } catch (e: any) {
    adminError.value = e?.response?.data?.detail ?? "Не удалось поставить генерацию видео";
  } finally {
    videoBusy.value = false;
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
      allergens: dishForm.allergens || null,
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
      const { data } = await api.put<{ video_job_queued?: boolean }>(
        `/menu/admin/dishes/${editingDishId.value}`,
        payload
      );
      if (data?.video_job_queued) {
        adminSuccess.value = "Позиция обновлена. Видео пересоздаётся под новую озвучку/фото…";
        await refreshVideoJobs();
      } else {
        adminSuccess.value = "Позиция обновлена";
      }
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

function selectCategory(categoryName: string) {
  selectedCategory.value = categoryName;
  openedDishIndex.value = null;
}

function openDish(index: number) {
  openedDishIndex.value = index;
  showVideo.value = false;
}

function closeDish() {
  openedDishIndex.value = null;
  showVideo.value = false;
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
  if (!hasNext.value || openedDishIndex.value === null) {
    return;
  }
  openedDishIndex.value += 1;
  showVideo.value = false;
}

function goPrev() {
  if (!hasPrev.value || openedDishIndex.value === null) {
    return;
  }
  openedDishIndex.value -= 1;
  showVideo.value = false;
}

/*
 * Свайп между блюдами. Три вещи, без которых жест на телефоне разваливается:
 * захват указателя (палец постоянно уходит за границы карточки), блокировка
 * оси (иначе диагональное движение при скролле засчитывается как листание) и
 * отсутствие обработчика на pointerleave, который обрывал жест на полпути.
 */
const SWIPE_THRESHOLD_PX = 60;
const AXIS_LOCK_PX = 10;

function onPointerDown(event: PointerEvent) {
  dragging = true;
  dragAxis = null;
  dragStartX = event.clientX;
  dragStartY = event.clientY;
  (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
}

function onPointerMove(event: PointerEvent) {
  if (!dragging) {
    return;
  }
  const deltaX = event.clientX - dragStartX;
  const deltaY = event.clientY - dragStartY;
  if (dragAxis === null && Math.abs(deltaX) + Math.abs(deltaY) > AXIS_LOCK_PX) {
    dragAxis = Math.abs(deltaX) > Math.abs(deltaY) ? "x" : "y";
  }
  if (dragAxis === "x") {
    cardOffsetX.value = deltaX;
  }
}

function onPointerUp(event: PointerEvent) {
  if (!dragging) {
    return;
  }
  dragging = false;
  const deltaX = event.clientX - dragStartX;
  if (dragAxis === "x" && Math.abs(deltaX) > SWIPE_THRESHOLD_PX) {
    if (deltaX < 0) {
      goNext();
    } else {
      goPrev();
    }
  }
  cardOffsetX.value = 0;
  dragAxis = null;
}

function onPointerCancel() {
  dragging = false;
  dragAxis = null;
  cardOffsetX.value = 0;
}

onMounted(() => {
  void loadPublicRestaurants().then(() => Promise.all([loadCategories(), loadDishes()]));
  if (isSuperadmin.value) {
    void loadRestaurants();
    void loadMenuBranches();
    void loadAdminCategories();
    void loadAdminDishes();
    void refreshVideoJobs();
    void loadImportSessions();
  }
});

onUnmounted(() => {
  if (videoPollTimer !== null) {
    window.clearInterval(videoPollTimer);
    videoPollTimer = null;
  }
  if (importPollTimer !== null) {
    window.clearInterval(importPollTimer);
    importPollTimer = null;
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
    void refreshVideoJobs();
    void loadImportSessions();
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

useBodyScrollLock(
  computed(
    () =>
      categoryModalOpen.value ||
      dishModalOpen.value ||
      branchModalOpen.value ||
      openedDishIndex.value !== null
  )
);
</script>

<template>
  <section class="card">
    <h2>Вкусная тетрадь</h2>

    <!-- Переключатель ресторанов -->
    <div v-if="publicRestaurants.length > 1" class="notebook-restaurant-tabs">
      <button
        v-for="restaurant in publicRestaurants"
        :key="restaurant.id"
        type="button"
        class="notebook-restaurant-tab"
        :class="{ active: restaurant.id === selectedPublicRestaurant }"
        @click="selectPublicRestaurant(restaurant.id)"
      >
        {{ restaurant.name }}
      </button>
    </div>

    <!-- Поиск: идёт и по составу, потому что гость спрашивает про продукт,
         а не про название блюда. -->
    <div class="nb-search">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-3.6-3.6" />
      </svg>
      <input
        v-model="searchQuery"
        type="search"
        placeholder="Блюдо или ингредиент…"
        autocomplete="off"
        aria-label="Поиск по блюдам и составу"
      />
      <button
        v-if="searchQuery"
        type="button"
        class="nb-search-clear"
        aria-label="Очистить поиск"
        @click="searchQuery = ''"
      >
        ✕
      </button>
    </div>

    <!-- Разделы меню -->
    <div v-if="categoryTabs.length > 0" class="nb-cats">
      <button
        type="button"
        class="nb-cat"
        :class="{ active: selectedCategory === '' }"
        @click="selectCategory('')"
      >
        Все<span class="nb-cat-n">{{ dishes.length }}</span>
      </button>
      <button
        v-for="tab in categoryTabs"
        :key="tab.name"
        type="button"
        class="nb-cat"
        :class="{ active: selectedCategory === tab.name }"
        @click="selectCategory(tab.name)"
      >
        {{ tab.name }}<span class="nb-cat-n">{{ tab.count }}</span>
      </button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>

    <template v-else>
      <p class="nb-count">{{ visibleDishes.length }} {{ dishWordForm(visibleDishes.length) }}</p>

      <div v-if="visibleDishes.length > 0" class="nb-grid">
        <button
          v-for="(dish, index) in visibleDishes"
          :key="dish.id"
          type="button"
          class="nb-tile"
          @click="openDish(index)"
        >
          <span class="nb-tile-media">
            <img
              v-if="dish.image_url"
              :src="toMediaUrl(dish.image_url) || undefined"
              :alt="''"
              loading="lazy"
              decoding="async"
            />
            <span v-else class="nb-tile-noimg">нет фото</span>
            <span class="nb-tile-marks">
              <span v-if="dish.audio_url" class="nb-mark" title="Есть озвучка">♪</span>
              <span v-if="dish.video_url" class="nb-mark" title="Есть видео">▶</span>
            </span>
          </span>
          <span class="nb-tile-body">
            <span class="nb-tile-name">{{ dish.name }}</span>
            <span v-if="dishTags(dish).length > 0" class="nb-tile-tags">
              <span v-for="tag in dishTags(dish)" :key="tag" class="nb-tag">{{ tag }}</span>
            </span>
            <span v-if="dish.category" class="nb-tile-cat">{{ dish.category.name }}</span>
          </span>
        </button>
      </div>

      <p v-else class="nb-empty">
        <strong>Ничего не нашлось</strong>
        Попробуйте часть названия или один ингредиент — например «креветки» или «камамбер».
      </p>
    </template>
  </section>

  <!-- Полноэкранная карточка блюда -->
  <div v-if="currentDish" class="nb-sheet" role="dialog" aria-modal="true" :aria-label="currentDish.name">
    <div
      class="nb-sheet-media"
      :class="{ 'is-video': showVideo }"
      :style="{ transform: `translateX(${cardOffsetX / 2.6}px)` }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerCancel"
    >
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
      <div v-else class="nb-sheet-noimg">Медиа недоступно</div>

      <div class="nb-sheet-top">
        <button type="button" class="nb-round-btn" aria-label="Назад к списку" @click="closeDish">←</button>
        <span class="nb-counter">{{ (openedDishIndex ?? 0) + 1 }} / {{ visibleDishes.length }}</span>
      </div>

      <div v-if="currentDish.video_url" class="nb-media-switch">
        <button type="button" :class="{ active: !showVideo }" @click="showVideo = false">Фото</button>
        <button type="button" :class="{ active: showVideo }" @click="showVideo = true">Видео</button>
      </div>
    </div>

    <div class="nb-sheet-body">
      <p v-if="currentDish.category" class="nb-sheet-cat">{{ currentDish.category.name }}</p>
      <h2 class="nb-sheet-name">{{ currentDish.name }}</h2>
      <p v-if="currentDish.price_rubles" class="nb-sheet-price">{{ currentDish.price_rubles }}</p>

      <template v-if="currentDish.description">
        <p class="nb-label">Как рассказать гостю</p>
        <div class="nb-pitch">
          <p>{{ currentDish.description }}</p>
          <audio
            v-if="currentDish.audio_url"
            :src="toMediaUrl(currentDish.audio_url) || undefined"
            controls
            preload="none"
            class="nb-audio"
          />
        </div>
      </template>

      <!-- Аллергены показываем, только если их заполнил шеф-повар. Пустое поле
           не значит «аллергенов нет», поэтому блока просто не будет. -->
      <template v-if="currentAllergens.length > 0">
        <p class="nb-label">Аллергены</p>
        <div class="nb-ings">
          <span v-for="tag in currentAllergens" :key="tag" class="nb-ing alrg">{{ tag }}</span>
        </div>
        <p class="nb-warn">
          Если гость спросит: в блюде есть <strong>{{ currentAllergens.join(", ") }}</strong>.
          При сомнении уточните на кухне.
        </p>
      </template>

      <template v-if="currentIngredients.length > 0">
        <p class="nb-label">Состав</p>
        <div class="nb-ings">
          <span
            v-for="(item, index) in currentIngredients"
            :key="`${item}-${index}`"
            class="nb-ing"
          >{{ item }}</span>
        </div>
      </template>

      <div class="nb-sheet-nav">
        <button type="button" class="ghost" :disabled="!hasPrev" @click="goPrev">Предыдущее</button>
        <button type="button" class="ghost" :disabled="!hasNext" @click="goNext">Следующее</button>
      </div>
    </div>
  </div>

  <section v-if="isSuperadmin" class="card">
    <h2>Заполнение вкусной тетради</h2>
    <p class="muted">Фото и аудио обязательны по процессу. Видео можно прикрепить отдельно (если уже собрано).</p>
    <p v-if="adminError" class="error">{{ adminError }}</p>
    <p v-if="adminSuccess" class="muted">{{ adminSuccess }}</p>

    <div class="card">
      <h3 style="margin: 0 0 8px 0">Загрузка меню файлом</h3>
      <p class="muted" style="margin: 0 0 14px 0">
        Реестр .xlsx с колонками «Раздел», «Блюдо», «Ингредиенты», «Текст озвучки» — или .zip,
        внутри которого лежит этот реестр вместе с папками фотографий. Чего в файле нет,
        сервер догенерирует сам: картинку ингредиентов, озвучку и видео.
      </p>

      <div
        class="file-drop"
        :class="{ 'file-drop--active': importDragOver, 'file-drop--filled': !!importFile }"
        @click="pickImportFile"
        @dragover.prevent="importDragOver = true"
        @dragleave="importDragOver = false"
        @drop.prevent="onImportDrop"
      >
        <input
          ref="importFileInput"
          type="file"
          accept=".xlsx,.xlsm,.zip"
          class="file-drop-input"
          @change="onImportFileChange"
        />
        <template v-if="importFile">
          <span class="file-drop-icon">📦</span>
          <span class="file-drop-name">{{ importFile.name }}</span>
          <span class="muted">Нажмите, чтобы выбрать другой файл</span>
        </template>
        <template v-else>
          <span class="file-drop-icon">⬆️</span>
          <span class="file-drop-name">Перетащите .xlsx или .zip сюда или нажмите для выбора</span>
        </template>
      </div>

      <div class="menu-toolbar" style="margin-top: 14px">
        <div class="menu-toolbar-filters">
          <div class="filter-row">
            <label class="filter-label">Ресторан</label>
            <select v-model="importRestaurantMode" class="filter-select">
              <option value="existing">Существующий</option>
              <option value="new">Создать новый</option>
            </select>
          </div>
          <div v-if="importRestaurantMode === 'existing'" class="filter-row">
            <label class="filter-label">Какой</label>
            <select v-model="importRestaurantId" class="filter-select">
              <option value="">Выберите…</option>
              <option v-for="item in restaurants" :key="item.id" :value="item.id">{{ item.name }}</option>
            </select>
          </div>
          <div v-else class="filter-row">
            <label class="filter-label">Название</label>
            <input
              v-model="importNewRestaurantName"
              type="text"
              class="filter-select"
              placeholder="например Жизнь Удалась"
            />
          </div>
        </div>
      </div>

      <div class="menu-stats-row" style="margin-top: 12px; flex-wrap: wrap">
        <label class="test-checkbox-label">
          <input v-model="importGenerateImage" type="checkbox" />
          Рисовать картинку ингредиентов
        </label>
        <label class="test-checkbox-label">
          <input v-model="importGenerateAudio" type="checkbox" />
          Озвучивать текст
        </label>
        <label class="test-checkbox-label">
          <input v-model="importGenerateVideo" type="checkbox" />
          Собирать видео
        </label>
      </div>
      <p class="muted" style="margin: 8px 0 0 0; font-size: 13px">
        Генерируем только то, чего нет в файле: если картинка или озвучка уже лежат в архиве,
        провайдеру за них не платим.
      </p>

      <div class="actions-row" style="margin-top: 14px">
        <button type="button" class="ghost" :disabled="importBusy" @click="previewImport">
          {{ importBusy ? "Читаем…" : "Проверить файл" }}
        </button>
        <button type="button" :disabled="importBusy" @click="runImport">
          {{ importBusy ? "Заливаем…" : "Загрузить" }}
        </button>
      </div>

      <!-- Ключи провайдеров прописаны в .env сервера, а кнопку жмут отсюда: без
           этого блока залив выглядел бы удачным, а генерация молча падала бы
           в очереди. Текст и медиа из файла заезжают в любом случае. -->
      <p v-for="warning in importWarnings" :key="warning" class="nb-warn">
        {{ warning }}
        <br />
        Пропишите ключ на сервере и нажмите «Повторить упавшие» у этого залива —
        текст и медиа из файла уже на месте.
      </p>

      <div v-if="importPreview" class="card" style="margin-top: 16px">
        <h4 style="margin: 0 0 10px 0">Что получится: {{ importPreview.file_name }}</h4>
        <div class="preview-summary">
          <span class="role-chip">Строк: {{ importPreview.total_rows }}</span>
          <span class="role-chip preview-summary-ok">Создать: {{ importPreview.will_create }}</span>
          <span class="role-chip">Обновить: {{ importPreview.will_update }}</span>
          <span v-if="importPreview.new_categories.length" class="role-chip">
            Новых разделов: {{ importPreview.new_categories.length }}
          </span>
        </div>
        <p v-if="importPreview.new_categories.length" class="muted" style="margin: 10px 0 0 0">
          Появятся разделы: {{ importPreview.new_categories.join(", ") }}
        </p>
        <div class="menu-stats-row" style="margin-top: 12px; flex-wrap: wrap">
          <span class="status-chip">Нарисовать картинок: {{ importPreview.will_generate_images }}</span>
          <span class="status-chip">Озвучить: {{ importPreview.will_generate_audio }}</span>
          <span class="status-chip">Собрать видео: {{ importPreview.will_generate_videos }}</span>
        </div>
        <div class="table-wrap" style="margin-top: 12px; max-height: 320px; overflow: auto">
          <table>
            <thead>
              <tr>
                <th>№</th>
                <th>Блюдо</th>
                <th>Раздел</th>
                <th>Что в файле</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in importPreview.rows" :key="row.row_number">
                <td>{{ row.row_number }}</td>
                <td>{{ row.name }}</td>
                <td>{{ row.category || "—" }}</td>
                <td>
                  <span v-if="row.has_photo_dish" class="status-chip status-chip-success">фото</span>
                  <span v-if="row.has_photo_ingredients" class="status-chip status-chip-success">ингредиенты</span>
                  <span v-if="row.has_audio" class="status-chip status-chip-success">озвучка</span>
                  <span
                    v-if="!row.has_photo_dish && !row.has_photo_ingredients && !row.has_audio"
                    class="status-chip status-chip-muted"
                  >
                    только текст
                  </span>
                </td>
                <td>
                  <span v-if="row.exists" class="status-chip">обновится</span>
                  <span v-else class="status-chip status-chip-success">новое</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="importSession" class="card" style="margin-top: 16px">
        <div class="category-actions-header">
          <h4 style="margin: 0">
            Залив #{{ importSession.id }} · {{ importSession.file_name }}
          </h4>
          <div class="category-actions-buttons">
            <button type="button" class="ghost" @click="refreshImportSession">Обновить</button>
            <button
              v-if="importSession.jobs_error > 0"
              type="button"
              class="ghost"
              :disabled="importBusy"
              @click="retryImportSession"
            >
              Повторить упавшие
            </button>
          </div>
        </div>
        <div class="menu-stats-row" style="margin-top: 12px; flex-wrap: wrap">
          <span class="status-chip status-chip-success">Создано: {{ importSession.created_dishes }}</span>
          <span class="status-chip">Обновлено: {{ importSession.updated_dishes }}</span>
          <span v-if="importSession.failed_rows > 0" class="status-chip status-chip-error">
            Строк с ошибкой: {{ importSession.failed_rows }}
          </span>
        </div>
        <div v-if="importSession.jobs_total > 0" class="menu-stats-row" style="margin-top: 10px; flex-wrap: wrap">
          <span class="status-chip">В очереди: {{ importSession.jobs_pending }}</span>
          <span class="status-chip">В работе: {{ importSession.jobs_processing }}</span>
          <span class="status-chip status-chip-success">Готово: {{ importSession.jobs_done }}</span>
          <span v-if="importSession.jobs_error > 0" class="status-chip status-chip-error">
            Ошибки: {{ importSession.jobs_error }}
          </span>
        </div>
        <div v-if="importSession.jobs_total > 0" class="test-progress-bar" style="margin-top: 12px">
          <div
            class="test-progress-fill"
            :style="{ width: Math.round((importSession.jobs_done / importSession.jobs_total) * 100) + '%' }"
          ></div>
        </div>

        <template v-if="importSession.failed_jobs && importSession.failed_jobs.length">
          <h4 style="margin: 16px 0 8px 0">Не сгенерировалось</h4>
          <div class="table-wrap" style="max-height: 240px; overflow: auto">
            <table>
              <thead>
                <tr>
                  <th>Блюдо</th>
                  <th>Стадия</th>
                  <th>Ошибка</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="job in importSession.failed_jobs" :key="job.id">
                  <td>{{ job.dish_name || job.dish_id }}</td>
                  <td>{{ job.kind }}</td>
                  <td class="long-text">{{ job.error }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>

        <template v-if="importSession.rows && importSession.rows.some((row) => row.status === 'error')">
          <h4 style="margin: 16px 0 8px 0">Строки, которые не заехали</h4>
          <div class="table-wrap" style="max-height: 240px; overflow: auto">
            <table>
              <thead>
                <tr>
                  <th>№</th>
                  <th>Блюдо</th>
                  <th>Ошибка</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="row in importSession.rows.filter((item) => item.status === 'error')"
                  :key="row.row_number"
                >
                  <td>{{ row.row_number }}</td>
                  <td>{{ row.dish_name || "—" }}</td>
                  <td class="long-text">{{ row.error }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </div>

      <template v-if="importSessions.length">
        <h4 style="margin: 18px 0 8px 0">История заливов</h4>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Файл</th>
                <th>Ресторан</th>
                <th>Итог</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in importSessions" :key="item.id">
                <td>{{ item.id }}</td>
                <td>{{ item.file_name }}</td>
                <td>{{ item.restaurant_name || "—" }}</td>
                <td>
                  +{{ item.created_dishes }} / ~{{ item.updated_dishes }}
                  <span v-if="item.jobs_error > 0" class="status-chip status-chip-error">
                    ошибок: {{ item.jobs_error }}
                  </span>
                </td>
                <td>
                  <button type="button" class="ghost" @click="openImportSession(item.id)">Отчёт</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </div>

    <div class="card">
      <div class="category-actions-header">
        <h3 style="margin: 0">Видео блюд</h3>
        <div class="category-actions-buttons">
          <button type="button" class="ghost" @click="refreshVideoJobs">Обновить статус</button>
          <button type="button" :disabled="videoBusy" @click="generateAllVideos">
            {{ videoBusy ? "Ставим в очередь…" : "Сгенерировать видео для всех" }}
          </button>
        </div>
      </div>
      <p class="muted" style="margin: 8px 0 0 0">
        Собирает видео на сервере из фото ингредиентов и озвучки для блюд, у которых видео ещё нет.
      </p>
      <div v-if="videoJobs && videoJobs.total > 0" class="menu-stats-row" style="margin-top: 12px">
        <span class="status-chip">В очереди: {{ videoJobs.pending }}</span>
        <span class="status-chip">В работе: {{ videoJobs.processing }}</span>
        <span class="status-chip status-chip-success">Готово: {{ videoJobs.done }}</span>
        <span v-if="videoJobs.error > 0" class="status-chip status-chip-error">Ошибки: {{ videoJobs.error }}</span>
      </div>
    </div>

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

        <label>Аллергены</label>
        <input v-model="dishForm.allergens" placeholder="через запятую: орехи, молочное" />
        <div class="dish-allergen-help">
          <p class="muted">
            Пусто — официанту блок аллергенов не показывается. Пустое поле не читается
            как «аллергенов нет», поэтому заполнять должен шеф-повар.
          </p>
          <button
            type="button"
            class="ghost"
            :disabled="!dishForm.ingredients"
            @click="suggestAllergens"
          >
            Подсказать по составу
          </button>
        </div>
        <p v-if="allergenHint" class="muted dish-allergen-hint">{{ allergenHint }}</p>

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
