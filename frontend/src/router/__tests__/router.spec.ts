import { describe, it, expect } from "vitest";
import { createRouter, createMemoryHistory } from "vue-router";
import DashboardView from "../../views/DashboardView.vue";
import LoginView from "../../views/LoginView.vue";
import StatisticsView from "../../views/StatisticsView.vue";
import StandardsView from "../../views/StandardsView.vue";
import MyTestsView from "../../views/MyTestsView.vue";
import TastyNotebookView from "../../views/TastyNotebookView.vue";

const routes = [
  { path: "/login", name: "login", component: LoginView },
  { path: "/", name: "dashboard", component: DashboardView },
  { path: "/standards", name: "standards", component: StandardsView },
  { path: "/my-tests", name: "my-tests", component: MyTestsView },
  { path: "/statistics", name: "statistics", component: StatisticsView },
  { path: "/tasty-notebook", name: "tasty-notebook", component: TastyNotebookView }
];

describe("Router", () => {
  it("has statistics route", () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes
    });
    const route = router.getRoutes().find((r) => r.name === "statistics");
    expect(route).toBeDefined();
    expect(route?.path).toBe("/statistics");
    expect(route?.name).toBe("statistics");
  });

  it("has dashboard as default route", () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes
    });
    const route = router.getRoutes().find((r) => r.name === "dashboard");
    expect(route).toBeDefined();
    expect(route?.path).toBe("/");
  });

  it("navigates to statistics", async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes
    });
    await router.push("/statistics");
    expect(router.currentRoute.value.name).toBe("statistics");
  });
});
