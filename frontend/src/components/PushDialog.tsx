/** Диалог отправки в Keitaro: шаг «Объединение» (если Keitaro меняли) и шаг «Проверка». */
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "../api/client";
import type { MergeItem, Preview, Resolution, Resolutions, Stream } from "../api/types";
import { errorText } from "../lib/format";
import { ChangeTable } from "./ChangeTable";
import { ShareBar } from "./ShareBar";

type Step = "merge" | "review";

interface Props {
  stream: Stream; // поток, который отправляем
  onClose: () => void;
  onPushed: (stream: Stream) => void; // отправка прошла
  onFailed: (message: string, resolutions: Resolutions) => void; // отправка не удалась (черновик сохранён), диалог закрывается; решения по конфликтам сохраняются для повтора
}

/** Заголовки вариантов для известных спорных пунктов (по окончанию ключа). */
const CHOICE_TITLES: Record<string, [string, string]> = {
  weight_changed_removed: ["Оставить убранным", "Вернуть с весом из Keitaro"],
  pinned_removed_in_kt: ["Оставить оффер в потоке", "Считать удалённым (в архив)"],
};
const CHOICE_HINTS: Record<string, [string, string]> = {
  weight_changed_removed: ["Оффер уйдёт в архив, как в вашем черновике.", "Берём вес из Keitaro, остальные доли пересчитаем."],
  pinned_removed_in_kt: ["Оффер вернётся в Keitaro как новый.", "Оффер уйдёт в архив, как в Keitaro."],
};

function choiceTitles(key: string): [string, string] {
  return CHOICE_TITLES[key.split(":")[1] ?? ""] ?? ["Как в черновике", "Как в Keitaro"];
}
function choiceHints(key: string): [string, string] {
  return CHOICE_HINTS[key.split(":")[1] ?? ""] ?? ["Берём вариант из черновика.", "Берём вариант из Keitaro."];
}

