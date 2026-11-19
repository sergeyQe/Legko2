/** Список кампаний: состояние публикации и переход в редактор. */
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { CampaignSummary } from "../api/types";
import { errorText } from "../lib/format";

interface Props {
  onOpen: (id: number) => void;
  onCreate: () => void;
}

export function CampaignListPage({ onOpen, onCreate }: Props) {
  const [campaigns, setCampaigns] = useState<CampaignSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.campaigns().then(setCampaigns).catch((e) => setError(errorText(e)));
  }, []);

  return (
    <>
      <div className="page-head">
        <h1>Кампании</h1>
        <button className="btn primary" onClick={onCreate}>
          Создать кампанию
        </button>
      </div>

      {error && (
        <div className="note err" role="alert">
          <div className="grow">{error}</div>
        </div>
      )}
      {!campaigns && !error && <p className="muted">Загружаем кампании…</p>}

      <div className="camps">
        {campaigns?.map((c) => (
          <div className="camp" key={c.id} data-testid={`campaign-${c.keitaro_id}`}>
            <div>
              <div className="nm">{c.name}</div>
              <div className="muted">
                ID {c.keitaro_id}
                {c.fetched ? ` · потоков: ${c.streams_total} · с офферами: ${c.streams_with_offers}` : " · потоки ещё не загружены"}
              </div>
            </div>
            <div className="btns">
              {c.dirty ? (
                <span className="chip warn">Есть неопубликованные изменения</span>
              ) : (
                <span className="chip">{c.fetched ? "Всё опубликовано" : "Не загружена"}</span>
              )}
              <button className="btn primary" onClick={() => onOpen(c.id)}>
                Открыть редактор
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
