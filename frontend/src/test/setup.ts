import { vi } from "vitest";

// Mock localStorage for jsdom (some environments don't provide it)
const storage: Record<string, string> = {};
const localStorageMock = {
  getItem: vi.fn((key: string) => storage[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    storage[key] = value;
  }),
  removeItem: vi.fn((key: string) => {
    delete storage[key];
  }),
  clear: vi.fn(() => {
    Object.keys(storage).forEach((k) => delete storage[k]);
  }),
  get length() {
    return Object.keys(storage).length;
  },
  key: vi.fn((i: number) => Object.keys(storage)[i] ?? null)
};

if (typeof globalThis.localStorage === "undefined" || typeof globalThis.localStorage.getItem !== "function") {
  Object.defineProperty(globalThis, "localStorage", { value: localStorageMock, writable: true });
}
