/** Строка оффера: метка цвета сегмента, название, доля, закрепление и убрать/вернуть. */
import type { Offer } from "../api/types";
import { isActive, stateTag } from "../lib/format";
import { SEGMENT_COLORS } from "./ShareBar";

const PIN_ICON = (
  <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true">
    <path
      fill="currentColor"
      d="M9.6 1.4l5 5-1.9.7-2.5 2.5.3 3.2-1.1 1.1-2.6-2.6L3.5 14.2l-.7-.7 3.2-3.2-2.6-2.6 1.1-1.1 3.2.3 2.5-2.5z"
    />
  </svg>
);

interface Props {
  offer: Offer;
  colorIndex: number | null; // индекс цвета сегмента (null — оффер не активен)
  busy: boolean; // идёт запрос: кнопки заблокированы
  onPin: (offer: Offer) => void;
  onRemove: (offer: Offer) => void;
  onRestore: (offer: Offer) => void;
}

export function OfferRow({ offer, colorIndex, busy, onPin, onRemove, onRestore }: Props) {
  const active = isActive(offer);
  const tag = stateTag(offer);

  return (
    <div className={`orow${active ? "" : " gone"}`} data-testid={`offer-${offer.offer_id}`}>
      <span className={`dot${active && colorIndex !== null ? ` c${colorIndex % SEGMENT_COLORS}` : ""}`} />
      <div className="name">
        <span className="oid">{offer.offer_id}</span>
        {offer.name}
        {tag.text && <span className={`tag ${tag.kind}`}>{tag.text}</span>}
        {offer.geo && <div className="geo">{offer.geo}</div>}
      </div>
      <div className="share num">{offer.weight}%</div>
      <div className="act">
        {active && (
          <button
            className="pin"
            aria-pressed={offer.pinned}
            aria-label={offer.pinned ? `Открепить вес оффера ${offer.offer_id}` : `Закрепить вес оффера ${offer.offer_id}`}
            title={offer.pinned ? "Вес закреплён" : "Закрепить вес"}
            disabled={busy}
            onClick={() => onPin(offer)}
          >
            {PIN_ICON}
          </button>
        )}{" "}
        {active ? (
          <button
            className="btn sm"
            disabled={busy}
            aria-label={`Убрать из потока, оффер ${offer.offer_id}`}
            onClick={() => onRemove(offer)}
          >
            Убрать из потока
          </button>
        ) : (
          <button
            className="btn sm"
            disabled={busy}
            aria-label={`Вернуть в поток, оффер ${offer.offer_id}`}
            onClick={() => onRestore(offer)}
          >
            Вернуть в поток
          </button>
        )}
      </div>
    </div>
  );
}
