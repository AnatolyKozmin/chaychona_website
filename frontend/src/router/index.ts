import { createRouter, createWebHistory } from "vue-router";
import ChecklistsAdminView from "../views/ChecklistsAdminView.vue";
import DashboardView from "../views/DashboardView.vue";
import LoginView from "../views/LoginView.vue";
import MyChecklistsView from "../views/MyChecklistsView.vue";
import StatisticsView from "../views/StatisticsView.vue";
import MyTestsView from "../views/MyTestsView.vue";
import StandardsView from "../views/StandardsView.vue";
import StandardsStudyView from "../views/StandardsStudyView.vue";
import TestsAnalyticsView from "../views/TestsAnalyticsView.vue";
import TastyNotebookView from "../views/TastyNotebookView.vue";
import TestsAdminView from "../views/TestsAdminView.vue";
import UsersAccessView from "../views/UsersAccessView.vue";
import UsersPeopleView from "../views/UsersPeopleView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    { path: "/", name: "dashboard", component: DashboardView },
    { path: "/standards", name: "standards", component: StandardsView },
    { path: "/standards/:id", name: "standards-study", component: StandardsStudyView },
    { path: "/my-tests", name: "my-tests", component: MyTestsView },
    { path: "/my-checklists", name: "my-checklists", component: MyChecklistsView },
    { path: "/statistics", name: "statistics", component: StatisticsView },
    { path: "/tests-analytics", name: "tests-analytics", component: TestsAnalyticsView },
    { path: "/tasty-notebook", name: "tasty-notebook", component: TastyNotebookView },
    { path: "/tests", name: "tests", component: TestsAdminView },
    { path: "/checklists", name: "checklists", component: ChecklistsAdminView },
    { path: "/users", redirect: { name: "users-access" } },
    { path: "/users/access", name: "users-access", component: UsersAccessView },
    { path: "/users/people", name: "users-people", component: UsersPeopleView }
  ]
});

/** Живой ли JWT: парсим exp, а не просто проверяем наличие строки в localStorage. */
function tokenAlive(token: string | null): boolean {
  if (!token) {
    return false;
  }
  try {
    const payloadPart = token.split(".")[1];
    const payload = JSON.parse(atob(payloadPart.replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" && payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

router.beforeEach((to) => {
  const accessAlive = tokenAlive(localStorage.getItem("access_token"));
  const refreshAlive = tokenAlive(localStorage.getItem("refresh_token"));
  // Живой refresh-токен тоже считается сессией: интерцептор восстановит access сам.
  const hasSession = accessAlive || refreshAlive;
  if (!hasSession) {
    // Мёртвые токены не должны блокировать страницу входа — вычищаем их.
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }
  if (!hasSession && to.name !== "login") {
    return { name: "login" };
  }
  if (hasSession && to.name === "login") {
    return { name: "dashboard" };
  }
  return true;
});

export default router;
