import { describe, it, expect, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "../DashboardView.vue";
import { useAuthStore } from "../../stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: "/", name: "dashboard", component: DashboardView }]
});

describe("DashboardView", () => {
  beforeEach(async () => {
    setActivePinia(createPinia());
    await router.push("/");
  });

  it("renders welcome section", () => {
    const pinia = createPinia();
    const wrapper = mount(DashboardView, {
      global: {
        plugins: [router, pinia],
        stubs: { RouterLink: true }
      }
    });

    expect(wrapper.text()).toContain("Добро пожаловать");
  });

  it("shows menu buttons for learner", () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const auth = useAuthStore();
    auth.user = {
      id: "1",
      email: "learner@test.com",
      full_name: "Test Learner",
      restaurant: "Test",
      role: "learner",
      job_title: "Waiter",
      is_active: true,
      created_at: "2024-01-01"
    };

    const RouterLinkStub = {
      template: "<a><slot /></a>",
      props: ["to"]
    };

    const wrapper = mount(DashboardView, {
      global: {
        plugins: [router, pinia],
        stubs: { RouterLink: RouterLinkStub }
      }
    });

    expect(wrapper.text()).toContain("Меню");
    expect(wrapper.text()).toContain("Стандарты");
    expect(wrapper.text()).toContain("Мои тесты");
    expect(wrapper.text()).toContain("Вкусная тетрадь");
    expect(wrapper.text()).toContain("Статистика");
  });
});
