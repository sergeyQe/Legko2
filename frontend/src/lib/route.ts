/** Простая маршрутизация по hash: #/campaigns, #/campaign/1, #/create. */
import { useCallback, useEffect, useState } from "react";

export type Route = { name: "campaigns" } | { name: "campaign"; id: number } | { name: "create" };

/** Разбирает hash адресной строки в маршрут (неизвестное ведёт к списку кампаний). */
export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "create") return { name: "create" };
  if (parts[0] === "campaign" && /^\d+$/.test(parts[1] ?? "")) return { name: "campaign", id: Number(parts[1]) };
  return { name: "campaigns" };
}

/** Текущий маршрут и функция перехода. */
export function useRoute(): [Route, (path: string) => void] {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));

  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);

  const navigate = useCallback((path: string) => {
    window.location.hash = path;
  }, []);

  return [route, navigate];
}
