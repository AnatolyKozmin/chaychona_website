import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { createRouter, createWebHistory } from "vue-router";
import StandardsStudyView from "../StandardsStudyView.vue";
import { api } from "../../api/client";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/standards", name: "standards", component: { template: "<div />" } },
    { path: "/standards/:id", name: "standards-study", component: StandardsStudyView },
    { path: "/my-tests", name: "my-tests", component: { template: "<div />" } }
  ]
});

function slide(id: number) {
  return {
    id,
    image_path: `uploads/slide-${id}.jpg`,
    image_url: `/api/v1/menu/media?path=uploads/slide-${id}.jpg`,
    width: 1600,
    height: 900,
    sort_order: id - 1
  };
}

function deckBlock(slideCount: number) {
  return {
    id: 1,
    heading: "Встреча гостя",
    text: "",
    image_path: null,
    image_url: null,
    sort_order: 0,
    kind: "deck",
    slides: Array.from({ length: slideCount }, (_, idx) => slide(idx + 1)),
    subblocks: []
  };
}

const TEXT_BLOCK = {
  id: 2,
  heading: "Расчёт",
  text: "Счёт приносим в течение двух минут после просьбы.",
  image_path: null,
  image_url: null,
  sort_order: 1,
  kind: "text",
  slides: [],
  subblocks: []
};

function studyResponse(blocks: any[]) {
  return {
    course: {
      id: 5,
      title: "Стандарты сервиса",
      description: null,
      restaurant_name: "Жизнь Удалась",
      job_title_name: "Официант",
      linked_test: null,
      blocks
    },
    blocks_progress: blocks.map((block, idx) => ({
      block_id: block.id,
      title: block.heading,
      sort_order: idx,
      is_completed: false,
      completed_at: null,
      is_unlocked: idx === 0
    })),
    progress_percent: 0,
    linked_test_stats: null
  };
}

async function openStudy(blocks: any[]) {
  vi.spyOn(api, "get").mockResolvedValue({ data: studyResponse(blocks) } as any);
  const pinia = createPinia();
  setActivePinia(pinia);
  await router.push("/standards/5");
  await router.isReady();
  const wrapper = mount(StandardsStudyView, { global: { plugins: [router, pinia] } });
  await flushPromises();
  return wrapper;
}

function understoodButton(wrapper: any) {
  return wrapper.find(".standards-understood-btn").element as HTMLButtonElement;
}

// jsdom не даёт подменить clientX у события, созданного через trigger(),
// поэтому шлём указательные события руками.
function fire(element: Element, type: string, clientX: number) {
  element.dispatchEvent(new MouseEvent(type, { clientX, clientY: 200, bubbles: true }));
}

async function swipe(wrapper: any, deltaX: number) {
  const card = wrapper.find(".standards-tinder-card").element as Element;
  fire(card, "pointerdown", 300);
  fire(card, "pointermove", 300 + deltaX);
  fire(card, "pointerup", 300 + deltaX);
  await flushPromises();
}

