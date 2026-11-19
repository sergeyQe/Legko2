/** Демо-панель (только режим mock): имитация правок и сбоев Keitaro и сброс данных. */
import { useState } from "react";

import { api } from "../api/client";
import { errorText } from "../lib/format";

interface Props {
  onReset: () => void; // после сброса страница перезагружает данные
}

/** ID потока 2 в заглушке Keitaro и офферы для сценариев демонстрации. */
const MOCK_STREAM_ID = 2;

export function DemoPanel({ onReset }: Props) {
  const [message, setMessage] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>, success: string) {
    try {
      await action();
      setMessage(success);
    } catch (error) {
      setMessage(errorText(error));
    }
  }

  return (
    <div className="demo" role="group" aria-label="Демо-панель">
      <span className="lbl">Демо (mock Keitaro)</span>
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
  );
}
