<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api/client";

let dragStartX = 0;
let dragStartY = 0;
let dragAxis: "x" | "y" | null = null;
// Свайп заканчивается кликом по картинке. Без этого флага любой листающий жест
// заодно открывал бы слайд на весь экран.
let suppressNextClick = false;

interface CourseSubBlock {
  id: number;
  heading: string | null;
  text: string;
  image_path: string | null;
  image_url: string | null;
  sort_order: number;
}

interface CourseSlide {
  id: number;
  image_path: string;
  image_url: string | null;
  width: number;
  height: number;
  sort_order: number;
}

interface CourseBlock {
  id: number;
  heading: string | null;
  text: string;
  image_path: string | null;
  image_url: string | null;
  sort_order: number;
  kind: string;
  slides: CourseSlide[];
  subblocks: CourseSubBlock[];
}

interface CoursePublic {
  id: number;
  title: string;
  description: string | null;
  restaurant_name: string | null;
  job_title_name: string | null;
  linked_test: { id: number; title: string } | null;
  blocks: CourseBlock[];
}

interface BlockProgress {
  block_id: number;
  title: string;
  sort_order: number;
  is_completed: boolean;
  completed_at: string | null;
  is_unlocked: boolean;
}

interface LinkedTestStats {
  test_id: number;
  test_title: string;
  attempts_count: number;
  best_score_percent: number | null;
  last_score_percent: number | null;
  last_attempt_at: string | null;
}

interface StudyResponse {
  course: CoursePublic;
  blocks_progress: BlockProgress[];
  progress_percent: number;
  linked_test_stats: LinkedTestStats | null;
}

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const study = ref<StudyResponse | null>(null);
const activeBlockIdx = ref(0);
const cardOffsetX = ref(0);
const isDragging = ref(false);

const activeSlideIdx = ref(0);
// Отметить блок изученным можно только долистав колоду до конца. Держим это
// по id блока, а не флагом: вернувшись на первый слайд, сотрудник не должен
// заново «зарабатывать» кнопку.
const deckFinished = ref<Record<number, boolean>>({});
const loadedSlides = ref<Record<number, boolean>>({});
const failedSlides = ref<Record<number, boolean>>({});
const zoomOpen = ref(false);
const zoomed = ref(false);
const zoomScroll = ref<HTMLElement | null>(null);

const activeBlock = computed(() => study.value?.course.blocks[activeBlockIdx.value] ?? null);
const activeProgress = computed(() => study.value?.blocks_progress[activeBlockIdx.value] ?? null);
const slides = computed(() => activeBlock.value?.slides ?? []);
const isDeck = computed(() => activeBlock.value?.kind === "deck" && slides.value.length > 0);
const activeSlide = computed(() => slides.value[activeSlideIdx.value] ?? null);

// Рисуем только соседей: колода бывает на сотню слайдов, а держать их все в DOM
// незачем. Три ячейки при этом уже загружены — свайп не упирается в загрузку и
// не моргает пустотой.
const visibleSlides = computed(() =>
  slides.value
    .map((slide, index) => ({ slide, index }))
    .filter(({ index }) => Math.abs(index - activeSlideIdx.value) <= 1)
);

const activeSlideLoaded = computed(() => Boolean(activeSlide.value && loadedSlides.value[activeSlide.value.id]));
const activeSlideFailed = computed(() => Boolean(activeSlide.value && failedSlides.value[activeSlide.value.id]));

const canGoPrev = computed(() => activeBlockIdx.value > 0);
const canGoNext = computed(() => {
  if (!study.value || !activeProgress.value) {
    return false;
  }
  if (activeBlockIdx.value >= study.value.course.blocks.length - 1) {
    return false;
  }
  return activeProgress.value.is_completed;
});

// Стрелки и свайп внутри колоды листают слайды, а на её краях — переходят
// к соседнему блоку. Для сотрудника это один и тот же жест.
const canStepBack = computed(() => (isDeck.value && activeSlideIdx.value > 0) || canGoPrev.value);
const canStepForward = computed(
  () => (isDeck.value && activeSlideIdx.value < slides.value.length - 1) || canGoNext.value
);

