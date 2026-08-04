import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import "./assets/main.css";

createApp(App).use(createPinia()).use(router).mount("#app");

// Service worker только в собранном приложении: в dev он перехватывал бы HMR.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js");
  });

  // Новый worker забирает управление -> перезагружаем страницу, чтобы код и
  // закэшированная статика не разъехались. Наличие контроллера проверяем
  // заранее: при самой первой установке он тоже появляется, но перезагружать
  // тогда нечего.
  const hadController = Boolean(navigator.serviceWorker.controller);
  let reloading = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (reloading || !hadController) {
      return;
    }
    reloading = true;
    window.location.reload();
  });
}
