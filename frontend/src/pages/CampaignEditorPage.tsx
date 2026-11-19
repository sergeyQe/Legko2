/** Редактор кампании: потоки, действия над черновиком, отправка в Keitaro. */
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import type { Campaign, Offer, Stream } from "../api/types";
import { PushDialog } from "../components/PushDialog";
import { StreamCard } from "../components/StreamCard";
import { errorText } from "../lib/format";

const TOAST_MS = 6000; // сколько показываем сообщение

interface Props {
  campaignId: number;
  keitaroUrl: string; // адрес Keitaro (пусто в режиме mock)
}

interface Toast {
  kind: "ok" | "err";
  text: string;
}

export function CampaignEditorPage({ campaignId, keitaroUrl }: Props) {
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const [streamErrors, setStreamErrors] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [pushFor, setPushFor] = useState<Stream | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();

  const say = useCallback((kind: Toast["kind"], text: string) => {
    setToast({ kind, text });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), TOAST_MS);
  }, []);

  // открываем кампанию из нашей БД; если потоки ещё не загружали, загружаем их из Keitaro.
  // Запрос общий для повторного запуска эффекта (StrictMode в разработке), чтобы не грузить кампанию дважды.
  const loading = useRef<{ id: number; promise: Promise<Campaign> } | null>(null);
  useEffect(() => {
    let cancelled = false;
    if (loading.current?.id !== campaignId) {
      loading.current = {
        id: campaignId,
        promise: (async () => {
          const loaded = await api.campaign(campaignId);
          return loaded.fetched_at ? loaded : api.fetchCampaign(campaignId);
        })(),
      };
    }
    loading.current.promise
      .then((loaded) => !cancelled && setCampaign(loaded))
      .catch((error) => !cancelled && setLoadError(errorText(error)));
    return () => {
      cancelled = true;
      clearTimeout(toastTimer.current);
    };
  }, [campaignId]);

  const replaceStream = useCallback((updated: Stream) => {
    setCampaign((current) =>
      current ? { ...current, streams: current.streams.map((s) => (s.id === updated.id ? updated : s)) } : current,
    );
  }, []);

  /** Выполняет действие над потоком: блокирует кнопки, обновляет поток, показывает ошибку. */
  const run = useCallback(
    async (action: () => Promise<Stream>, okText?: string): Promise<boolean> => {
      setBusy(true);
      try {
        replaceStream(await action());
        if (okText) say("ok", okText);
        return true;
      } catch (error) {
        say("err", errorText(error));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [replaceStream, say],
  );

  async function fetchStreams() {
    setBusy(true);
    try {
      setCampaign(await api.fetchCampaign(campaignId));
      setStreamErrors({});
      say("ok", "Потоки загружены из KT. Неопубликованные изменения сохранены.");
    } catch (error) {
      say("err", errorText(error));
    } finally {
      setBusy(false);
    }
  }

  function clearStreamError(streamId: number) {
    setStreamErrors((current) => {
      const { [streamId]: _removed, ...rest } = current;
      return rest;
    });
  }

  async function cancel(stream: Stream) {
    if (await run(() => api.cancelStream(stream.id), "Изменения отменены. Поток снова совпадает с Keitaro.")) {
      clearStreamError(stream.id);
    }
  }

  /** Повторная отправка после ошибки: если появились спорные пункты, открываем диалог. */
  async function retryPush(stream: Stream) {
    setBusy(true);
    try {
      const sent = await api.push(stream.id, {});
      replaceStream(sent);
      clearStreamError(stream.id);
      say("ok", "Поток отправлен в Keitaro.");
    } catch (error) {
      if (error instanceof ApiError && error.code === "MERGE_CONFLICT") setPushFor(stream);
      else setStreamErrors((current) => ({ ...current, [stream.id]: errorText(error) }));
    } finally {
      setBusy(false);
    }
  }

  if (loadError) {
    return (
      <div className="note err" role="alert">
        <div className="grow">{loadError}</div>
      </div>
    );
  }
  if (!campaign) return <p className="muted">Открываем кампанию…</p>;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Потоки кампании {campaign.name}</h1>
          <div className="meta">ID {campaign.keitaro_id} · ротация по весу</div>
        </div>
        <div className="btns">
          <button className="btn" disabled={busy} onClick={fetchStreams}>
            Загрузить потоки из KT
          </button>
          {keitaroUrl ? (
            <a className="btn" href={`${keitaroUrl.replace(/\/+$/, "")}/admin/`} target="_blank" rel="noreferrer">
              Кампания в Keitaro <span aria-hidden="true">↗</span>
            </a>
          ) : (
            <button className="btn" disabled title="В режиме mock Keitaro нет: ссылка появится при подключении настоящего Keitaro.">
              Кампания в Keitaro <span aria-hidden="true">↗</span>
            </button>
          )}
        </div>
      </div>

      <div className="note" role="note">
        <span className="grow">
          Не меняйте поток в Keitaro между загрузкой и отправкой: изменения придётся объединять.
        </span>
      </div>

      {toast ? (
        <div className={`note ${toast.kind === "err" ? "err" : "ok"} status`} role="status">
          {toast.text}
        </div>
      ) : (
        <div className="status" role="status" />
      )}

      <div style={{ display: "grid", gap: 14 }}>
        {campaign.streams.map((stream) => (
          <StreamCard
            key={stream.id}
            stream={stream}
            error={streamErrors[stream.id] ?? null}
            busy={busy}
            onAdd={(offerId) => run(() => api.addOffer(stream.id, offerId), `Оффер ${offerId} добавлен в черновик. В Keitaro ничего не изменилось.`)}
            onProblem={(message) => say("err", message)}
            onPin={(offer: Offer) => void run(() => api.pinOffer(stream.id, offer.offer_id, !offer.pinned))}
            onRemove={(offer: Offer) => void run(() => api.removeOffer(stream.id, offer.offer_id))}
            onRestore={(offer: Offer) => void run(() => api.restoreOffer(stream.id, offer.offer_id), `Оффер ${offer.offer_id} возвращён в черновик.`)}
            onCancel={() => void cancel(stream)}
            onOpenPush={() => setPushFor(stream)}
            onRetry={() => void retryPush(stream)}
          />
        ))}
      </div>

      {pushFor && (
        <PushDialog
          stream={pushFor}
          onClose={() => setPushFor(null)}
          onPushed={(sent) => {
            replaceStream(sent);
            clearStreamError(sent.id);
            setPushFor(null);
            say("ok", `Поток «${sent.name}» отправлен в Keitaro.`);
          }}
          onFailed={(message) => {
            setStreamErrors((current) => ({ ...current, [pushFor.id]: message }));
            setPushFor(null);
          }}
        />
      )}
    </>
  );
}
