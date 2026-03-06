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

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null);
  const loading = ref(false);
  const errorMessage = ref("");
  const accessToken = ref(localStorage.getItem("access_token"));
  const refreshToken = ref(localStorage.getItem("refresh_token"));

  const isAuthenticated = computed(() => Boolean(accessToken.value));
  const isAdmin = computed(() => user.value?.role === "admin" || user.value?.role === "superadmin");
  const isSuperadmin = computed(() => user.value?.role === "superadmin");

  async function register(payload: RegisterPayload) {
    loading.value = true;
    errorMessage.value = "";
    try {
      await api.post("/auth/register", payload);
    } catch (error: any) {
      errorMessage.value = error?.response?.data?.detail ?? "Ошибка регистрации";
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
      errorMessage.value = error?.response?.data?.detail ?? "Ошибка входа";
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
    } catch {
      logout();
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
