import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { answeredCount, clearDraft, loadDraft, newAttemptId, saveDraft, type DraftTest } from "../testDraft";

const test: DraftTest = {
  id: 55,
  title: "Управление сменой для менеджера",
  description: null,
  restaurant_name: "Жизнь Удалась",
  job_title_name: "Менеджер",
  questions: [
    { id: 1, text: "Первый", question_type: "single", sort_order: 0, options: [] },
    { id: 2, text: "Второй", question_type: "multiple", sort_order: 1, options: [] }
  ]
};

function draftFor(answers: Record<number, number[]> = { 1: [10] }) {
  return { test, answers, questionIndex: 1, startedAt: "2026-09-08T12:48:43Z", clientAttemptId: "attempt-1" };
}

describe("черновик теста", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("переживает перезагрузку страницы: ответы, место в тесте и номер попытки", () => {
    saveDraft("user-a", draftFor({ 1: [10], 2: [20, 21] }));

    const restored = loadDraft("user-a");

    expect(restored?.answers).toEqual({ 1: [10], 2: [20, 21] });
    expect(restored?.questionIndex).toBe(1);
    expect(restored?.clientAttemptId).toBe("attempt-1");
    expect(restored && answeredCount(restored)).toBe(2);
  });

  it("не отдаёт чужой черновик на общем телефоне", () => {
    saveDraft("user-a", draftFor());

    expect(loadDraft("user-b")).toBeNull();
  });

  it("без пользователя ничего не пишет и не читает", () => {
    saveDraft(null, draftFor());

    expect(localStorage.length).toBe(0);
    expect(loadDraft(null)).toBeNull();
  });

  it("выбрасывает черновик старше трёх дней — тест могли поменять", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-01T10:00:00Z"));
    saveDraft("user-a", draftFor());

    vi.setSystemTime(new Date("2026-09-05T10:00:00Z"));

    expect(loadDraft("user-a")).toBeNull();
    expect(localStorage.length).toBe(0);
  });

  it("стирается после успешной отправки", () => {
    saveDraft("user-a", draftFor());

    clearDraft("user-a");

    expect(loadDraft("user-a")).toBeNull();
  });

  it("битая запись не роняет страницу", () => {
    localStorage.setItem("test-draft:user-a", "{не json");

    expect(loadDraft("user-a")).toBeNull();
  });

  it("запрещённое хранилище не мешает проходить тест", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });

    expect(() => saveDraft("user-a", draftFor())).not.toThrow();
  });

  it("выдаёт разные номера попыток", () => {
    expect(newAttemptId()).not.toBe(newAttemptId());
  });
});
