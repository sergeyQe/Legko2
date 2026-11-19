import { describe, expect, it } from "vitest";

import { isGeoCode, parseOfferId, previewAlias, stateTag } from "../lib/format";
import { parseHash } from "../lib/route";
import { offer } from "./fixtures";

describe("parseOfferId", () => {
  it("берёт число из ввода", () => {
    expect(parseOfferId("11112")).toBe(11112);
    expect(parseOfferId("  11112  ")).toBe(11112);
    expect(parseOfferId("11112 Oxys [BE]")).toBe(11112);
  });
  it("не принимает названия и смешанный ввод", () => {
    expect(parseOfferId("Oxys")).toBeNull();
    expect(parseOfferId("11112abc")).toBeNull();
    expect(parseOfferId("")).toBeNull();
  });
});

describe("previewAlias", () => {
  it("транслитерирует и делает слаг", () => {
    expect(previewAlias("Тест кампания")).toBe("test-kampaniya");
    expect(previewAlias("  Лето!!! 2026 ")).toBe("leto-2026");
    expect(previewAlias("!!!")).toBe("");
  });
});

describe("isGeoCode", () => {
  it("принимает две латинские буквы", () => {
    expect(isGeoCode("AU")).toBe(true);
    expect(isGeoCode("au")).toBe(true);
    expect(isGeoCode("AUS")).toBe(false);
    expect(isGeoCode("1A")).toBe(false);
    expect(isGeoCode("ру")).toBe(false);
  });
});

describe("stateTag", () => {
  it("подписывает состояния оффера", () => {
    expect(stateTag(offer(1, 10)).text).toBe("");
    expect(stateTag(offer(1, 10, { state: "added" })).text).toBe("добавлен");
    expect(stateTag(offer(1, 0, { state: "removing" })).text).toBe("убирается");
    expect(stateTag(offer(1, 0, { state: "removed" })).text).toBe("удалён");
  });
});

describe("parseHash", () => {
  it("разбирает маршруты", () => {
    expect(parseHash("#/campaigns")).toEqual({ name: "campaigns" });
    expect(parseHash("#/campaign/12")).toEqual({ name: "campaign", id: 12 });
    expect(parseHash("#/create")).toEqual({ name: "create" });
  });
  it("неизвестное ведёт к списку кампаний", () => {
    expect(parseHash("")).toEqual({ name: "campaigns" });
    expect(parseHash("#/campaign/abc")).toEqual({ name: "campaigns" });
    expect(parseHash("#/что-то")).toEqual({ name: "campaigns" });
  });
});
