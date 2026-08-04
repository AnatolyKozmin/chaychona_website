/*
 * Service worker приложения обучения персонала.
 *
 * Задача — чтобы иконка с рабочего стола открывалась мгновенно и не показывала
 * «нет интернета» при слабом Wi-Fi в зале. Кэшируем только свою статику:
 * ответы API содержат персональные данные и живут под JWT, их не кэшируем никогда.
 *
 * Версию поднимать при изменении логики этого файла — старые кэши подчистятся сами.
 */
const VERSION = "v1";
const SHELL_CACHE = "shell-" + VERSION;
const ASSET_CACHE = "assets-" + VERSION;
const SHELL_URL = "/index.html";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.add(SHELL_URL))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => !key.endsWith(VERSION)).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  // Бэкенд живёт на другом origin — его ответы не трогаем вообще.
  if (url.origin !== self.location.origin) {
    return;
  }

  // Переходы по страницам: сеть вперёд, кэш как страховка. Так свежая сборка
  // подхватывается сразу, а без сети приложение всё равно открывается.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(SHELL_URL, copy));
          return response;
        })
        .catch(() =>
          caches.match(SHELL_URL).then(
            (cached) =>
              cached ||
              new Response("<h1>Нет соединения</h1>", {
                status: 503,
                headers: { "Content-Type": "text/html; charset=utf-8" }
              })
          )
        )
    );
    return;
  }

  // Хэшированная статика Vite и иконки: отдаём из кэша, обновляем в фоне.
  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.open(ASSET_CACHE).then((cache) =>
        cache.match(request).then((cached) => {
          const network = fetch(request)
            .then((response) => {
              if (response && response.ok) {
                cache.put(request, response.clone());
              }
              return response;
            })
            .catch(() => cached);
          return cached || network;
        })
      )
    );
  }
});
