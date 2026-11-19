import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "../api/client";

function mockFetch(response: Response | Error) {
  const fn = vi.fn(async () => {
    if (response instanceof Error) throw response;
    return response;
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("возвращает разобранный JSON", async () => {
    mockFetch(new Response(JSON.stringify({ mode: "mock", version: "1", keitaro_url: "" }), { status: 200 }));
    expect((await api.meta()).mode).toBe("mock");
  });

  it("отправляет тело запроса как JSON", async () => {
    const fn = mockFetch(new Response("{}", { status: 200 }));
    await api.addOffer(2, 11112);
    const [url, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/streams\/2\/offers$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ offer_id: 11112 });
  });

  it("превращает ответ-ошибку в ApiError с кодом, текстом и подробностями", async () => {
    mockFetch(
      new Response(JSON.stringify({ code: "MERGE_CONFLICT", message: "Есть спорные изменения", details: { conflicts: [] } }), { status: 409 }),
    );
    const error = (await api.push(2).catch((e) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.code).toBe("MERGE_CONFLICT");
    expect(error.message).toBe("Есть спорные изменения");
    expect(error.details).toEqual({ conflicts: [] });
  });

  it("при ответе без JSON даёт общее сообщение", async () => {
    mockFetch(new Response("<html>oops</html>", { status: 500 }));
    const error = (await api.campaigns().catch((e) => e)) as ApiError;
    expect(error.status).toBe(500);
    expect(error.code).toBe("HTTP_ERROR");
    expect(error.message).toContain("500");
  });

  it("при недоступном сервере даёт понятную ошибку", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    const error = (await api.campaigns().catch((e) => e)) as ApiError;
    expect(error.status).toBe(0);
    expect(error.code).toBe("NETWORK");
    expect(error.message).toContain("бэкенд");
  });

  it("кодирует поисковый запрос", async () => {
    const fn = mockFetch(new Response("[]", { status: 200 }));
    await api.searchOffers("a b&c");
    expect((fn.mock.calls[0] as unknown as [string])[0]).toContain("q=a%20b%26c");
  });
});
