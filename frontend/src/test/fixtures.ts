/** Данные для тестов: потоки и офферы в формате API. */
import type { Campaign, Offer, Preview, Stream } from "../api/types";

export function offer(id: number, weight: number, extra: Partial<Offer> = {}): Offer {
  return {
    offer_id: id,
    name: `Оффер ${id}`,
    geo: "Румыния",
    state: "published",
    weight,
    kt_weight: weight,
    pinned: false,
    ...extra,
  };
}

export function stream(id: number, offers: Offer[], extra: Partial<Stream> = {}): Stream {
  return {
    id,
    keitaro_id: id,
    name: `Поток ${id}`,
    position: id,
    has_offers: offers.length > 0,
    dirty: false,
    weight_sum: offers.filter((o) => o.state === "published" || o.state === "added").reduce((a, o) => a + o.weight, 0),
    offers,
    notes: [],
    ...extra,
  };
}

/** Кампания со скриншотов: поток без офферов и поток с тремя офферами 33/33/34. */
export function campaign(streams: Stream[] = [stream(1, []), stream(2, [offer(11109, 33), offer(11110, 33), offer(11111, 34)])]): Campaign {
  return { id: 1, keitaro_id: 93212, name: "campaign 2", alias: "campaign-2", fetched_at: "2026-11-19T10:00:00Z", streams };
}

export function preview(target: Stream, extra: Partial<Preview> = {}): Preview {
  return {
    stream: target,
    keitaro_offers: [],
    changes: [],
    merge_items: [],
    unresolved: [],
    can_push: true,
    ...extra,
  };
}
