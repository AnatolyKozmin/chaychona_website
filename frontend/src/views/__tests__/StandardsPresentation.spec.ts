import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createWebHistory } from "vue-router";
import StandardsView from "../StandardsView.vue";
import { api } from "../../api/client";
import { useAuthStore } from "../../stores/auth";

// Роутер нужен только чтобы useRouter() было что вернуть: переходы отсюда
// не проверяются.
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: { template: "<div />" } },
    { path: "/standards", name: "standards", component: { template: "<div />" } }
  ]
});

const SLIDES = [
  { image_path: "uploads/a.jpg", image_url: "/api/v1/menu/media?path=uploads/a.jpg", width: 1600, height: 900, sort_order: 0 },
  { image_path: "uploads/b.jpg", image_url: "/api/v1/menu/media?path=uploads/b.jpg", width: 1600, height: 900, sort_order: 1 },
  { image_path: "uploads/c.jpg", image_url: "/api/v1/menu/media?path=uploads/c.jpg", width: 1600, height: 900, sort_order: 2 }
];

let postCalls: Array<{ url: string; body: any }> = [];

function mockApi(postImpl?: (url: string, body?: any) => any) {
  vi.spyOn(api, "get").mockImplementation((url: string) => {
    if (url === "/courses/admin") return Promise.resolve({ data: [] } as any);
    if (url === "/users/catalog/restaurants-with-roles") return Promise.resolve({ data: [] } as any);
    if (url === "/tests") return Promise.resolve({ data: [] } as any);
    return Promise.resolve({ data: [] } as any);
  });
  vi.spyOn(api, "post").mockImplementation((url: string, body?: any) => {
    postCalls.push({ url, body });
    if (postImpl) {
      const result = postImpl(url, body);
      if (result) return Promise.resolve(result as any);
    }
    if (url === "/courses/admin/presentation") return Promise.resolve({ data: { slides: SLIDES } } as any);
    return Promise.resolve({ data: {} } as any);
  });
}

async function mountAsAdmin() {
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
  const wrapper = mount(StandardsView, {
    global: { plugins: [router, pinia], stubs: { AssignmentPicker: true } }
  });
  await flushPromises();
  return wrapper;
}

/** Переключить первый блок в презентацию. */
async function switchToDeck(wrapper: any) {
  const select = wrapper.findAll("select").find((item: any) => item.text().includes("Презентация"));
  await select.setValue("deck");
}

async function attachPdf(wrapper: any, name = "стандарты.pdf") {
  const input = wrapper.find('input[type="file"][accept="application/pdf,.pdf"]');
  const file = new File([new Uint8Array([1, 2, 3])], name, { type: "application/pdf" });
  Object.defineProperty(input.element, "files", { value: [file], configurable: true });
  await input.trigger("change");
  await flushPromises();
}

describe("StandardsView — залив презентации в блок", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    postCalls = [];
    mockApi();
  });

  it("по умолчанию блок текстовый, поля презентации скрыты", async () => {
    const wrapper = await mountAsAdmin();

    expect(wrapper.find('input[type="file"][accept="application/pdf,.pdf"]').exists()).toBe(false);
    expect(wrapper.find("textarea").exists()).toBe(true);
  });

  it("переключение в презентацию убирает поля текста и подблоков", async () => {
    const wrapper = await mountAsAdmin();
    await switchToDeck(wrapper);

    expect(wrapper.find('input[type="file"][accept="application/pdf,.pdf"]').exists()).toBe(true);
    expect(wrapper.find("textarea").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Подблоки");
    expect(wrapper.text()).toContain("Сохранить как");
  });

  it("залитый PDF превращается в миниатюры слайдов", async () => {
    const wrapper = await mountAsAdmin();
    await switchToDeck(wrapper);
    await attachPdf(wrapper);

    expect(postCalls.some((call) => call.url === "/courses/admin/presentation")).toBe(true);
    expect(wrapper.findAll(".std-slide")).toHaveLength(3);
    expect(wrapper.text()).toContain("Слайдов: 3");
  });

  it("лишний слайд можно выкинуть до сохранения", async () => {
    const wrapper = await mountAsAdmin();
    await switchToDeck(wrapper);
    await attachPdf(wrapper);

    await wrapper.findAll(".std-slide-del")[0].trigger("click");

    expect(wrapper.findAll(".std-slide")).toHaveLength(2);
    expect(wrapper.find(".std-slide img").attributes("src")).toContain("uploads/b.jpg");
  });

  it("слайды уезжают на сервер вместе со стандартом", async () => {
    const wrapper = await mountAsAdmin();
    await wrapper.find("input").setValue("Встреча гостя");
    await switchToDeck(wrapper);
    await attachPdf(wrapper);

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    const save = postCalls.find((call) => call.url === "/courses/admin");
    expect(save).toBeTruthy();
    expect(save!.body.blocks).toHaveLength(1);
    expect(save!.body.blocks[0].kind).toBe("deck");
    expect(save!.body.blocks[0].slides.map((slide: any) => slide.image_path)).toEqual([
      "uploads/a.jpg",
      "uploads/b.jpg",
      "uploads/c.jpg"
    ]);
    expect(save!.body.blocks[0].slides.map((slide: any) => slide.sort_order)).toEqual([0, 1, 2]);
  });

  it("ошибку разбора PDF показывает, а слайды не подставляет", async () => {
    mockApi((url: string) => {
      if (url === "/courses/admin/presentation") {
        return Promise.reject({ response: { data: { detail: "Файл повреждён или защищён паролем." } } });
      }
      return undefined;
    });
    const wrapper = await mountAsAdmin();
    await switchToDeck(wrapper);
    await attachPdf(wrapper);

    expect(wrapper.find(".error").text()).toContain("повреждён");
    expect(wrapper.findAll(".std-slide")).toHaveLength(0);
  });
});
