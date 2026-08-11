import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import TastyNotebookView from "../TastyNotebookView.vue";
import { api } from "../../api/client";

const RESTAURANTS = [{ id: "r1", name: "Жизнь Удалась" }];

const CATEGORIES = [
  { id: 1, name: "Горячие закуски", menu_type: null },
  { id: 2, name: "Салаты", menu_type: null }
];

const DISHES = [
  {
    id: 1,
    name: "Камамбер обжаренный в хрустящем миндале",
    ingredients: "Сыр камамбер, арахисовые лепестки, вишневая эспума",
    allergens: "молочное, орехи",
    description: "Обжаренный камамбер с вишнёвым соусом.",
    price: 890,
    price_rubles: "890 ₽",
    category: CATEGORIES[0],
    image_url: "/uploads/1.png",
    video_url: null,
    audio_url: "/uploads/1.mp3"
  },
  {
    id: 2,
    name: "Большой зеленый салат с креветками",
    ingredients: "Креветки, салатная смесь, огурец, гуакамоле из авокадо",
    allergens: null,
    description: "Креветки, микс салатов, авокадо.",
    price: 1200,
    price_rubles: "1 200 ₽",
    category: CATEGORIES[1],
    image_url: null,
    video_url: null,
    audio_url: null
  },
  {
    id: 3,
    name: "Хрустящий сыр с чесночным соусом",
    ingredients: "Сыр моцарелла, чеснок, майонез",
    allergens: "",
    description: "Хрустящие палочки сыра в панировке.",
    price: 640,
    price_rubles: "640 ₽",
    category: CATEGORIES[0],
    image_url: null,
    video_url: null,
    audio_url: null
  }
];

function mockApi() {
  vi.spyOn(api, "get").mockImplementation((url: string) => {
    if (url === "/menu/restaurants") {
      return Promise.resolve({ data: RESTAURANTS } as any);
    }
    if (url === "/menu/categories") {
      return Promise.resolve({ data: CATEGORIES } as any);
    }
    if (url === "/menu/feed") {
      return Promise.resolve({ data: { total: DISHES.length, items: DISHES } } as any);
    }
    return Promise.resolve({ data: [] } as any);
  });
}

async function mountView() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const wrapper = mount(TastyNotebookView, { global: { plugins: [pinia] } });
  await flushPromises();
  return wrapper;
}

describe("TastyNotebookView — экран официанта", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockApi();
  });

  it("показывает все блюда сеткой сразу, без промежуточного экрана категорий", async () => {
    const wrapper = await mountView();
    expect(wrapper.findAll(".nb-tile")).toHaveLength(3);
    expect(wrapper.text()).toContain("3 блюда");
  });

  it("ищет по составу, а не только по названию", async () => {
    const wrapper = await mountView();
    await wrapper.find(".nb-search input").setValue("креветки");

    const tiles = wrapper.findAll(".nb-tile");
    expect(tiles).toHaveLength(1);
    expect(tiles[0].text()).toContain("Большой зеленый салат");
  });

  it("не различает регистр и букву ё", async () => {
    const wrapper = await mountView();
    await wrapper.find(".nb-search input").setValue("ЗЕЛЕНЫЙ");
    expect(wrapper.findAll(".nb-tile")).toHaveLength(1);
  });

  it("фильтрует по разделу меню и считает блюда в каждом", async () => {
    const wrapper = await mountView();
    const tabs = wrapper.findAll(".nb-cat");
    const hot = tabs.find((tab) => tab.text().includes("Горячие закуски"));

    expect(hot?.text()).toContain("2");
    await hot?.trigger("click");
    expect(wrapper.findAll(".nb-tile")).toHaveLength(2);
  });

  it("объясняет пустой результат вместо молчаливой пустой сетки", async () => {
    const wrapper = await mountView();
    await wrapper.find(".nb-search input").setValue("вертолёт");

    expect(wrapper.findAll(".nb-tile")).toHaveLength(0);
    expect(wrapper.text()).toContain("Ничего не нашлось");
  });

  it("показывает аллергены только те, что заполнил шеф", async () => {
    const wrapper = await mountView();
    await wrapper.findAll(".nb-tile")[0].trigger("click");

    const sheet = wrapper.find(".nb-sheet");
    expect(sheet.exists()).toBe(true);
    expect(sheet.text()).toContain("Камамбер обжаренный");
    expect(sheet.text()).toContain("Как рассказать гостю");

    const flagged = sheet.findAll(".nb-ing.alrg").map((node) => node.text());
    expect(flagged).toEqual(["молочное", "орехи"]);
    expect(sheet.find(".nb-warn").text()).toContain("молочное, орехи");
  });

  it("не показывает блок аллергенов, когда поле не заполнено", async () => {
    const wrapper = await mountView();
    // Во втором блюде состав есть, а аллергены не заполнены (null).
    await wrapper.findAll(".nb-tile")[1].trigger("click");

    const sheet = wrapper.find(".nb-sheet");
    expect(sheet.text()).toContain("Большой зеленый салат");
    expect(sheet.find(".nb-warn").exists()).toBe(false);
    expect(sheet.findAll(".nb-ing.alrg")).toHaveLength(0);
    expect(sheet.text()).not.toContain("Аллергены");
    // Состав при этом на месте.
    expect(sheet.text()).toContain("Состав");
    expect(sheet.findAll(".nb-ing").length).toBeGreaterThan(0);
  });

  it("пустая строка аллергенов тоже считается незаполненной", async () => {
    const wrapper = await mountView();
    await wrapper.findAll(".nb-tile")[2].trigger("click");
    expect(wrapper.find(".nb-sheet .nb-warn").exists()).toBe(false);
  });

  it("метки на плитке берёт из заполненного поля, а не из состава", async () => {
    const wrapper = await mountView();
    const tiles = wrapper.findAll(".nb-tile");

    expect(tiles[0].findAll(".nb-tag").map((n) => n.text())).toEqual(["молочное", "орехи"]);
    // У салата с креветками аллергены не заполнены — меток быть не должно,
    // хотя по составу их можно было бы угадать.
    expect(tiles[1].findAll(".nb-tag")).toHaveLength(0);
  });

  it("листает блюда внутри текущего отбора и показывает позицию", async () => {
    const wrapper = await mountView();
    await wrapper.findAll(".nb-tile")[0].trigger("click");
    expect(wrapper.find(".nb-counter").text()).toBe("1 / 3");

    const [prev, next] = wrapper.findAll(".nb-sheet-nav button");
    expect((prev.element as HTMLButtonElement).disabled).toBe(true);

    await next.trigger("click");
    expect(wrapper.find(".nb-counter").text()).toBe("2 / 3");
    expect(wrapper.find(".nb-sheet-name").text()).toContain("Большой зеленый салат");
  });

  it("закрывает карточку и возвращает сетку", async () => {
    const wrapper = await mountView();
    await wrapper.findAll(".nb-tile")[0].trigger("click");
    await wrapper.find(".nb-round-btn").trigger("click");

    expect(wrapper.find(".nb-sheet").exists()).toBe(false);
    expect(wrapper.findAll(".nb-tile")).toHaveLength(3);
  });
});
