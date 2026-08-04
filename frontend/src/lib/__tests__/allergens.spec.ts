import { describe, expect, it } from "vitest";
import { allergenSummary, analyzeIngredients, splitIngredients } from "../allergens";

describe("splitIngredients", () => {
  it("режет состав по запятым и чистит пробелы", () => {
    expect(splitIngredients("устрица,  лимон")).toEqual(["устрица", "лимон"]);
  });

  it("отбрасывает мусорные обрывки и пустую строку", () => {
    expect(splitIngredients(null)).toEqual([]);
    expect(splitIngredients("а, , лимон")).toEqual(["лимон"]);
  });
});

describe("analyzeIngredients", () => {
  it("находит молочное и орехи в реальном составе камамбера", () => {
    const result = analyzeIngredients(
      "Сыр камамбер, арахисовые лепестки, крамбл из лесных орехов, вишневая эспума",
      "Камамбер обжаренный в хрустящем миндале с вишневой эспумой"
    );
    expect(result.allergens).toEqual(["молочное", "орехи", "глютен"]);
    expect(result.items[0]).toEqual({ text: "Сыр камамбер", allergens: ["молочное"], isHot: false });
  });

  it("помечает ингредиент сразу двумя аллергенами, если он попадает в оба", () => {
    const [item] = analyzeIngredients("крамбл из лесных орехов").items;
    expect(item.allergens).toEqual(["орехи", "глютен"]);
  });

  it("находит морепродукты, а не рыбу, у креветок", () => {
    const result = analyzeIngredients("Креветки, салатная смесь, огурец");
    expect(result.allergens).toEqual(["морепродукты"]);
  });

  it("не путает сырую рыбу с сыром", () => {
    const result = analyzeIngredients("лосось сырой, лимон");
    expect(result.allergens).toEqual(["рыба"]);
    expect(result.allergens).not.toContain("молочное");
  });

  it("помечает острое по составу и по названию блюда", () => {
    expect(analyzeIngredients("Соус шрирача, майонез").isHot).toBe(true);
    expect(analyzeIngredients("курица, рис", "Острый цыплёнок").isHot).toBe(true);
    expect(analyzeIngredients("курица, рис", "Цыплёнок").isHot).toBe(false);
  });

  it("не повторяет один аллерген дважды", () => {
    const result = analyzeIngredients("сыр пармезан, сыр моцарелла, сливки");
    expect(result.allergens).toEqual(["молочное"]);
  });

  it("возвращает пустой разбор на пустом составе", () => {
    const result = analyzeIngredients("");
    expect(result.items).toEqual([]);
    expect(result.allergens).toEqual([]);
    expect(result.isHot).toBe(false);
  });
});

describe("allergenSummary", () => {
  it("ставит острое первым и перечисляет аллергены через запятую", () => {
    const result = analyzeIngredients("Соус шрирача, майонез, кунжут");
    expect(allergenSummary(result)).toBe("острое, соя, яйцо, кунжут");
  });

  it("отдаёт пустую строку, когда предупреждать не о чем", () => {
    expect(allergenSummary(analyzeIngredients("огурец, помидор"))).toBe("");
  });
});
