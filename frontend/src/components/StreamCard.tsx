/** Карточка потока: заголовок со статусом, полоса долей, офферы, добавление и кнопки публикации. */
import type { Offer, Stream } from "../api/types";
import { isActive } from "../lib/format";
import { AddOfferForm } from "./AddOfferForm";
import { OfferRow } from "./OfferRow";
import { ShareBar } from "./ShareBar";

interface Props {
  stream: Stream;
  error: string | null; // ошибка последней отправки (черновик сохранён)
  busy: boolean; // идёт запрос
  onAdd: (offerId: number) => Promise<boolean>;
  onProblem: (message: string) => void;
  onPin: (offer: Offer) => void;
  onRemove: (offer: Offer) => void;
  onRestore: (offer: Offer) => void;
  onCancel: () => void;
  onOpenPush: () => void;
  onRetry: () => void;
}

export function StreamCard(props: Props) {
  const { stream, error, busy } = props;

  // поток без офферов показываем без содержимого
  if (!stream.has_offers) {
    return (
      <section className="stream empty" aria-label={stream.name}>
        <h3>{stream.name}</h3>
        <span className="chip gray">без офферов</span>
        <span>Содержимое потока не показываем и не меняем.</span>
      </section>
    );
  }

  const active = stream.offers.filter(isActive);
  let colorIndex = 0;

  return (
    <section className={`stream${stream.dirty ? " dirty" : ""}`} aria-label={stream.name} data-testid={`stream-${stream.id}`}>
      <div className="stream-head">
        <div className="ttl">
          <h3>{stream.name}</h3>
          <span className={`chip${stream.dirty ? " warn" : ""}`}>{stream.dirty ? "Не опубликован" : "Опубликован"}</span>
          <span className="muted">
            Сумма{" "}
            <span className={`sum ${stream.weight_sum === 100 ? "good" : "bad"}`}>
              {stream.weight_sum}%{stream.weight_sum === 100 ? " ✓" : " — должно быть 100%"}
            </span>
          </span>
        </div>
        {stream.dirty && (
          <div className="btns">
            <button className="btn" disabled={busy} onClick={props.onCancel}>
              Отменить изменения
            </button>
            <button className="btn primary" disabled={busy} onClick={props.onOpenPush}>
              Отправить в KT
            </button>
          </div>
        )}
      </div>

      <div className="inner">
        {error && (
          <div className="note err" role="alert" style={{ margin: "0 20px 8px" }}>
            <div className="grow">
              <strong>Не отправлено.</strong> {error}
            </div>
            <button className="btn sm" disabled={busy} onClick={props.onRetry}>
              Повторить
            </button>
          </div>
        )}
        {stream.notes.length > 0 && (
          <div className="note" role="note" style={{ margin: "0 20px 8px" }}>
            <div className="grow">
              {stream.notes.map((note) => (
                <div key={note}>{note}</div>
              ))}
            </div>
          </div>
        )}

        <ShareBar items={active.map((o) => ({ weight: o.weight, pinned: o.pinned, title: `${o.name} — ${o.weight}%` }))} />
        <div className="cols-note">Статистика и тренды: пока пусто</div>

        <div className="olist">
          {stream.offers.map((offer) => (
            <OfferRow
              key={offer.offer_id}
              offer={offer}
              colorIndex={isActive(offer) && offer.weight > 0 ? colorIndex++ : null}
              busy={busy}
              onPin={props.onPin}
              onRemove={props.onRemove}
              onRestore={props.onRestore}
            />
          ))}
        </div>

        <AddOfferForm disabled={busy} onAdd={props.onAdd} onProblem={props.onProblem} />
      </div>
    </section>
  );
}