describe("StandardsStudyView — презентация в блоке", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
    document.body.style.overflow = "";
  });

  it("показывает по одному слайду со счётчиком", async () => {
    const wrapper = await openStudy([deckBlock(3)]);

    expect(wrapper.findAll(".deck-cell--active")).toHaveLength(1);
    expect(wrapper.find(".deck-counter").text()).toBe("1 / 3");
    expect(wrapper.find(".deck-cell--active img").attributes("src")).toContain("uploads/slide-1.jpg");
  });

  it("держит в DOM только соседние слайды, а не всю колоду", async () => {
    const wrapper = await openStudy([deckBlock(40)]);

    // Первый слайд + следующий: свайп не упирается в загрузку, но и сотню
    // картинок в разметке мы не держим.
    expect(wrapper.findAll(".deck-cell")).toHaveLength(2);

    const forward = wrapper.findAll(".standards-block-actions button")[2];
    await forward.trigger("click");
    expect(wrapper.findAll(".deck-cell")).toHaveLength(3);
    expect(wrapper.find(".deck-cell--active img").attributes("src")).toContain("uploads/slide-2.jpg");
  });

  it("листающий жест не открывает слайд на весь экран", async () => {
    const wrapper = await openStudy([deckBlock(3)]);

    await swipe(wrapper, -120);
    await wrapper.find(".deck-cell--active img").trigger("click");

    expect(document.body.querySelector(".deck-zoom")).toBeNull();
    expect(wrapper.find(".deck-counter").text()).toBe("2 / 3");
  });

  it("не даёт отметить блок изученным, пока колода не долистана", async () => {
    const wrapper = await openStudy([deckBlock(3)]);
    expect(understoodButton(wrapper).disabled).toBe(true);
    expect(wrapper.find(".deck-lock-note").exists()).toBe(true);

    const forward = wrapper.findAll(".standards-block-actions button")[2];
    await forward.trigger("click");
    expect(understoodButton(wrapper).disabled).toBe(true);

    await forward.trigger("click");
    expect(wrapper.find(".deck-counter").text()).toBe("3 / 3");
    expect(understoodButton(wrapper).disabled).toBe(false);
    expect(wrapper.find(".deck-lock-note").exists()).toBe(false);
  });

  it("вернувшись к началу колоды, кнопку обратно не отбирает", async () => {
    const wrapper = await openStudy([deckBlock(2)]);
    const [back, , forward] = wrapper.findAll(".standards-block-actions button");

    await forward.trigger("click");
    expect(understoodButton(wrapper).disabled).toBe(false);

    await back.trigger("click");
    expect(wrapper.find(".deck-counter").text()).toBe("1 / 2");
    expect(understoodButton(wrapper).disabled).toBe(false);
  });

  it("колоду из одного слайда сразу можно отметить изученной", async () => {
    const wrapper = await openStudy([deckBlock(1)]);

    expect(wrapper.find(".deck-counter").text()).toBe("1 / 1");
    expect(understoodButton(wrapper).disabled).toBe(false);
  });

  it("свайп листает слайды, а не блоки", async () => {
    const wrapper = await openStudy([deckBlock(3), TEXT_BLOCK]);

    await swipe(wrapper, -120);
    expect(wrapper.find(".deck-counter").text()).toBe("2 / 3");
    // Блок прежний: заголовок не сменился на следующий.
    expect(wrapper.find(".standards-block-heading").text()).toBe("Встреча гостя");

    await swipe(wrapper, 120);
    expect(wrapper.find(".deck-counter").text()).toBe("1 / 3");
  });

  it("на краю колоды дальше листать некуда, пока блок не изучен", async () => {
    const wrapper = await openStudy([deckBlock(2), TEXT_BLOCK]);
    const forward = wrapper.findAll(".standards-block-actions button")[2];

    await forward.trigger("click");
    expect(wrapper.find(".deck-counter").text()).toBe("2 / 2");
    // Следующий блок откроется только после «Понял!» — как и для текстовых блоков.
    expect((forward.element as HTMLButtonElement).disabled).toBe(true);
  });

  it("тап по слайду открывает его на весь экран и закрывает крестиком", async () => {
    const wrapper = await openStudy([deckBlock(3)]);

    await wrapper.find(".deck-cell--active img").trigger("click");
    const overlay = document.body.querySelector(".deck-zoom");
    expect(overlay).not.toBeNull();
    expect(overlay?.querySelector(".deck-zoom-img")?.getAttribute("src")).toContain("uploads/slide-1.jpg");
    expect(document.body.style.overflow).toBe("hidden");

    (overlay?.querySelector(".deck-zoom-close") as HTMLButtonElement).click();
    await flushPromises();
    expect(document.body.querySelector(".deck-zoom")).toBeNull();
    expect(document.body.style.overflow).toBe("");
  });

  it("точки переключения показываются только у коротких колод", async () => {
    const short = await openStudy([deckBlock(5)]);
    expect(short.findAll(".deck-dot")).toHaveLength(5);
    expect(short.find(".deck-line").exists()).toBe(false);

    const long = await openStudy([deckBlock(20)]);
    expect(long.findAll(".deck-dot")).toHaveLength(0);
    expect(long.find(".deck-line").exists()).toBe(true);
  });

  it("текстовый блок работает как раньше", async () => {
    const wrapper = await openStudy([TEXT_BLOCK]);

    expect(wrapper.find(".deck-stage").exists()).toBe(false);
    expect(wrapper.text()).toContain("Счёт приносим");
    expect(understoodButton(wrapper).disabled).toBe(false);
  });
});
