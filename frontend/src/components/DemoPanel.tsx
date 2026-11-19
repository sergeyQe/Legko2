/** Демо-панель (только режим mock): имитация правок и сбоев Keitaro и сброс данных. */
import { useRef, useState } from "react";

import { api } from "../api/client";
import { errorText } from "../lib/format";

interface Props {
  onReset: () => void; // после сброса страница перезагружает данные
}

/** ID потока 2 в заглушке Keitaro и офферы для сценариев демонстрации. */
const MOCK_STREAM_ID = 2;

const MESSAGE_MS = 6000; // сколько показываем сообщение демо-панели

export function DemoPanel({ onReset }: Props) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  // на узком экране панель свёрнута, чтобы не занимать место; на широком открыта
  const startOpen = useRef(typeof window.matchMedia !== "function" || window.matchMedia("(min-width: 641px)").matches);

  async function run(action: () => Promise<unknown>, success: string) {
    try {
      await action();
      setMessage(success);
    } catch (error) {
      setMessage(errorText(error));
    }
    // сообщение не должно устаревать: через несколько секунд убираем
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(null), MESSAGE_MS);
  }

  return (
    <details className="demo" open={startOpen.current}>
      <summary>Демо (mock Keitaro)</summary>
      <div className="demo-body" role="group" aria-label="Демо-панель">
      <button
        className="btn sm"
        onClick={() =>
          run(
            () => api.mockExternalChange({ scenario: "offer_added", stream_id: MOCK_STREAM_ID, offer_id: 11120, weight: 20 }),
            "В Keitaro добавлен оффер 11120. Обёртка узнает об этом при отправке или загрузке.",
          )
        }
      >
        Правка: оффер 11120 в KT
      </button>
      <button
        className="btn sm"
        onClick={() =>
          run(
            () => api.mockExternalChange({ scenario: "weight_changed", stream_id: MOCK_STREAM_ID, offer_id: 11110, weight: 40 }),
            "В Keitaro вес оффера 11110 изменён на 40%.",
          )
        }
      >
        Правка: вес 11110 → 40%
      </button>
      <button
        className="btn sm"
        onClick={() => run(() => api.mockFailure({ kind: "network", target: "push" }), "Следующая отправка в KT завершится ошибкой сети.")}
      >
        Сбой отправки в KT
      </button>
      <button
        className="btn sm"
        onClick={() =>
          run(() => api.mockFailure({ kind: "rejected", target: "create_stream2" }), "Следующее создание потока 2 завершится ошибкой.")
        }
      >
        Сбой создания потока 2
      </button>
      <button
        className="btn sm"
        onClick={async () => {
          await run(() => api.mockReset(), "Демо сброшено: данные Keitaro и наши черновики очищены.");
          onReset();
        }}
      >
        Сбросить
      </button>
      {message && (
        <span className="muted" role="status">
          {message}
        </span>
      )}
      </div>
    </details>
  );
}