const deckReadToEnd = computed(() => Boolean(activeBlock.value && deckFinished.value[activeBlock.value.id]));
const canMarkUnderstood = computed(() => {
  if (!activeProgress.value || activeProgress.value.is_completed) return false;
  return isDeck.value ? deckReadToEnd.value : true;
});

// Высоту сцены задаём по первому слайду и больше не меняем: у колоды пропорции
// одинаковые, а если попадётся страница другого формата — она впишется полями,
// и лист не будет прыгать под пальцем при листании.
const slideAspectRatio = computed(() => {
  const first = slides.value[0];
  if (!first || !first.width || !first.height) return "16 / 9";
  return `${first.width} / ${first.height}`;
});

function toMediaUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
  const backendOrigin = new URL(baseUrl).origin;
  return `${backendOrigin}/api/v1/menu/media?path=${path}`;
}

function extractError(e: any, fallback: string): string {
  const detail = e?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item: any) => item?.msg || JSON.stringify(item)).join(" | ");
  }
  if (typeof detail === "string" && detail.trim()) return detail;
  return fallback;
}

function chooseInitialBlock() {
  if (!study.value) {
    activeBlockIdx.value = 0;
    return;
  }
  const firstPendingUnlocked = study.value.blocks_progress.findIndex((item) => item.is_unlocked && !item.is_completed);
  if (firstPendingUnlocked >= 0) {
    activeBlockIdx.value = firstPendingUnlocked;
    return;
  }
  const lastUnlocked = study.value.blocks_progress.map((item, idx) => ({ item, idx })).filter((x) => x.item.is_unlocked).pop();
  activeBlockIdx.value = lastUnlocked ? lastUnlocked.idx : 0;
}

async function loadStudy() {
  const courseId = Number(route.params.id);
  if (!courseId || Number.isNaN(courseId)) {
    error.value = "Некорректный ID курса";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.get<StudyResponse>(`/courses/my/${courseId}/study`);
    study.value = data;
    chooseInitialBlock();
  } catch (e: any) {
    error.value = extractError(e, "Не удалось загрузить обучение");
  } finally {
    loading.value = false;
  }
}

async function markUnderstood() {
  if (!study.value || !activeBlock.value) {
    return;
  }
  saving.value = true;
  error.value = "";
  try {
    const { data } = await api.post<StudyResponse>(
      `/courses/my/${study.value.course.id}/blocks/${activeBlock.value.id}/complete`
    );
    study.value = data;
    const currentCompleted = study.value.blocks_progress[activeBlockIdx.value]?.is_completed;
    if (currentCompleted && activeBlockIdx.value < study.value.course.blocks.length - 1) {
      activeBlockIdx.value += 1;
    }
  } catch (e: any) {
    error.value = extractError(e, "Не удалось отметить блок");
  } finally {
    saving.value = false;
  }
}

function goPrev() {
  if (!canGoPrev.value) return;
  activeBlockIdx.value -= 1;
}

function goNext() {
  if (!canGoNext.value) return;
  activeBlockIdx.value += 1;
}

function stepBack() {
  if (isDeck.value && activeSlideIdx.value > 0) {
    activeSlideIdx.value -= 1;
    return;
  }
  goPrev();
}

function stepForward() {
  if (isDeck.value && activeSlideIdx.value < slides.value.length - 1) {
    activeSlideIdx.value += 1;
    return;
  }
  goNext();
}

function goToSlide(index: number) {
  if (index < 0 || index >= slides.value.length) return;
  activeSlideIdx.value = index;
}

function onSlideLoad(slideId: number) {
  loadedSlides.value = { ...loadedSlides.value, [slideId]: true };
}

function onSlideError(slideId: number) {
  failedSlides.value = { ...failedSlides.value, [slideId]: true };
}

