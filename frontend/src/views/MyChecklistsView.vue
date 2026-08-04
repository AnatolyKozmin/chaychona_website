<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api } from "../api/client";

interface ChecklistItem {
  id: number;
  title: string;
  requires_photo: boolean;
  sort_order: number;
}

interface Checklist {
  id: number;
  title: string;
  shift_type_name: string | null;
  items: ChecklistItem[];
}

const loading = ref(false);
const submitting = ref(false);
const error = ref("");
const checklists = ref<Checklist[]>([]);
const activeChecklist = ref<Checklist | null>(null);
const checkedItems = ref<Record<number, boolean>>({});
const photoPaths = ref<Record<number, string>>({});

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

function toMediaUrl(path: string | null): string | null {
  if (!path) return null;
  const origin = new URL(baseUrl).origin;
  return `${origin}/api/v1/menu/media?path=${encodeURIComponent(path)}`;
}

async function loadChecklists() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<Checklist[]>("/checklists/my");
    checklists.value = data;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить чек-листы";
  } finally {
    loading.value = false;
  }
}

function openChecklist(cl: Checklist) {
  activeChecklist.value = cl;
  checkedItems.value = {};
  photoPaths.value = {};
  for (const item of cl.items) {
    checkedItems.value[item.id] = false;
  }
}

function goBack() {
  activeChecklist.value = null;
  checkedItems.value = {};
  photoPaths.value = {};
}

function itemWordForm(count: number): string {
  const lastTwo = count % 100;
  const last = count % 10;
  if (last === 1 && lastTwo !== 11) return "пункт";
  if (last >= 2 && last <= 4 && (lastTwo < 10 || lastTwo >= 20)) return "пункта";
  return "пунктов";
}

async function onPhotoUpload(itemId: number, event: Event) {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (!file) return;
  submitting.value = true;
  error.value = "";
  try {
    const formData = new FormData();
    formData.append("file", file);
    const { data } = await api.post<{ path: string }>("/checklists/media", formData);
    photoPaths.value[itemId] = data.path;
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось загрузить фото";
  } finally {
    submitting.value = false;
    target.value = "";
  }
}

function toggleItem(itemId: number) {
  checkedItems.value[itemId] = !checkedItems.value[itemId];
}

const checkedCount = computed(() => {
  if (!activeChecklist.value) return 0;
  return activeChecklist.value.items.filter((item) => checkedItems.value[item.id]).length;
});

const canSubmit = computed(() => {
  if (!activeChecklist.value) return false;
  for (const item of activeChecklist.value.items) {
    if (!checkedItems.value[item.id]) return false;
    if (item.requires_photo && !photoPaths.value[item.id]) return false;
  }
  return true;
});

/** Почему кнопка «Завершить» ещё не активна — иначе она просто серая без объяснений. */
const blockedReason = computed(() => {
  if (!activeChecklist.value || canSubmit.value) return "";
  const total = activeChecklist.value.items.length;
  if (checkedCount.value < total) {
    return `Отмечено ${checkedCount.value} из ${total}`;
  }
  const missing = activeChecklist.value.items.filter(
    (item) => item.requires_photo && !photoPaths.value[item.id]
  ).length;
  return missing > 0 ? `Не приложено фото: ${missing}` : "";
});

async function submitChecklist() {
  if (!activeChecklist.value || !canSubmit.value) return;
  submitting.value = true;
  error.value = "";
  try {
    const item_completions = activeChecklist.value.items.map((item) => ({
      checklist_item_id: item.id,
      photo_path: item.requires_photo ? photoPaths.value[item.id] : null
    }));
    await api.post(`/checklists/my/${activeChecklist.value.id}/complete`, { item_completions });
    goBack();
    await loadChecklists();
  } catch (e: any) {
    error.value = e?.response?.data?.detail ?? "Не удалось отправить";
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  await loadChecklists();
});
</script>

<template>
  <section class="card">
    <h2>Чек-листы</h2>
    <p class="page-desc">Пройдите чек-листы при открытии и закрытии смены. Отметьте выполненные пункты и приложите фото, где требуется.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>

    <template v-if="!activeChecklist">
      <p v-if="!loading && checklists.length === 0" class="muted">Для вас пока нет назначенных чек-листов.</p>
      <div v-else class="cl-list">
        <button
          v-for="cl in checklists"
          :key="cl.id"
          type="button"
          class="cl-row"
          @click="openChecklist(cl)"
        >
          <span class="cl-row-text">
            <strong>{{ cl.title }}</strong>
            <span class="cl-row-meta">
              <template v-if="cl.shift_type_name">{{ cl.shift_type_name }} · </template>
              {{ cl.items.length }} {{ itemWordForm(cl.items.length) }}
            </span>
          </span>
          <span class="cl-row-go" aria-hidden="true">→</span>
        </button>
      </div>
    </template>

    <template v-else>
      <div class="cl-head">
        <button type="button" class="ghost cl-back" @click="goBack">← Назад</button>
        <h3 class="cl-head-title">{{ activeChecklist.title }}</h3>
      </div>

      <div class="cl-items">
        <div
          v-for="item in activeChecklist.items"
          :key="item.id"
          class="cl-item"
          :class="{ 'cl-item--checked': checkedItems[item.id] }"
        >
          <button
            type="button"
            class="cl-item-hit"
            :aria-pressed="Boolean(checkedItems[item.id])"
            @click="toggleItem(item.id)"
          >
            <span class="cl-box" aria-hidden="true">✓</span>
            <span class="cl-item-text">{{ item.title }}</span>
          </button>

          <div v-if="item.requires_photo" class="cl-photo" :class="{ filled: photoPaths[item.id] }">
            <img
              v-if="photoPaths[item.id]"
              :src="toMediaUrl(photoPaths[item.id]) || undefined"
              alt="Приложенное фото"
              class="cl-photo-preview"
            />
            <span class="cl-photo-text">{{ photoPaths[item.id] ? "Фото приложено" : "Нужно фото" }}</span>
            <label class="cl-photo-btn">
              {{ photoPaths[item.id] ? "Переснять" : "Снять" }}
              <!-- capture=environment открывает сразу заднюю камеру, а не галерею -->
              <input
                type="file"
                accept="image/*"
                capture="environment"
                @change="onPhotoUpload(item.id, $event)"
              />
            </label>
          </div>
        </div>
      </div>

      <div class="cl-foot">
        <p v-if="blockedReason" class="cl-foot-hint">{{ blockedReason }}</p>
        <button type="button" class="cl-submit" :disabled="!canSubmit || submitting" @click="submitChecklist">
          {{ submitting ? "Отправка..." : "Завершить" }}
        </button>
      </div>
    </template>
  </section>
</template>
