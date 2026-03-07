import { createRouter, createWebHistory } from "vue-router";
import DashboardView from "../views/DashboardView.vue";
import LoginView from "../views/LoginView.vue";
import MyTestsView from "../views/MyTestsView.vue";
import StandardsView from "../views/StandardsView.vue";
import StandardsStudyView from "../views/StandardsStudyView.vue";
import TestsAnalyticsView from "../views/TestsAnalyticsView.vue";
import TastyNotebookView from "../views/TastyNotebookView.vue";
import TestsAdminView from "../views/TestsAdminView.vue";
import UsersView from "../views/UsersView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    { path: "/", name: "dashboard", component: DashboardView },
    { path: "/standards", name: "standards", component: StandardsView },
    { path: "/standards/:id", name: "standards-study", component: StandardsStudyView },
    { path: "/my-tests", name: "my-tests", component: MyTestsView },
    { path: "/tests-analytics", name: "tests-analytics", component: TestsAnalyticsView },
    { path: "/tasty-notebook", name: "tasty-notebook", component: TastyNotebookView },
    { path: "/tests", name: "tests", component: TestsAdminView },
    { path: "/users", name: "users", component: UsersView }
  ]
});

router.beforeEach((to) => {
  const isAuthenticated = Boolean(localStorage.getItem("access_token"));
  if (!isAuthenticated && to.name !== "login") {
    return { name: "login" };
  }
  if (isAuthenticated && to.name === "login") {
    return { name: "dashboard" };
  }
  return true;
});

export default router;