function cellStyle(index: number) {
  const shift = (index - activeSlideIdx.value) * 100;
  return { transform: `translateX(calc(${shift}% + ${cardOffsetX.value}px))` };
}

function onSlideClick() {
  if (suppressNextClick) return;
  openZoom();
}

function openZoom() {
  if (!activeSlide.value) return;
  zoomOpen.value = true;
  zoomed.value = false;
}

function closeZoom() {
  zoomOpen.value = false;
  zoomed.value = false;
}

/**
 * Увеличение с привязкой к точке тапа: сотрудник тычет в мелкую сноску внизу
 * слайда и должен увидеть именно её, а не левый верхний угол.
 */
async function toggleZoom(event: MouseEvent) {
  const image = event.currentTarget as HTMLImageElement;
  if (zoomed.value) {
    zoomed.value = false;
    return;
  }
  const rect = image.getBoundingClientRect();
  const fx = rect.width ? (event.clientX - rect.left) / rect.width : 0.5;
  const fy = rect.height ? (event.clientY - rect.top) / rect.height : 0.5;
  zoomed.value = true;
  await nextTick();
  const scroller = zoomScroll.value;
  if (!scroller) return;
  scroller.scrollLeft = fx * image.offsetWidth - scroller.clientWidth / 2;
  scroller.scrollTop = fy * image.offsetHeight - scroller.clientHeight / 2;
}

// Смена блока начинает колоду сначала.
watch(activeBlockIdx, () => {
  activeSlideIdx.value = 0;
  closeZoom();
});

// Долистали до последнего слайда — колода прочитана. immediate нужен для колод
// из одного слайда: там конец совпадает с началом.
watch(
  [activeBlockIdx, activeSlideIdx, isDeck],
  () => {
    const block = activeBlock.value;
    if (!block || !isDeck.value) return;
    if (activeSlideIdx.value >= block.slides.length - 1) {
      deckFinished.value = { ...deckFinished.value, [block.id]: true };
    }
  },
  { immediate: true }
);

// В полноэкранном режиме уровень увеличения сохраняем — читая колоду вплотную,
// сотрудник не должен зумить каждый слайд заново. Сбрасываем только прокрутку.
watch(activeSlideIdx, async () => {
  if (!zoomOpen.value) return;
  await nextTick();
  zoomScroll.value?.scrollTo?.(0, 0);
});

/*
 * Свайп между блоками. Захват указателя нужен потому, что палец постоянно
 * уходит за границы карточки; блокировка оси — чтобы вертикальный скролл
 * длинного текста не засчитывался как листание.
 */
const SWIPE_THRESHOLD_PX = 60;
const AXIS_LOCK_PX = 10;

