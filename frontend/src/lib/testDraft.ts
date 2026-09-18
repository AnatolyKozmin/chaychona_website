/**
 * Черновик прохождения теста в памяти телефона.
 *
 * Пока тест идёт, ответы живут только в памяти страницы. В проде этого
 * хватало, чтобы терять пройденные тесты целиком: телефон выгружает свёрнутую
 * вкладку, связь рвётся на отправке, сессия истекает посреди теста — и
 * сотрудник начинает заново. Черновик пишется после каждого ответа и
 * переживает перезагрузку, повторный вход и потерю сети.
 *
 * Черновик привязан к пользователю: телефон в зале бывает общим, и чужие
 * ответы подхватывать нельзя. Хранилище может быть недоступно (приватный
 * режим, запрет сайта) — тогда тест просто идёт без черновика, как раньше.
 */

export interface DraftOption {
  id: number;
  text: string;
  sort_order: number;
}

export interface DraftQuestion {
  id: number;
  text: string;
  question_type: "single" | "multiple";
  sort_order: number;
  options: DraftOption[];
}

export interface DraftTest {
  id: number;
  title: string;
  description: string | null;
  restaurant_name: string;
  job_title_name: string;
  questions: DraftQuestion[];
}

export interface TestDraft {
  version: 1;
  test: DraftTest;
  answers: Record<number, number[]>;
  questionIndex: number;
  startedAt: string | null;
  /** Номер попытки: повторная отправка с ним не создаст на сервере дубль. */
  clientAttemptId: string;
  savedAt: string;
}

// Дольше черновик не нужен: тест за это время могли поменять, а человек —
// давно пройти его заново.
const MAX_AGE_MS = 3 * 24 * 60 * 60 * 1000;

function storageKey(userId: string): string {
  return `test-draft:${userId}`;
}

export function newAttemptId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // Старые Safari без randomUUID: уникальности в пределах одного телефона хватает.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export function loadDraft(userId: string | null | undefined): TestDraft | null {
  if (!userId) {
    return null;
  }
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) {
      return null;
    }
    const draft = JSON.parse(raw) as TestDraft;
    const age = Date.now() - new Date(draft.savedAt).getTime();
    if (draft.version !== 1 || !draft.test?.questions?.length || !(age < MAX_AGE_MS)) {
      localStorage.removeItem(storageKey(userId));
      return null;
    }
    return draft;
  } catch {
    return null;
  }
}

export function saveDraft(userId: string | null | undefined, draft: Omit<TestDraft, "version" | "savedAt">): void {
  if (!userId) {
    return;
  }
  try {
    const payload: TestDraft = { ...draft, version: 1, savedAt: new Date().toISOString() };
    localStorage.setItem(storageKey(userId), JSON.stringify(payload));
  } catch {
    // Хранилище переполнено или запрещено — тест продолжится без черновика.
  }
}

export function clearDraft(userId: string | null | undefined): void {
  if (!userId) {
    return;
  }
  try {
    localStorage.removeItem(storageKey(userId));
  } catch {
    // нечего чистить
  }
}

export function answeredCount(draft: TestDraft): number {
  return draft.test.questions.filter((question) => (draft.answers[question.id] ?? []).length > 0).length;
}
