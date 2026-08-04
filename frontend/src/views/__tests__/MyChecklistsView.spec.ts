import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import MyChecklistsView from "../MyChecklistsView.vue";
import { api } from "../../api/client";

const CHECKLISTS = [
  {
    id: 1,
    title: "Открытие смены",
    shift_type_name: "Утренняя",
    items: [
      { id: 10, title: "Проверить чистоту зала", requires_photo: true, sort_order: 1 },
      { id: 11, title: "Пересчитать разменную кассу", requires_photo: false, sort_order: 2 }
    ]
  },
  {
    id: 2,
    title: "Закрытие смены",
    shift_type_name: null,
    items: [{ id: 20, title: "Сдать выручку", requires_photo: false, sort_order: 1 }]
  }
];

async function mountView() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const wrapper = mount(MyChecklistsView, { global: { plugins: [pinia] } });
  await flushPromises();
  return wrapper;
}

function submitButton(wrapper: any) {
  return wrapper.find(".cl-submit").element as HTMLButtonElement;
}

describe("MyChecklistsView — чек-лист смены", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "get").mockResolvedValue({ data: CHECKLISTS } as any);
  });

  it("показывает назначенные чек-листы с числом пунктов", async () => {
    const wrapper = await mountView();
    const rows = wrapper.findAll(".cl-row");

    expect(rows).toHaveLength(2);
    expect(rows[0].text()).toContain("Открытие смены");
    expect(rows[0].text()).toContain("2 пункта");
    expect(rows[1].text()).toContain("1 пункт");
  });

  it("открывает чек-лист и даёт отмечать пункты нажатием на всю строку", async () => {
    const wrapper = await mountView();
    await wrapper.findAll(".cl-row")[0].trigger("click");

    const items = wrapper.findAll(".cl-item");
    expect(items).toHaveLength(2);
    expect(items[0].classes()).not.toContain("cl-item--checked");

    await items[0].find(".cl-item-hit").trigger("click");
    expect(wrapper.findAll(".cl-item")[0].classes()).toContain("cl-item--checked");
  });

  it("держит «Завершить» заблокированной и объясняет, чего не хватает", async () => {
    const wrapper = await mountView();
    await wrapper.findAll(".cl-row")[0].trigger("click");

    expect(submitButton(wrapper).disabled).toBe(true);
    expect(wrapper.find(".cl-foot-hint").text()).toBe("Отмечено 0 из 2");

    for (const item of wrapper.findAll(".cl-item-hit")) {
      await item.trigger("click");
    }

    // Всё отмечено, но у первого пункта обязательное фото ещё не приложено.
    expect(submitButton(wrapper).disabled).toBe(true);
    expect(wrapper.find(".cl-foot-hint").text()).toBe("Не приложено фото: 1");
  });

  it("разблокирует отправку после загрузки обязательного фото", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: { path: "uploads/x.jpg" } } as any);
    const wrapper = await mountView();
    await wrapper.findAll(".cl-row")[0].trigger("click");

    for (const item of wrapper.findAll(".cl-item-hit")) {
      await item.trigger("click");
    }

    const file = new File(["x"], "shot.jpg", { type: "image/jpeg" });
    const input = wrapper.find('.cl-photo input[type="file"]');
    Object.defineProperty(input.element, "files", { value: [file], configurable: true });
    await input.trigger("change");
    await flushPromises();

    expect(postSpy).toHaveBeenCalledWith("/checklists/media", expect.any(FormData));
    expect(submitButton(wrapper).disabled).toBe(false);
    expect(wrapper.find(".cl-foot-hint").exists()).toBe(false);
    expect(wrapper.find(".cl-photo").classes()).toContain("filled");
  });

  it("камеру открывает сразу задней камерой, а не галереей", async () => {
    const wrapper = await mountView();
    await wrapper.findAll(".cl-row")[0].trigger("click");

    const input = wrapper.find('.cl-photo input[type="file"]');
    expect(input.attributes("capture")).toBe("environment");
    expect(input.attributes("accept")).toBe("image/*");
  });

  it("отправляет отметки и возвращает к списку", async () => {
    vi.spyOn(api, "post").mockResolvedValue({ data: {} } as any);
    const wrapper = await mountView();
    await wrapper.findAll(".cl-row")[1].trigger("click");
    await wrapper.find(".cl-item-hit").trigger("click");

    expect(submitButton(wrapper).disabled).toBe(false);
    await wrapper.find(".cl-submit").trigger("click");
    await flushPromises();

    expect(api.post).toHaveBeenCalledWith("/checklists/my/2/complete", {
      item_completions: [{ checklist_item_id: 20, photo_path: null }]
    });
    expect(wrapper.findAll(".cl-row")).toHaveLength(2);
  });
});
