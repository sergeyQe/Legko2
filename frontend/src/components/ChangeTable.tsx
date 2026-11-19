/** Таблица «Оффер / Было / Станет» для предпросмотра отправки. */
import type { Change } from "../api/types";

const SIGNS: Record<Change["kind"], string> = { add: "+", remove: "−", change: "~" };

interface Props {
  changes: Change[];
}

export function ChangeTable({ changes }: Props) {
  if (changes.length === 0) {
    return <p className="muted" style={{ margin: 0 }}>Изменений нет: поток совпадает с Keitaro.</p>;
  }

  return (
    <div className="ctbl" role="table" aria-label="Изменения потока">
      <div className="crow h" role="row">
        <span />
        <span>Оффер</span>
        <span>Было</span>
        <span>Станет</span>
      </div>
      {changes.map((change) => (
        <div key={change.offer_id} className={`crow ${change.kind}`} role="row">
          <span className="sg" aria-hidden="true">
            {SIGNS[change.kind]}
          </span>
          <span className="nm">
            <span className="oid">{change.offer_id}</span>
            {change.name}
            <div className="geo">{change.note}</div>
          </span>
          <span className="num">{change.from_weight === null ? "—" : `${change.from_weight}%`}</span>
          <span className="num to">{change.kind === "remove" ? "0%" : `${change.to_weight}%`}</span>
        </div>
      ))}
    </div>
  );
}
