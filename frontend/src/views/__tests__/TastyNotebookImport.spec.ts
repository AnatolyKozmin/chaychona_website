import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import TastyNotebookView from "../TastyNotebookView.vue";
import { api } from "../../api/client";
import { useAuthStore } from "../../stores/auth";

const RESTAURANTS = [
  { id: "r1", name: "Жизнь Удалась" },
  { id: "r2", name: "Чайхона №1" }
];

const PREVIEW = {
  file_name: "реестр.zip",
  total_rows: 2,
  will_create: 1,
  will_update: 1,
  new_categories: ["Холодные закуски"],
  will_generate_images: 1,
  will_generate_audio: 2,
  will_generate_videos: 2,
  rows: [
    {
      row_number: 2,
      name: "Ассорти под крепкое",
      category: "Холодные закуски",
      ingredients: "Сельдь, грибы",
      description: "Набор под крепкие напитки",
      has_photo_dish: true,
      has_photo_ingredients: false,
      has_audio: false,
      exists: false
    },
    {
      row_number: 3,
      name: "Плов",
      category: "Горячее",
      ingredients: "рис, баранина",
      description: "Рассказ про плов",
      has_photo_dish: false,
      has_photo_ingredients: true,
      has_audio: true,
      exists: true
    }
  ]
};

const SESSION = {
  id: 7,
  file_name: "реестр.zip",
  restaurant_id: "r1",
  restaurant_name: "Жизнь Удалась",
  status: "running",
  error: null,
  total_rows: 2,
  created_dishes: 1,
  updated_dishes: 1,
  failed_rows: 0,
  created_at: "2026-08-19T10:00:00",
  finished_at: null,
  jobs_total: 4,
  jobs_pending: 3,
  jobs_processing: 1,
  jobs_done: 0,
  jobs_error: 0,
  rows: [],
  failed_jobs: []
};

function mockApi(postImpl?: (url: string, body?: any) => any) {
  vi.spyOn(api, "get").mockImplementation((url: string) => {
    if (url === "/menu/restaurants") return Promise.resolve({ data: RESTAURANTS } as any);
    if (url === "/users/catalog/restaurants") return Promise.resolve({ data: RESTAURANTS } as any);
    if (url === "/menu/feed") return Promise.resolve({ data: { total: 0, items: [] } } as any);
    if (url === "/menu/admin/dishes/import-jobs") {
      return Promise.resolve({
        data: { pending: 0, processing: 0, done: 0, error: 0, total: 0, jobs: [] }
      } as any);
    }
    return Promise.resolve({ data: [] } as any);
  });
  vi.spyOn(api, "post").mockImplementation((url: string, body?: any) => {
    if (postImpl) {
      const result = postImpl(url, body);
      if (result) return Promise.resolve(result as any);
    }
    return Promise.resolve({ data: {} } as any);
  });
}

async function mountAsSuperadmin() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const auth = useAuthStore();
  auth.user = {
    id: "u1",
    email: "owner@example.com",
    full_name: "System Owner",
    restaurant: null,
    role: "superadmin",
    job_title: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00"
  } as any;
  const wrapper = mount(TastyNotebookView, { global: { plugins: [pinia] } });
  await flushPromises();
  return wrapper;
}

function fakeFile(name = "реестр.zip") {
  return new File([new Uint8Array([1, 2, 3])], name, { type: "application/zip" });
}

/** Положить файл в форму так же, как это делает выбор через input. */
async function attachFile(wrapper: any, name?: string) {
  const input = wrapper.find(".file-drop-input");
  Object.defineProperty(input.element, "files", { value: [fakeFile(name)], configurable: true });
  await input.trigger("change");
}

