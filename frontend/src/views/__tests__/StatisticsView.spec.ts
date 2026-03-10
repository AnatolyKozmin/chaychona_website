import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import StatisticsView from "../StatisticsView.vue";
import { api } from "../../api/client";

vi.mock("../../api/client", () => ({
  api: {
    get: vi.fn()
  }
}));

describe("StatisticsView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.mocked(api.get).mockImplementation((url: string) => {
      if (url === "/dashboard/me-overview") {
        return Promise.resolve({
          data: {
            total_trainings: 5,
            completed_trainings: 2,
            completed_percent: 40,
            total_tests: 3,
            attempts_count: 4,
            best_result: null,
            worst_result: null,
            attempts_last_7_days: 2,
            avg_score_last_7_days: 75,
            current_streak_days: 0,
            longest_streak_days: 2,
            daily_progress: []
          }
        } as any);
      }
      if (url === "/tests/my-attempts") {
        return Promise.resolve({ data: [] } as any);
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
  });

  it("renders statistics title", async () => {
    const wrapper = mount(StatisticsView, {
      global: {
        plugins: [createPinia()]
      }
    });

    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain("Статистика");
  });

  it("loads overview data on mount", async () => {
    mount(StatisticsView, {
      global: {
        plugins: [createPinia()]
      }
    });

    await new Promise((r) => setTimeout(r, 50));
    expect(api.get).toHaveBeenCalledWith("/dashboard/me-overview");
  });
});
