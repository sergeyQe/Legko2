/** Клиент API legko2: единая обработка ошибок формата {code, message, details}. */
import type {
  Campaign,
  CampaignSummary,
  CreateCampaignBody,
  CreateReport,
  ExternalChangeBody,
  FailureBody,
  Meta,
  OfferSearchResult,
  Preview,
  References,
  Resolutions,
  Stream,
} from "./types";

const BASE_URL: string = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

/** Ошибка API: код и текст пришли с сервера, status — HTTP-статус (0 — сервер недоступен). */
export class ApiError extends Error {
  status: number; // HTTP-статус
  code: string; // код ошибки (KEITARO_UNREACHABLE, MERGE_CONFLICT и т.д.)
  details: Record<string, unknown>; // подробности

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // сервер не отвечает вообще (не запущен, нет сети)
    throw new ApiError(0, "NETWORK", "Не удалось связаться с сервером legko2. Проверьте, что бэкенд запущен.");
  }

  if (!response.ok) {
    let payload: { code?: string; message?: string; details?: Record<string, unknown> } = {};
    try {
      payload = await response.json();
    } catch {
      /* тело не JSON: используем общее сообщение */
    }
    throw new ApiError(
      response.status,
      payload.code ?? "HTTP_ERROR",
      payload.message ?? `Ошибка сервера (${response.status}).`,
      payload.details ?? {},
    );
  }
  return (await response.json()) as T;
}

export const api = {
  meta: () => request<Meta>("GET", "/meta"),
  campaigns: () => request<CampaignSummary[]>("GET", "/campaigns"),
  campaign: (id: number) => request<Campaign>("GET", `/campaigns/${id}`),
  fetchCampaign: (id: number) => request<Campaign>("POST", `/campaigns/${id}/fetch`),
  addOffer: (streamId: number, offerId: number) =>
    request<Stream>("POST", `/streams/${streamId}/offers`, { offer_id: offerId }),
  removeOffer: (streamId: number, offerId: number) => request<Stream>("DELETE", `/streams/${streamId}/offers/${offerId}`),
  restoreOffer: (streamId: number, offerId: number) =>
    request<Stream>("POST", `/streams/${streamId}/offers/${offerId}/restore`),
  pinOffer: (streamId: number, offerId: number, pinned: boolean) =>
    request<Stream>("PUT", `/streams/${streamId}/offers/${offerId}/pin`, { pinned }),
  cancelStream: (streamId: number) => request<Stream>("POST", `/streams/${streamId}/cancel`),
  preview: (streamId: number, resolutions: Resolutions = {}) =>
    request<Preview>("POST", `/streams/${streamId}/preview`, { resolutions }),
  push: (streamId: number, resolutions: Resolutions = {}) =>
    request<Stream>("POST", `/streams/${streamId}/push`, { resolutions }),
  searchOffers: (query: string) => request<OfferSearchResult[]>("GET", `/offers/search?q=${encodeURIComponent(query)}`),
  references: () => request<References>("GET", "/references"),
  createCampaign: (body: CreateCampaignBody) => request<CreateReport>("POST", "/campaign-creator/campaigns", body),
  retryStream2: (campaignId: number, offerId: number, name: string, alias: string, geo: string) =>
    request<CreateReport>("POST", `/campaign-creator/campaigns/${campaignId}/retry-stream2`, {
      offer_id: offerId,
      name,
      alias,
      geo,
    }),
  mockExternalChange: (body: ExternalChangeBody) => request<{ status: string }>("POST", "/mock/external-change", body),
  mockFailure: (body: FailureBody) => request<{ status: string }>("POST", "/mock/failure", body),
  mockReset: () => request<{ status: string }>("POST", "/mock/reset"),
};
