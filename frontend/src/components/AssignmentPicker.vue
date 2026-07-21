<script setup lang="ts">
import { computed } from "vue";

interface CatalogItem {
  id: string;
  name: string;
}

interface RestaurantWithRoles {
  id: string;
  name: string;
  roles: CatalogItem[];
}

interface Assignment {
  restaurant_id: string;
  job_title_id: string;
}

const props = withDefaults(
  defineProps<{
    restaurants: RestaurantWithRoles[];
    modelValue: Assignment[];
    /** Существительное для подсказки: «будет доступен {{ noun }}». */
    noun?: string;
  }>(),
  { noun: "тест" }
);

const emit = defineEmits<{ (e: "update:modelValue", value: Assignment[]): void }>();

function isChecked(restaurantId: string, roleId: string): boolean {
  return props.modelValue.some((a) => a.restaurant_id === restaurantId && a.job_title_id === roleId);
}

function toggle(restaurantId: string, roleId: string) {
  const exists = isChecked(restaurantId, roleId);
  if (exists) {
    emit(
      "update:modelValue",
      props.modelValue.filter((a) => !(a.restaurant_id === restaurantId && a.job_title_id === roleId))
    );
  } else {
    emit("update:modelValue", [...props.modelValue, { restaurant_id: restaurantId, job_title_id: roleId }]);
  }
}

function allChecked(restaurant: RestaurantWithRoles): boolean {
  return restaurant.roles.length > 0 && restaurant.roles.every((role) => isChecked(restaurant.id, role.id));
}

function toggleAll(restaurant: RestaurantWithRoles) {
  const others = props.modelValue.filter((a) => a.restaurant_id !== restaurant.id);
  if (allChecked(restaurant)) {
    emit("update:modelValue", others);
  } else {
    const all = restaurant.roles.map((role) => ({ restaurant_id: restaurant.id, job_title_id: role.id }));
    emit("update:modelValue", [...others, ...all]);
  }
}

const selectedCount = computed(() => props.modelValue.length);
</script>

<template>
  <div class="assignment-picker">
    <p class="muted" style="margin: 0 0 8px 0">
      Отметьте галочками, в каких ресторанах и для каких ролей будет доступен {{ noun }}.
      <span v-if="selectedCount > 0">Выбрано: {{ selectedCount }}.</span>
    </p>
    <p v-if="restaurants.length === 0" class="muted">
      Сначала добавьте рестораны и роли.
    </p>
    <div v-for="restaurant in restaurants" :key="restaurant.id" class="ap-restaurant">
      <div class="ap-restaurant-head">
        <span class="ap-restaurant-name">{{ restaurant.name }}</span>
        <button
          v-if="restaurant.roles.length > 0"
          type="button"
          class="ghost ap-toggle-all"
          @click="toggleAll(restaurant)"
        >
          {{ allChecked(restaurant) ? "Снять все" : "Выбрать все" }}
        </button>
      </div>
      <div v-if="restaurant.roles.length === 0" class="muted ap-no-roles">
        Нет ролей — добавьте их в управлении ресторанами.
      </div>
      <div v-else class="ap-roles">
        <label v-for="role in restaurant.roles" :key="role.id" class="ap-role">
          <input
            type="checkbox"
            :checked="isChecked(restaurant.id, role.id)"
            @change="toggle(restaurant.id, role.id)"
          />
          <span>{{ role.name }}</span>
        </label>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ap-restaurant {
  border: 1px solid #e5ebf6;
  border-radius: 10px;
  padding: 10px 14px;
  background: #f8faff;
  margin-bottom: 10px;
}
.ap-restaurant-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.ap-restaurant-name {
  font-weight: 600;
  color: #1e293b;
}
.ap-toggle-all {
  font-size: 13px;
  padding: 2px 8px;
}
.ap-no-roles {
  font-size: 13px;
}
.ap-roles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}
.ap-role {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 14px;
  color: #2a4a8a;
}
.ap-role input {
  margin: 0;
}
</style>