function onPointerDown(event: PointerEvent) {
  isDragging.value = true;
  dragAxis = null;
  suppressNextClick = false;
  dragStartX = event.clientX;
  dragStartY = event.clientY;
  (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
}

function onPointerMove(event: PointerEvent) {
  if (!isDragging.value) return;
  const deltaX = event.clientX - dragStartX;
  const deltaY = event.clientY - dragStartY;
  if (dragAxis === null && Math.abs(deltaX) + Math.abs(deltaY) > AXIS_LOCK_PX) {
    dragAxis = Math.abs(deltaX) > Math.abs(deltaY) ? "x" : "y";
  }
  if (dragAxis === "x") {
    cardOffsetX.value = deltaX;
  }
}

function onPointerUp(event: PointerEvent) {
  if (!isDragging.value) return;
  isDragging.value = false;
  const deltaX = event.clientX - dragStartX;
  if (dragAxis === "x") {
    suppressNextClick = Math.abs(deltaX) > AXIS_LOCK_PX;
    if (Math.abs(deltaX) > SWIPE_THRESHOLD_PX) {
      if (deltaX < 0) {
        stepForward();
      } else {
        stepBack();
      }
    }
  }
  cardOffsetX.value = 0;
  dragAxis = null;
}

function onPointerCancel() {
  isDragging.value = false;
  dragAxis = null;
  cardOffsetX.value = 0;
}

function onKeydown(event: KeyboardEvent) {
  if (zoomOpen.value && event.key === "Escape") {
    closeZoom();
    return;
  }
  if (!isDeck.value) return;
  if (event.key === "ArrowRight") stepForward();
  if (event.key === "ArrowLeft") stepBack();
}

// Пока открыт слайд на весь экран, страница под ним скроллиться не должна:
// иначе после закрытия сотрудник оказывается не там, где был.
watch(zoomOpen, (open) => {
  if (typeof document === "undefined") return;
  document.body.style.overflow = open ? "hidden" : "";
});

onMounted(async () => {
  window.addEventListener("keydown", onKeydown);
  await loadStudy();
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
  if (typeof document !== "undefined") {
    document.body.style.overflow = "";
  }
});
</script>

<template>
  <section class="card standards-study-card">
    <div class="standards-study-header">
      <button type="button" class="ghost standards-back-btn" @click="router.push({ name: 'standards' })">
        ← Назад
      </button>
      <h2 class="standards-study-title">{{ study?.course?.title ?? "Стандарт" }}</h2>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading">Загрузка...</p>

    <template v-if="!loading && study">
      <div class="standards-progress-wrap standards-progress-wrap--study">
        <div class="standards-progress-bar standards-progress-bar--shimmer">
          <div
            class="standards-progress-fill"
            :style="{ width: `${study.progress_percent}%` }"
          />
        </div>
        <span class="standards-progress-text">{{ activeBlockIdx + 1 }} / {{ study.course.blocks.length }}</span>
      </div>

      <div
        v-if="activeBlock && activeProgress"
        class="tinder-card standards-tinder-card"
        :class="{ 'standards-tinder-card--deck': isDeck }"
        :style="isDeck ? {} : { transform: `translateX(${cardOffsetX}px) rotate(${cardOffsetX / 18}deg)` }"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerCancel"
      >
        <h3 class="standards-block-heading">{{ activeBlock.heading || activeProgress.title }}</h3>

        <!-- Презентация: сам PDF на телефон не отдаём, листаются готовые слайды. -->
        <div v-if="isDeck" class="deck">
          <div
            class="deck-stage"
            :class="{ 'deck-stage--dragging': isDragging }"
            :style="{ aspectRatio: slideAspectRatio }"
          >
            <div
              v-for="item in visibleSlides"
              :key="item.slide.id"
              class="deck-cell"
              :class="{ 'deck-cell--active': item.index === activeSlideIdx }"
              :style="cellStyle(item.index)"
            >
              <img
                :src="toMediaUrl(item.slide.image_path) || undefined"
                :alt="`Слайд ${item.index + 1} из ${slides.length}`"
                class="deck-slide"
                draggable="false"
                decoding="async"
                @load="onSlideLoad(item.slide.id)"
                @error="onSlideError(item.slide.id)"
                @click="onSlideClick"
              />
            </div>
            <div v-if="activeSlideFailed" class="deck-loading">
              Слайд не загрузился. Проверьте связь и обновите страницу.
            </div>
            <div v-else-if="!activeSlideLoaded" class="deck-loading">Загружаю слайд...</div>
          </div>

          <div class="deck-meta">
            <span class="deck-counter">{{ activeSlideIdx + 1 }} / {{ slides.length }}</span>
            <span class="deck-hint">Тап по слайду — на весь экран</span>
          </div>

          <div v-if="slides.length <= 15" class="deck-dots">
            <button
              v-for="(slide, index) in slides"
              :key="slide.id"
              type="button"
              class="deck-dot"
              :class="{ 'deck-dot--active': index === activeSlideIdx }"
              :aria-label="`Слайд ${index + 1}`"
              @click="goToSlide(index)"
            />
          </div>
          <div v-else class="deck-line">
            <div
              class="deck-line-fill"
              :style="{ width: `${((activeSlideIdx + 1) / slides.length) * 100}%` }"
            />
          </div>
        </div>

        <template v-else>
          <img
            v-if="activeBlock.image_path"
            :src="toMediaUrl(activeBlock.image_path) || undefined"
            alt=""
            class="standards-block-img"
          />
          <p class="long-text">{{ activeBlock.text }}</p>
          <div v-for="subblock in activeBlock.subblocks" :key="subblock.id" class="standards-subblock">
            <h4 v-if="subblock.heading" class="standards-subblock-heading">{{ subblock.heading }}</h4>
            <img
              v-if="subblock.image_path"
              :src="toMediaUrl(subblock.image_path) || undefined"
              alt=""
              class="standards-subblock-img"
            />
            <p class="long-text">{{ subblock.text }}</p>
          </div>
        </template>

        <div class="standards-block-actions">
          <button type="button" class="ghost" :disabled="!canStepBack" aria-label="Назад" @click="stepBack">←</button>
          <button
            type="button"
            class="standards-understood-btn"
            :disabled="saving || !canMarkUnderstood"
            @click="markUnderstood"
          >
            {{ activeProgress.is_completed ? "Изучено" : "Понял!" }}
          </button>
          <button type="button" class="ghost" :disabled="!canStepForward" aria-label="Вперёд" @click="stepForward">→</button>
        </div>
        <p v-if="isDeck && !deckReadToEnd && !activeProgress.is_completed" class="deck-lock-note">
          Долистайте презентацию до конца — тогда блок можно будет отметить изученным.
        </p>
      </div>

      <div v-if="study.linked_test_stats" class="standards-test-link">
        <button type="button" @click="router.push({ name: 'my-tests', query: { test: String(study.linked_test_stats.test_id) } })">
          Пройти тест: {{ study.linked_test_stats.test_title }}
        </button>
      </div>
    </template>
  </section>

  <!-- Слайд на весь экран — именно здесь его и читают, поэтому листание отсюда
       не выкидывает. Через Teleport, иначе overlay обрежется трансформом
       карточки и `overflow-x: clip` на html. -->
  <Teleport to="body">
    <div v-if="zoomOpen && activeSlide" class="deck-zoom" @click.self="closeZoom">
      <button type="button" class="deck-zoom-close" aria-label="Закрыть слайд" @click="closeZoom">✕</button>
      <div
        ref="zoomScroll"
        class="deck-zoom-scroll"
        :class="{ 'deck-zoom-scroll--zoomed': zoomed, 'deck-zoom-scroll--dragging': isDragging }"
        @click.self="closeZoom"
        @pointerdown="!zoomed && onPointerDown($event)"
        @pointermove="!zoomed && onPointerMove($event)"
        @pointerup="!zoomed && onPointerUp($event)"
        @pointercancel="onPointerCancel"
      >
        <img
          :src="toMediaUrl(activeSlide.image_path) || undefined"
          :alt="`Слайд ${activeSlideIdx + 1} из ${slides.length}`"
          class="deck-zoom-img"
          :class="{ 'deck-zoom-img--zoomed': zoomed }"
          draggable="false"
          :style="zoomed ? {} : { transform: `translateX(${cardOffsetX}px)` }"
          @click="toggleZoom"
        />
      </div>
      <div class="deck-zoom-nav">
        <button
          type="button"
          class="deck-zoom-step"
          :disabled="activeSlideIdx === 0"
          aria-label="Предыдущий слайд"
          @click="goToSlide(activeSlideIdx - 1)"
        >
          ←
        </button>
        <span class="deck-zoom-hint">
          {{ activeSlideIdx + 1 }} / {{ slides.length }} · {{ zoomed ? "тап — уменьшить" : "тап — увеличить" }}
        </span>
        <button
          type="button"
          class="deck-zoom-step"
          :disabled="activeSlideIdx >= slides.length - 1"
          aria-label="Следующий слайд"
          @click="goToSlide(activeSlideIdx + 1)"
        >
          →
        </button>
      </div>
    </div>
  </Teleport>
</template>
