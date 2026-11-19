/** Сегментированная полоса долей: сегмент на оффер, ширина по весу, закреплённый вес со штриховкой. */
import type { CSSProperties } from "react";

export interface ShareItem {
  weight: number; // вес, %
  pinned: boolean; // вес закреплён
  title?: string; // подсказка при наведении
}

/** Минимальный вес, при котором внутри сегмента помещается подпись с процентом. */
export const LABEL_MIN_WEIGHT = 9;

/** Сколько разных цветов у сегментов (классы c0..c7 в styles.css); дальше цвета повторяются. */
export const SEGMENT_COLORS = 8;

interface Props {
  items: ShareItem[];
  small?: boolean; // уменьшенная полоса для сравнения в диалоге
}

export function ShareBar({ items, small = false }: Props) {
  // в полосе только офферы с весом больше нуля
  const visible = items.filter((item) => item.weight > 0);
  const cls = `bar${small ? " small" : ""}`;

  if (visible.length === 0) {
    return <div className={`${cls} empty`}>Нет активных офферов</div>;
  }

  return (
    <div className={cls} role="img" aria-label={`Распределение долей: ${visible.map((i) => `${i.weight}%`).join(", ")}`}>
      {visible.map((item, index) => {
        const style: CSSProperties = { flex: `${item.weight} 1 0` };
        return (
          <div
            key={index}
            className={`seg c${index % SEGMENT_COLORS}${item.pinned ? " pinned" : ""}`}
            style={style}
            title={item.title}
            data-testid="segment"
          >
            <span>{item.weight >= LABEL_MIN_WEIGHT ? `${item.weight}%` : ""}</span>
          </div>
        );
      })}
    </div>
  );
}
