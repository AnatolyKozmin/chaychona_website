/**
 * Разбор строки состава блюда на отдельные ингредиенты с пометкой аллергенов.
 *
 * Зачем: официанта у стола спрашивают «а орехи там есть?», и листать состав
 * глазами в этот момент неудобно. Разметка делается на клиенте по ключевым
 * словам — в базе отдельного поля аллергенов нет.
 *
 * ВАЖНО: это подсказка официанту, а не юридическая гарантия. Список ключевых
 * слов проверяется шеф-поваром; при сомнении официант обязан уточнить на кухне.
 */

export type AllergenKey =
  | "орехи"
  | "кунжут"
  | "молочное"
  | "яйцо"
  | "морепродукты"
  | "рыба"
  | "глютен"
  | "мёд"
  | "горчица"
  | "соя"
  | "сельдерей";

interface AllergenRule {
  key: AllergenKey;
  pattern: RegExp;
}

const ALLERGEN_RULES: AllergenRule[] = [
  { key: "орехи", pattern: /(орех|арахис|миндал|фундук|кешью|фисташ|пекан|кедров|прал)/i },
  { key: "кунжут", pattern: /(кунжут|тахин)/i },
  {
    key: "молочное",
    // «сыр» без «сырой/сырое/сырая/сырые» — иначе сырая рыба попадёт в молочное.
    pattern:
      /(молок|сливоч|сливк|сметан|творож|йогурт|сыр(?!ой|ое|ая|ые|ым|ого)|пармезан|моцарел|камамбер|качот|гауда|чеддер|маскарпоне|рикотт|фет[ая]|бри\b|дорблю)/i
  },
  { key: "яйцо", pattern: /(яйц|майонез|меренг|безе)/i },
  { key: "морепродукты", pattern: /(креветк|кальмар|устриц|мидии|краб|гребеш|осьминог|лангустин)/i },
  {
    key: "рыба",
    pattern: /(рыб|сельдь|сельди|лосос|сёмг|семг|тунец|форел|треск|анчоус|икра|дорад|сибас|угорь|палтус|берш)/i
  },
  {
    key: "глютен",
    pattern:
      /(мук[аи]|хлеб|лаваш|тест[оа]|панировк|сухар|паст[аы]|спагетт|эклер|темпур|крамбл|тост|булк|батон|пит[аы]|блин|вафл|бисквит|лапш|фокачч|бриош|ризо)/i
  },
  { key: "мёд", pattern: /(мёд|\bмед\b|медов)/i },
  { key: "горчица", pattern: /(горчиц|дижон)/i },
  { key: "соя", pattern: /(со[ея]вый|\bсоя\b|терияки|понзу|мисо|унаги|шрирач)/i },
  { key: "сельдерей", pattern: /(сельдере)/i }
];

const HOT_PATTERN = /(шрирач|чили|остр[ыаоъ]|табаско|аджик|халапень|огонек|огонёк|васаби|перец кайен)/i;

export interface IngredientMark {
  /** Текст ингредиента как он записан в карточке блюда. */
  text: string;
  /**
   * Все найденные аллергены. Именно массив, а не одно значение: «крамбл из
   * лесных орехов» — это и глютен, и орехи, и умолчать про второй опаснее,
   * чем показать оба.
   */
  allergens: AllergenKey[];
  /** Острый компонент. */
  isHot: boolean;
}

export interface IngredientBreakdown {
  items: IngredientMark[];
  /** Уникальные аллергены в порядке первого появления. */
  allergens: AllergenKey[];
  isHot: boolean;
}

/** Состав в базе — строка через запятую; иногда встречается «а\б» и точка с запятой. */
export function splitIngredients(raw: string | null | undefined): string[] {
  if (!raw) {
    return [];
  }
  return raw
    .split(/[,;]|\s\/\s/)
    .map((part) => part.replace(/\s+/g, " ").trim())
    .filter((part) => part.length > 1 && part.length < 70);
}

export function analyzeIngredients(
  raw: string | null | undefined,
  dishName = ""
): IngredientBreakdown {
  const allergens: AllergenKey[] = [];
  const items = splitIngredients(raw).map<IngredientMark>((text) => {
    const found = ALLERGEN_RULES.filter((rule) => rule.pattern.test(text)).map((rule) => rule.key);
    for (const key of found) {
      if (!allergens.includes(key)) {
        allergens.push(key);
      }
    }
    return { text, allergens: found, isHot: HOT_PATTERN.test(text) };
  });

  return {
    items,
    allergens,
    isHot: HOT_PATTERN.test(raw ?? "") || HOT_PATTERN.test(dishName)
  };
}

/** Готовая фраза для ответа гостю: «в блюде есть острое, орехи, молочное». */
export function allergenSummary(breakdown: IngredientBreakdown): string {
  const parts = breakdown.isHot ? ["острое", ...breakdown.allergens] : [...breakdown.allergens];
  return parts.join(", ");
}