describe("TastyNotebookView — залив меню файлом", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockApi();
  });

  it("показывает форму залива только суперадмину", async () => {
    mockApi();
    const pinia = createPinia();
    setActivePinia(pinia);
    const wrapper = mount(TastyNotebookView, { global: { plugins: [pinia] } });
    await flushPromises();

    expect(wrapper.text()).not.toContain("Загрузка меню файлом");
  });

  it("даёт суперадмину форму залива", async () => {
    const wrapper = await mountAsSuperadmin();

    expect(wrapper.text()).toContain("Загрузка меню файлом");
    expect(wrapper.find(".file-drop").exists()).toBe(true);
  });

  it("не отправляет файл без выбранного ресторана", async () => {
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);

    const buttons = wrapper.findAll("button");
    await buttons.find((b) => b.text() === "Загрузить")?.trigger("click");
    await flushPromises();

    expect(api.post).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Выберите ресторан-получатель");
  });

  it("не отправляет без файла, даже если ресторан выбран", async () => {
    const wrapper = await mountAsSuperadmin();
    const selects = wrapper.findAll(".filter-select");
    await selects[1].setValue("r1");

    await wrapper.findAll("button").find((b) => b.text() === "Загрузить")?.trigger("click");
    await flushPromises();

    expect(api.post).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Выберите файл реестра");
  });

  it("требует название, если выбрано «создать новый ресторан»", async () => {
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[0].setValue("new");

    await wrapper.findAll("button").find((b) => b.text() === "Загрузить")?.trigger("click");
    await flushPromises();

    expect(api.post).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Введите название нового ресторана");
  });

  it("шлёт название нового ресторана вместо идентификатора", async () => {
    const sent: any[] = [];
    mockApi((url, body) => {
      if (url === "/menu/admin/import") {
        sent.push(body);
        return { data: { dry_run: false, session: SESSION } };
      }
      return null;
    });
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[0].setValue("new");
    await wrapper.findAll(".filter-select")[1].setValue("Новая точка");

    await wrapper.findAll("button").find((b) => b.text() === "Загрузить")?.trigger("click");
    await flushPromises();

    const form = sent[0] as FormData;
    expect(form.get("restaurant_name")).toBe("Новая точка");
    expect(form.get("restaurant_id")).toBeNull();
  });

  it("показывает план проверки файла, ничего не заливая", async () => {
    mockApi((url, body) => {
      if (url === "/menu/admin/import") {
        expect((body as FormData).get("dry_run")).toBe("true");
        return { data: { dry_run: true, preview: PREVIEW } };
      }
      return null;
    });
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[1].setValue("r1");

    await wrapper.findAll("button").find((b) => b.text() === "Проверить файл")?.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Создать: 1");
    expect(wrapper.text()).toContain("Обновить: 1");
    expect(wrapper.text()).toContain("Холодные закуски");
    expect(wrapper.text()).toContain("Нарисовать картинок: 1");
  });

  it("отмечает в плане, какие строки уже есть в ресторане", async () => {
    mockApi((url) =>
      url === "/menu/admin/import" ? { data: { dry_run: true, preview: PREVIEW } } : null
    );
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[1].setValue("r1");
    await wrapper.findAll("button").find((b) => b.text() === "Проверить файл")?.trigger("click");
    await flushPromises();

    const rows = wrapper.findAll("tbody tr");
    expect(rows[0].text()).toContain("новое");
    expect(rows[1].text()).toContain("обновится");
  });

  it("после залива показывает прогресс генерации", async () => {
    mockApi((url) =>
      url === "/menu/admin/import" ? { data: { dry_run: false, session: SESSION } } : null
    );
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[1].setValue("r1");

    await wrapper.findAll("button").find((b) => b.text() === "Загрузить")?.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Залив #7");
    expect(wrapper.text()).toContain("Создано: 1");
    expect(wrapper.text()).toContain("В очереди: 3");
  });

  it("сбрасывает старый разбор при выборе другого файла", async () => {
    mockApi((url) =>
      url === "/menu/admin/import" ? { data: { dry_run: true, preview: PREVIEW } } : null
    );
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[1].setValue("r1");
    await wrapper.findAll("button").find((b) => b.text() === "Проверить файл")?.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Создать: 1");

    await attachFile(wrapper, "другой.xlsx");
    await flushPromises();

    // Иначе легко залить не то, что смотрел в предпросмотре.
    expect(wrapper.text()).not.toContain("Создать: 1");
    expect(wrapper.text()).toContain("другой.xlsx");
  });

  it("предлагает повтор, только когда есть упавшие задания", async () => {
    mockApi((url) =>
      url === "/menu/admin/import"
        ? { data: { dry_run: false, session: { ...SESSION, jobs_error: 2 } } }
        : null
    );
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[1].setValue("r1");
    await wrapper.findAll("button").find((b) => b.text() === "Загрузить")?.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Ошибки: 2");
    expect(wrapper.findAll("button").some((b) => b.text() === "Повторить упавшие")).toBe(true);
  });
  it("предупреждает, что озвучка запущена без ключа на сервере", async () => {
    const warning =
      "Генерация озвучки запущена, но ключ Yandex SpeechKit (YANDEX_TTS_API_KEY) на сервере не задан — эти задания упадут с ошибкой.";
    mockApi((url) => {
      if (url === "/menu/admin/import") {
        return { data: { dry_run: false, session: SESSION, warnings: [warning] } };
      }
      return null;
    });
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[1].setValue("r1");

    await wrapper.findAll("button").find((b) => b.text() === "Загрузить")?.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("YANDEX_TTS_API_KEY");
    // Залив при этом состоялся: блюда из файла на месте, упало бы только медиа.
    expect(wrapper.text()).toContain("Повторить упавшие");
  });

  it("показывает предупреждение уже на проверке файла", async () => {
    mockApi((url, body) => {
      if (url === "/menu/admin/import") {
        const dry = (body as FormData).get("dry_run") === "true";
        return {
          data: dry
            ? { dry_run: true, preview: PREVIEW, warnings: ["Картинки ингредиентов поставлены в очередь, но ключ Magnific (MAGNIFIC_API_KEY) на сервере не задан — эти задания упадут с ошибкой."] }
            : { dry_run: false, session: SESSION, warnings: [] }
        };
      }
      return null;
    });
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[1].setValue("r1");

    await wrapper.findAll("button").find((b) => b.text() === "Проверить файл")?.trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("MAGNIFIC_API_KEY");
  });

  it("убирает старое предупреждение при выборе другого файла", async () => {
    mockApi((url) => {
      if (url === "/menu/admin/import") {
        return { data: { dry_run: true, preview: PREVIEW, warnings: ["ключ Magnific (MAGNIFIC_API_KEY) на сервере не задан"] } };
      }
      return null;
    });
    const wrapper = await mountAsSuperadmin();
    await attachFile(wrapper);
    await wrapper.findAll(".filter-select")[1].setValue("r1");
    await wrapper.findAll("button").find((b) => b.text() === "Проверить файл")?.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("MAGNIFIC_API_KEY");

    await attachFile(wrapper, "другой-реестр.zip");

    expect(wrapper.text()).not.toContain("MAGNIFIC_API_KEY");
  });
});
