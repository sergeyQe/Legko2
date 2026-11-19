/** Мелкие функции форматирования и разбора ввода. */
import { ApiError } from "../api/client";
import type { Offer } from "../api/types";

/** Текст ошибки для показа пользователю. */
export function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Что-то пошло не так. Попробуйте ещё раз.";
}

/** Достаёт ID оффера из ввода: число, либо число в начале строки («11112 Название»). */
export function parseOfferId(input: string): number | null {
  const match = input.trim().match(/^(\d+)(?:\s|$)/);
  return match ? Number(match[1]) : null;
}

/** Активен ли оффер в черновике (участвует в полосе долей). */
export function isActive(offer: Offer): boolean {
  return offer.state === "published" || offer.state === "added";
}

/** Подпись состояния оффера (пусто для опубликованного). */
export function stateTag(offer: Offer): { text: string; kind: "add" | "rem" | "" } {
  switch (offer.state) {
    case "added":
      return { text: "добавлен", kind: "add" };
    case "removing":
      return { text: "убирается", kind: "rem" };
    case "removed":
      return { text: "удалён", kind: "" };
    default:
      return { text: "", kind: "" };
  }
}

/** Код страны: две латинские буквы. */
export function isGeoCode(value: string): boolean {
  return /^[A-Za-z]{2}$/.test(value);
}

/** Алиас из названия (та же идея, что на сервере; сервер строит окончательный). */
export function previewAlias(name: string): string {
  const map: Record<string, string> = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z", и: "i", й: "y", к: "k", л: "l",
    м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t", у: "u", ф: "f", х: "h", ц: "c", ч: "ch", ш: "sh",
    щ: "sch", ы: "y", э: "e", ю: "yu", я: "ya", ъ: "", ь: "",
  };
  const latin = [...name.toLowerCase()].map((ch) => (ch in map ? map[ch] : ch)).join("");
  return latin.replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60).replace(/-$/, "");
}

/** Названия стран для подсказки (не проверка: правильность кода проверяет Keitaro). */
export const COUNTRY_NAMES: Record<string, string> = {
  AU: "Австралия", AT: "Австрия", AZ: "Азербайджан", AR: "Аргентина", AM: "Армения", BY: "Беларусь", BE: "Бельгия",
  BG: "Болгария", BR: "Бразилия", GB: "Великобритания", HU: "Венгрия", VN: "Вьетнам", DE: "Германия", GR: "Греция",
  GE: "Грузия", DK: "Дания", EG: "Египет", IL: "Израиль", IN: "Индия", ID: "Индонезия", IE: "Ирландия", ES: "Испания",
  IT: "Италия", KZ: "Казахстан", CA: "Канада", KE: "Кения", CY: "Кипр", CN: "Китай", CO: "Колумбия", KR: "Корея",
  LV: "Латвия", LT: "Литва", MY: "Малайзия", MX: "Мексика", MD: "Молдова", NL: "Нидерланды", NZ: "Новая Зеландия",
  NG: "Нигерия", NO: "Норвегия", AE: "ОАЭ", PE: "Перу", PL: "Польша", PT: "Португалия", RU: "Россия", RO: "Румыния",
  SA: "Саудовская Аравия", RS: "Сербия", SG: "Сингапур", SK: "Словакия", SI: "Словения", US: "США", TH: "Таиланд",
  TR: "Турция", UZ: "Узбекистан", UA: "Украина", PH: "Филиппины", FI: "Финляндия", FR: "Франция", HR: "Хорватия",
  CZ: "Чехия", CL: "Чили", CH: "Швейцария", SE: "Швеция", EE: "Эстония", ZA: "ЮАР", JP: "Япония",
};
