/** Переключатель темы: авто (по системе), светлая, тёмная. Выбор запоминается в браузере. */
import { useCallback, useEffect, useState } from "react";

export type ThemePref = "auto" | "light" | "dark";

const STORAGE_KEY = "legko2-theme";
const ORDER: ThemePref[] = ["auto", "light", "dark"];

function readStored(): ThemePref {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : "auto";
  } catch {
    return "auto"; // хранилище недоступно (приватный режим): работаем без запоминания
  }
}

/** Применяет тему к документу: для «авто» атрибут убирается и работает системная настройка. */
export function applyTheme(pref: ThemePref): void {
  const root = document.documentElement;
  if (pref === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", pref);
}

export function themeLabel(pref: ThemePref): string {
  return pref === "auto" ? "Тема: авто" : pref === "light" ? "Тема: светлая" : "Тема: тёмная";
}

/** Текущий выбор темы и функция переключения по кругу. */
export function useTheme(): [ThemePref, () => void] {
  const [pref, setPref] = useState<ThemePref>(readStored);

  useEffect(() => {
    applyTheme(pref);
    try {
      if (pref === "auto") localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, pref);
    } catch {
      /* без запоминания */
    }
  }, [pref]);

  const cycle = useCallback(() => setPref((current) => ORDER[(ORDER.indexOf(current) + 1) % ORDER.length]), []);
  return [pref, cycle];
}
