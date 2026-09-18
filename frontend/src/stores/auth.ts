import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { api } from "../api/client";

type UserRole = "superadmin" | "admin" | "learner";

interface User {
  id: string;
  email: string;
  full_name: string;
  restaurant: string | null;
  role: UserRole;
  job_title: string | null;
  is_active: boolean;
  created_at: string;
}

interface LoginPayload {
  login: string;
  password: string;
}

interface RegisterPayload {
  first_name: string;
  last_name: string;
  restaurant: string;
  job_title: string;
  desired_login: string;
  password: string;
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

/** Текст ошибки для человека, а не для разработчика.
 *
 * FastAPI на ошибку валидации отдаёт `detail` массивом объектов — без разбора
 * на экране появлялось «[object Object]», и человек не понимал, что не так
 * с паролем. Нет ответа вовсе — значит, пропала связь, а не «неверный пароль».
 */
export function describeAuthError(error: any, fallback: string): string {
  if (!error?.response) {
    return "Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.";
  }
  const detail = error.response.data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const fields = detail.map((item: any) => String(item?.loc?.[item.loc.length - 1] ?? ""));
    if (fields.includes("password")) {
      return "Пароль должен быть не короче 6 символов.";
    }
    if (fields.includes("desired_login")) {
      return "Логин должен быть не короче 3 символов.";
    }
    if (fields.includes("first_name") || fields.includes("last_name")) {
      return "Имя и фамилия — не короче 2 букв.";
    }
    return "Проверьте, что все поля заполнены.";
  }
  return fallback;
}

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null);
  const loading = ref(false);
  const errorMessage = ref("");
  const accessToken = ref(localStorage.getItem("access_token"));
  const refreshToken = ref(localStorage.getItem("refresh_token"));

  const isAuthenticated = computed(() => Boolean(accessToken.value));
  const isAdmin = computed(() => user.value?.role === "admin" || user.value?.role === "superadmin");
  const isSuperadmin = computed(() => user.value?.role === "superadmin");

  const registerError = ref("");

  /** Регистрация сразу создаёт аккаунт и входит в него — без одобрения. */
  async function register(payload: RegisterPayload) {
    loading.value = true;
    registerError.value = "";
    try {
      const { data } = await api.post<TokenPair>("/auth/register", payload);
      setTokens(data.access_token, data.refresh_token);
      await fetchMe();
    } catch (error: any) {
      clearTokens();
      registerError.value = describeAuthError(error, "Не удалось зарегистрироваться");
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function login(payload: LoginPayload) {
    loading.value = true;
    errorMessage.value = "";
    try {
      const { data } = await api.post<TokenPair>("/auth/login", payload);
      setTokens(data.access_token, data.refresh_token);
      await fetchMe();
    } catch (error: any) {
      clearTokens();
      errorMessage.value = describeAuthError(error, "Не удалось войти");
      throw error;
    } finally {
      loading.value = false;
    }
  }

  async function fetchMe() {
    const { data } = await api.get<User>("/auth/me");
    user.value = data;
  }

  async function refresh() {
    const token = localStorage.getItem("refresh_token");
    if (!token) {
      logout();
      return;
    }
    try {
      const { data } = await api.post<TokenPair>("/auth/refresh", { refresh_token: token });
      setTokens(data.access_token, data.refresh_token);
      await fetchMe();
    } catch (error: any) {
      // Выходим, только если сервер отверг сессию. Нет связи — не повод
      // выкидывать человека из аккаунта посреди теста.
      const status = error?.response?.status;
      if (status === 401 || status === 403 || status === 422) {
        logout();
      }
    }
  }

  function logout() {
    clearTokens();
    user.value = null;
  }

  function clearTokens() {
    accessToken.value = null;
    refreshToken.value = null;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  function setTokens(newAccessToken: string, newRefreshToken: string) {
    accessToken.value = newAccessToken;
    refreshToken.value = newRefreshToken;
    localStorage.setItem("access_token", newAccessToken);
    localStorage.setItem("refresh_token", newRefreshToken);
  }

  return {
    user,
    loading,
    errorMessage,
    registerError,
    isAuthenticated,
    isAdmin,
    isSuperadmin,
    register,
    login,
    fetchMe,
    refresh,
    logout
  };
});
