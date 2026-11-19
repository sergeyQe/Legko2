/** Типы ответов API (соответствуют схемам backend/app/api/schemas.py). */

/** Состояние оффера: опубликован, добавлен (не опубликован), убирается, удалён (архив). */
export type OfferState = "published" | "added" | "removing" | "removed";

export interface Offer {
  offer_id: number; // ID оффера в Keitaro
  name: string; // название
  geo: string; // гео для подписи
  state: OfferState; // состояние
  weight: number; // вес в черновике, %
  kt_weight: number; // вес в Keitaro по последней загрузке, %
  pinned: boolean; // вес закреплён
}

export interface Stream {
  id: number; // внутренний ID потока
  keitaro_id: number; // ID потока в Keitaro
  name: string; // название
  position: number; // позиция
  has_offers: boolean; // есть ли офферы
  dirty: boolean; // есть неопубликованные изменения
  weight_sum: number; // сумма весов активных офферов
  offers: Offer[]; // офферы
  notes: string[]; // сообщения по итогам загрузки
}

export interface Campaign {
  id: number; // внутренний ID
  keitaro_id: number; // ID в Keitaro
  name: string; // название
  alias: string; // алиас
  fetched_at: string | null; // когда загружали потоки
  streams: Stream[]; // потоки
}

export interface CampaignSummary {
  id: number;
  keitaro_id: number;
  name: string;
  alias: string;
  fetched: boolean; // загружали ли потоки
  streams_total: number | null;
  streams_with_offers: number | null;
  dirty: boolean; // есть неопубликованные изменения
}

export type Resolution = "draft" | "keitaro";
export type Resolutions = Record<string, Resolution>;

export interface Change {
  kind: "add" | "remove" | "change"; // что произойдёт с оффером
  offer_id: number;
  name: string;
  from_weight: number | null; // вес в Keitaro сейчас
  to_weight: number; // вес после отправки
  note: string; // пояснение
}

export interface MergeItem {
  key: string; // ключ пункта (по нему присылается решение)
  kind: "auto" | "conflict"; // объединено само или нужно решение
  offer_id: number;
  message: string;
  resolution: Resolution | null;
}

export interface KtOffer {
  offer_id: number;
  name: string;
  geo: string;
  weight: number;
}

export interface Preview {
  stream: Stream; // поток после объединения
  keitaro_offers: KtOffer[]; // офферы в Keitaro сейчас
  changes: Change[]; // изменения
  merge_items: MergeItem[]; // пункты объединения
  unresolved: MergeItem[]; // спорные пункты без решения
  can_push: boolean; // можно ли отправлять
}

export interface CreateStep {
  name: "campaign" | "stream1" | "stream2";
  description: string;
  status: "ok" | "failed" | "skipped";
  error: string | null;
}

export interface CreateReport {
  ok: boolean;
  campaign_id: number | null;
  name: string;
  alias: string;
  steps: CreateStep[];
}

export interface CreateCampaignBody {
  name: string;
  geo: string;
  offer_id: number;
  domain_id: number | null;
  group_id: number | null;
  source_id: number | null;
}

export interface Reference {
  id: number;
  name: string;
}

export interface References {
  domains: Reference[];
  groups: Reference[];
  sources: Reference[];
  defaults: { domain_id: number | null; group_id: number | null; source_id: number | null; missing: string[] };
}

export interface OfferSearchResult {
  offer_id: number;
  name: string;
  geo: string;
}

export interface Meta {
  version: string;
  keitaro_url: string; // адрес Keitaro
  campaign_prefix: string; // префикс названий кампаний (например test_titov_)
}
