import { beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import MyTestsView from "../MyTestsView.vue";
import { api } from "../../api/client";

const MY_TESTS = [
  {
    id: 7,
    title: "Стандарты сервиса в зале",
    description: "Цикл обслуживания от встречи до расчёта",
    restaurant_name: "Жизнь Удалась",
    job_title_name: "Официант"
  }
];

const TAKE_TEST = {
  id: 7,
  title: "Стандарты сервиса в зале",
  description: "Цикл обслуживания",
  restaurant_name: "Жизнь Удалась",
  job_title_name: "Официант",
  questions: [
    {
      id: 100,
      text: "За сколько секунд нужно встретить гостя?",
      question_type: "single",
      sort_order: 1,
      options: [
        { id: 1000, text: "30 секунд", sort_order: 1 },
        { id: 1001, text: "5 минут", sort_order: 2 }
      ]
    },
    {
      id: 101,
      text: "Что делать при возражении «дорого»?",
      question_type: "multiple",
      sort_order: 2,
      options: [
        { id: 1010, text: "Назвать состав и вес", sort_order: 1 },
        { id: 1011, text: "Предложить позицию дешевле", sort_order: 2 },
        { id: 1012, text: "Согласиться, что дорого", sort_order: 3 }
      ]
    }
  ]
};

const SUBMIT_RESULT = {
  attempt_id: 1,
  started_at: null,
  finished_at: "2026-08-04T10:00:00Z",
  duration_seconds: 42,
  total_questions: 2,
  correct_answers: 1,
  incorrect_answers: 1,
  results: [
    {
      question_id: 100,
      question_text: "За сколько секунд нужно встретить гостя?",
      correct_options: ["30 секунд"],
      selected_options: ["30 секунд"],
      is_correct: true
    },
    {
      question_id: 101,
      question_text: "Что делать при возражении «дорого»?",
      correct_options: ["Назвать состав и вес", "Предложить позицию дешевле"],
      selected_options: ["Согласиться, что дорого"],
      is_correct: false
    }
  ]
};

function mockApi() {
  vi.spyOn(api, "get").mockImplementation((url: string) => {
    if (url === "/tests/my") return Promise.resolve({ data: MY_TESTS } as any);
    if (url === "/tests/my-attempts") return Promise.resolve({ data: [] } as any);
    if (url === "/tests/7/take") return Promise.resolve({ data: TAKE_TEST } as any);
    return Promise.resolve({ data: [] } as any);
  });
}

async function startTest() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const wrapper = mount(MyTestsView, { global: { plugins: [pinia] } });
  await flushPromises();
  await wrapper.find(".test-card").trigger("click");
  await flushPromises();
  return wrapper;
}

function nextButton(wrapper: any) {
  return wrapper.find(".quiz-next");
}

describe("MyTestsView — прохождение теста", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockApi();
  });

  it("показывает ровно один вопрос за раз", async () => {
    const wrapper = await startTest();

    expect(wrapper.findAll(".quiz-card")).toHaveLength(1);
    expect(wrapper.find(".quiz-num").text()).toBe("Вопрос 1 из 2");
    expect(wrapper.find(".quiz-text").text()).toContain("встретить гостя");
    expect(wrapper.text()).not.toContain("возражении");
  });

  it("не пускает дальше, пока на вопрос не ответили", async () => {
    const wrapper = await startTest();
    expect((nextButton(wrapper).element as HTMLButtonElement).disabled).toBe(true);

    await wrapper.findAll(".quiz-option")[0].trigger("click");
    expect((nextButton(wrapper).element as HTMLButtonElement).disabled).toBe(false);
  });

  it("на первом вопросе не показывает кнопку «Назад»", async () => {
    const wrapper = await startTest();
    expect(wrapper.find(".quiz-back").exists()).toBe(false);

    await wrapper.findAll(".quiz-option")[0].trigger("click");
    await nextButton(wrapper).trigger("click");
    expect(wrapper.find(".quiz-back").exists()).toBe(true);
  });

  it("подсказывает формой ответа, сколько вариантов можно выбрать", async () => {
    const wrapper = await startTest();
    // Один ответ — круглая метка.
    expect(wrapper.find(".quiz-mark").classes()).not.toContain("multi");
    expect(wrapper.find(".quiz-hint").text()).toBe("Один правильный ответ");

    await wrapper.findAll(".quiz-option")[0].trigger("click");
    await nextButton(wrapper).trigger("click");

    expect(wrapper.find(".quiz-mark").classes()).toContain("multi");
    expect(wrapper.find(".quiz-hint").text()).toBe("Можно выбрать несколько ответов");
  });

  it("в вопросе с одним ответом выбор переключается, а не копится", async () => {
    const wrapper = await startTest();
    await wrapper.findAll(".quiz-option")[0].trigger("click");
    await wrapper.findAll(".quiz-option")[1].trigger("click");

    const selected = wrapper.findAll(".quiz-option.selected");
    expect(selected).toHaveLength(1);
    expect(selected[0].text()).toContain("5 минут");
  });

  it("в вопросе с несколькими ответами копит выбор и снимает повторным нажатием", async () => {
    const wrapper = await startTest();
    await wrapper.findAll(".quiz-option")[0].trigger("click");
    await nextButton(wrapper).trigger("click");

    await wrapper.findAll(".quiz-option")[0].trigger("click");
    await wrapper.findAll(".quiz-option")[1].trigger("click");
    expect(wrapper.findAll(".quiz-option.selected")).toHaveLength(2);

    await wrapper.findAll(".quiz-option")[1].trigger("click");
    expect(wrapper.findAll(".quiz-option.selected")).toHaveLength(1);
  });

  it("сохраняет ответ при возврате на предыдущий вопрос", async () => {
    const wrapper = await startTest();
    await wrapper.findAll(".quiz-option")[0].trigger("click");
    await nextButton(wrapper).trigger("click");
    await wrapper.find(".quiz-back").trigger("click");

    expect(wrapper.findAll(".quiz-option.selected")).toHaveLength(1);
    expect(wrapper.find(".quiz-option.selected").text()).toContain("30 секунд");
  });

  it("на последнем вопросе завершает тест и показывает разбор", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({ data: SUBMIT_RESULT } as any);
    const wrapper = await startTest();

    await wrapper.findAll(".quiz-option")[0].trigger("click");
    await nextButton(wrapper).trigger("click");
    expect(nextButton(wrapper).text()).toBe("Завершить тест");

    await wrapper.findAll(".quiz-option")[2].trigger("click");
    await nextButton(wrapper).trigger("click");
    await flushPromises();

    expect(postSpy).toHaveBeenCalledWith("/tests/7/submit", {
      answers: [
        { question_id: 100, option_ids: [1000] },
        { question_id: 101, option_ids: [1012] }
      ],
      started_at: expect.any(String)
    });

    expect(wrapper.find(".quiz-score").text()).toBe("50%");
    expect(wrapper.find(".quiz-score-note").text()).toContain("1 из 2 верно");
    expect(wrapper.findAll(".test-result-card")).toHaveLength(2);
    expect(wrapper.text()).toContain("Назвать состав и вес");
  });
});
