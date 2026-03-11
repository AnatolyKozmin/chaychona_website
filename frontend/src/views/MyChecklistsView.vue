<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
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

const router = useRouter();
const route = useRoute();
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

const canSubmit = computed(() => {
  if (!activeChecklist.value) return false;
  for (const item of activeChecklist.value.items) {
    if (!checkedItems.value[item.id]) return false;
    if (item.requires_photo && !photoPaths.value[item.id]) return false;
  }
  return true;
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
      <div v-else class="checklist-grid">
        <div
          v-for="cl in checklists"
          :key="cl.id"
          class="checklist-card"
          @click="openChecklist(cl)"
        >
          <h3 class="checklist-card-title">{{ cl.title }}</h3>
          <p v-if="cl.shift_type_name" class="muted checklist-card-meta">{{ cl.shift_type_name }}</p>
          <p class="checklist-card-items">{{ cl.items.length }} пунктов</p>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="checklist-fill-header">
        <button type="button" class="ghost" @click="goBack">← Назад</button>
        <h3 style="margin: 0">{{ activeChecklist.title }}</h3>
      </div>

      <div class="checklist-fill-items">
        <div
          v-for="item in activeChecklist.items"
          :key="item.id"
          class="checklist-fill-item"
          :class="{ 'checklist-fill-item--checked': checkedItems[item.id] }"
        >
          <label class="checklist-fill-label">
            <input type="checkbox" v-model="checkedItems[item.id]" />
            <span class="checklist-fill-text">{{ item.title }}</span>
          </label>
          <div v-if="item.requires_photo" class="checklist-fill-photo">
            <input
              type="file"
              accept="image/*"
              capture="environment"
              @change="onPhotoUpload(item.id, $event)"
            />
            <img
              v-if="photoPaths[item.id]"
              :src="toMediaUrl(photoPaths[item.id]) || undefined"
              alt=""
              class="checklist-fill-preview"
            />
            <span v-else class="muted">Приложить фото</span>
          </div>
        </div>
      </div>

      <div class="checklist-fill-actions">
        <button type="button" :disabled="!canSubmit || submitting" @click="submitChecklist">
          {{ submitting ? "Отправка..." : "Завершить" }}
        </button>
      </div>
    </template>
  </section>
</template>