export function PushDialog({ stream, onClose, onPushed, onFailed }: Props) {
  const [resolutions, setResolutions] = useState<Resolutions>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [step, setStep] = useState<Step>("review");
  const [options, setOptions] = useState<Record<string, Record<Resolution, Preview>>>({});
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const firstButton = useRef<HTMLButtonElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  // загружаем предпросмотр с текущими решениями
  const load = useCallback(
    async (current: Resolutions, initial = false) => {
      try {
        const result = await api.preview(stream.id, current);
        setPreview(result);
        if (initial) setStep(result.merge_items.length > 0 ? "merge" : "review");

        // для каждого спорного пункта считаем итог при обоих вариантах, чтобы показать последствия
        const conflicts = result.merge_items.filter((i) => i.kind === "conflict");
        const entries = await Promise.all(
          conflicts.map(async (item) => {
            const [draft, keitaro] = await Promise.all([
              api.preview(stream.id, { ...current, [item.key]: "draft" }),
              api.preview(stream.id, { ...current, [item.key]: "keitaro" }),
            ]);
            return [item.key, { draft, keitaro }] as const;
          }),
        );
        setOptions(Object.fromEntries(entries));
        setProblem(null);
      } catch (error) {
        setProblem(errorText(error));
      }
    },
    [stream.id],
  );

  useEffect(() => {
    void load({}, true);
  }, [load]);

  // Esc закрывает диалог, Tab не выпускает фокус за его пределы
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") return onClose();
      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // фокус на первую кнопку при открытии; при закрытии возвращаем его туда, откуда диалог открыли
  const opener = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null);
  useEffect(() => {
    firstButton.current?.focus();
  }, [preview === null]);
  useEffect(() => {
    const target = opener.current;
    return () => target?.focus?.();
  }, []);

  async function choose(key: string, value: Resolution) {
    const next = { ...resolutions, [key]: value };
    setResolutions(next);
    await load(next);
  }

  async function push() {
    setBusy(true);
    try {
      onPushed(await api.push(stream.id, resolutions));
    } catch (error) {
      if (error instanceof ApiError && error.code === "MERGE_CONFLICT") {
        // пока мы смотрели, в Keitaro снова что-то поменяли: показываем свежие данные
        setStep("merge");
        await load(resolutions, true);
        setProblem(error.message);
      } else {
        onFailed(errorText(error), resolutions);
      }
    } finally {
      setBusy(false);
    }
  }

  const unresolved = preview?.unresolved.length ?? 0;
  const hasMerge = (preview?.merge_items.length ?? 0) > 0;
  const canPush = !!preview && preview.can_push && !busy;

  return (
    <div className="scrim" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dlg" role="dialog" aria-modal="true" aria-labelledby="push-title" ref={dialogRef}>
        {hasMerge && (
          <ol className="stepper" aria-label="Шаги">
            <li className={step === "merge" ? "cur" : "done"}>1 · Объединение</li>
            <li className={step === "review" ? "cur" : ""}>2 · Проверка</li>
          </ol>
        )}

        {problem && (
          <div className="note err" role="alert">
            <div className="grow">{problem}</div>
          </div>
        )}
        {!preview && !problem && <p className="muted">Загружаем предпросмотр…</p>}

        {preview && step === "merge" && (
          <MergeStep
            stream={stream}
            preview={preview}
            options={options}
            resolutions={resolutions}
            onChoose={choose}
          />
        )}
        {preview && step === "review" && <ReviewStep stream={stream} preview={preview} />}

        <div className="dlg-foot">
          {step === "merge" ? (
            <>
              <button ref={firstButton} className="btn" onClick={onClose}>
                Отмена
              </button>
              <button className="btn primary" disabled={unresolved > 0 || !preview} onClick={() => setStep("review")}>
                Далее: проверить
              </button>
            </>
          ) : (
            <>
              <button ref={firstButton} className="btn" onClick={hasMerge ? () => setStep("merge") : onClose}>
                {hasMerge ? "Назад к объединению" : "Назад"}
              </button>
              <button className="btn primary" disabled={!canPush} onClick={push}>
                Отправить в KT
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function MergeStep(props: {
  stream: Stream;
  preview: Preview;
  options: Record<string, Record<Resolution, Preview>>;
  resolutions: Resolutions;
  onChoose: (key: string, value: Resolution) => void;
}) {
  const { stream, preview, options, resolutions, onChoose } = props;

  return (
    <>
      <h2 id="push-title">В Keitaro поток изменили после загрузки</h2>
      <p className="muted" style={{ margin: 0 }}>
        Пока вы правили черновик, поток «{stream.name}» поменяли в Keitaro. Ниже, что мы сохраним сами и что нужно решить вам.
      </p>
      {preview.merge_items.map((item) =>
        item.kind === "auto" ? (
          <div key={item.key} className="mrow auto">
            <span className="ok-ic" aria-hidden="true">✓</span>
            <div>
              <div className="k">Объединено автоматически</div>
              {item.message}
            </div>
          </div>
        ) : (
          <ConflictCard key={item.key} item={item} options={options[item.key]} value={resolutions[item.key]} onChoose={onChoose} />
        ),
      )}
    </>
  );
}

function ConflictCard(props: {
  item: MergeItem;
  options: Record<Resolution, Preview> | undefined;
  value: Resolution | undefined;
  onChoose: (key: string, value: Resolution) => void;
}) {
  const { item, options, value, onChoose } = props;
  const [draftTitle, keitaroTitle] = choiceTitles(item.key);
  const [draftHint, keitaroHint] = choiceHints(item.key);
  const variants: [Resolution, string, string][] = [
    ["draft", draftTitle, draftHint],
    ["keitaro", keitaroTitle, keitaroHint],
  ];

  return (
    <div className="conf">
      <div>
        <div className="k">Нужно ваше решение</div>
        <strong>{item.message}</strong>
      </div>
      <div className="opts" role="radiogroup" aria-label={`Решение: ${item.message}`}>
        {variants.map(([resolution, title, hint]) => {
          const result = options?.[resolution]?.stream;
          const active = result?.offers.filter((o) => o.state === "published" || o.state === "added") ?? [];
          return (
            <label key={resolution} className="opt">
              <input
                type="radio"
                name={`choice-${item.key}`}
                checked={value === resolution}
                onChange={() => onChoose(item.key, resolution)}
              />
              <strong>{title}</strong>
              <span className="muted">{hint}</span>
              {result && <ShareBar small items={active.map((o) => ({ weight: o.weight, pinned: o.pinned }))} />}
              {result && <span className="num">Доли после выбора: {active.map((o) => `${o.weight}%`).join(" / ")}</span>}
            </label>
          );
        })}
      </div>
    </div>
  );
}

function ReviewStep({ stream, preview }: { stream: Stream; preview: Preview }) {
  const count = (kind: "add" | "remove" | "change") => preview.changes.filter((c) => c.kind === kind).length;
  const active = preview.stream.offers.filter((o) => o.state === "published" || o.state === "added");
  const merged = preview.merge_items;

  return (
    <>
      <h2 id="push-title">Отправить «{stream.name}» в Keitaro?</h2>
      <p className="muted" style={{ margin: 0 }}>
        Keitaro заменит офферы потока этим списком. Убранные офферы останутся у вас в архиве, их можно вернуть.
      </p>
      <div className="sumchips">
        {count("add") > 0 && <span className="chip add">+{count("add")} добавится</span>}
        {count("remove") > 0 && <span className="chip rem">−{count("remove")} уйдёт в архив</span>}
        {count("change") > 0 && <span className="chip chg">~{count("change")} изменится вес</span>}
        {preview.changes.length === 0 && <span className="chip gray">Без изменений</span>}
      </div>
      <div className="preview-pair">
        <div className="cmp">
          <div className="cap">Сейчас в Keitaro</div>
          <ShareBar small items={preview.keitaro_offers.map((o) => ({ weight: o.weight, pinned: false }))} />
        </div>
        <div className="cmp">
          <div className="cap">Станет после отправки · сумма {preview.stream.weight_sum}%</div>
          <ShareBar small items={active.map((o) => ({ weight: o.weight, pinned: o.pinned }))} />
        </div>
      </div>
      <ChangeTable changes={preview.changes} />
      {active.length === 0 && (
        <div className="note err" role="alert">
          <div className="grow">
            В потоке не осталось активных офферов, отправлять нечего. Верните оффер в поток или отмените изменения.
          </div>
        </div>
      )}
      {merged.length > 0 && (
        <div className="mrow auto">
          <span className="ok-ic" aria-hidden="true">✓</span>
          <div>
            <div className="k">Учтено объединение с Keitaro</div>
            {merged.map((m) => (
              <div key={m.key}>{m.message}</div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
