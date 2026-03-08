import { onUnmounted, watch, type ComputedRef, type Ref } from "vue";

let activeLocksCount = 0;

function syncBodyClass() {
  if (typeof document === "undefined") {
    return;
  }
  document.body.classList.toggle("body-scroll-lock", activeLocksCount > 0);
}

function acquireLock() {
  activeLocksCount += 1;
  syncBodyClass();
}

function releaseLock() {
  activeLocksCount = Math.max(0, activeLocksCount - 1);
  syncBodyClass();
}

export function useBodyScrollLock(source: Ref<boolean> | ComputedRef<boolean>) {
  let lockedByThisInstance = false;
  const stop = watch(
    source,
    (shouldLock) => {
      if (shouldLock && !lockedByThisInstance) {
        acquireLock();
        lockedByThisInstance = true;
        return;
      }
      if (!shouldLock && lockedByThisInstance) {
        releaseLock();
        lockedByThisInstance = false;
      }
    },
    { immediate: true }
  );

  onUnmounted(() => {
    stop();
    if (lockedByThisInstance) {
      releaseLock();
      lockedByThisInstance = false;
    }
  });
}
