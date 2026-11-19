/** Создание кампании: форма с живым предпросмотром, ход создания и итог по шагам. */
import { FormEvent, useEffect, useId, useMemo, useState } from "react";

import { ApiError, api } from "../api/client";
import type { CreateReport, CreateStep, OfferSearchResult, References } from "../api/types";
import { COUNTRY_NAMES, errorText, isGeoCode, parseOfferId, previewAlias } from "../lib/format";

type Stage = "form" | "running" | "done";

const STEP_ICON: Record<CreateStep["status"], string> = { ok: "✓", failed: "✕", skipped: "·" };

interface Props {
  onOpenCampaign: (keitaroId: number) => Promise<void>; // перейти в редактор созданной кампании
}

export function CreateCampaignPage({ onOpenCampaign }: Props) {
  const [refs, setRefs] = useState<References | null>(null);
  const [name, setName] = useState("");
  const [geo, setGeo] = useState("");
  const [offerInput, setOfferInput] = useState("");
  const [domainId, setDomainId] = useState<string>("");
  const [groupId, setGroupId] = useState<string>("");
  const [sourceId, setSourceId] = useState<string>("");
  const [offer, setOffer] = useState<OfferSearchResult | null>(null);
  const [stage, setStage] = useState<Stage>("form");
  const [report, setReport] = useState<CreateReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ids = { name: useId(), geo: useId(), offer: useId(), domain: useId(), group: useId(), source: useId() };

  // справочники и значения по умолчанию (не найденные значения остаются пустыми)
  useEffect(() => {
    api
      .references()
      .then((loaded) => {
        setRefs(loaded);
        setDomainId(loaded.defaults.domain_id?.toString() ?? "");
        setGroupId(loaded.defaults.group_id?.toString() ?? "");
        setSourceId(loaded.defaults.source_id?.toString() ?? "");
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  // ищем введённый оффер в базе Keitaro, чтобы показать его название и гео
  useEffect(() => {
    const id = parseOfferId(offerInput);
    if (id === null) {
      setOffer(null);
      return;
    }
    const timer = setTimeout(() => {
      api
        .searchOffers(String(id))
        .then((found) => setOffer(found.find((o) => o.offer_id === id) ?? null))
        .catch(() => setOffer(null));
    }, 250);
    return () => clearTimeout(timer);
  }, [offerInput]);

  const alias = previewAlias(name);
  const geoOk = isGeoCode(geo);
  const valid = name.trim() !== "" && alias !== "" && geoOk && offer !== null;

  const nameOf = (list: { id: number; name: string }[] | undefined, id: string) =>
    list?.find((r) => String(r.id) === id)?.name;

  const geoHint = useMemo(() => {
    if (!geo) return { text: "Две латинские буквы, например AU", bad: false };
    if (!geoOk) return { text: "Нужны две латинские буквы", bad: true };
    return { text: COUNTRY_NAMES[geo.toUpperCase()] ?? "Такого кода нет в подсказке. Правильность проверит Keitaro.", bad: false };
  }, [geo, geoOk]);

  const offerHint = !offerInput
    ? { text: "Введите ID оффера из базы Keitaro", bad: false }
    : offer
      ? { text: `${offer.name}${offer.geo ? ` · ${offer.geo}` : ""}`, bad: false }
      : { text: "Оффер не найден в Keitaro", bad: true };

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid || !offer) return;
    setStage("running");
    setError(null);
    try {
      setReport(
        await api.createCampaign({
          name: name.trim(),
          geo: geo.toUpperCase(),
          offer_id: offer.offer_id,
          domain_id: domainId ? Number(domainId) : null,
          group_id: groupId ? Number(groupId) : null,
          source_id: sourceId ? Number(sourceId) : null,
        }),
      );
      setStage("done");
    } catch (e) {
      if (e instanceof ApiError && e.code === "CREATE_PARTIAL") {
        // кампания создана не полностью: показываем, что получилось
        const details = e.details as { steps: CreateStep[]; campaign_id: number | null; name: string; alias: string };
        setReport({ ok: false, campaign_id: details.campaign_id, name: details.name, alias: details.alias, steps: details.steps });
        setStage("done");
      } else {
        setError(errorText(e));
        setStage("form");
      }
    }
  }

  async function retryStream2() {
    if (!report?.campaign_id || !offer) return;
    setStage("running");
    try {
      setReport(await api.retryStream2(report.campaign_id, offer.offer_id, report.name, report.alias));
      setStage("done");
    } catch (e) {
      if (e instanceof ApiError && e.code === "CREATE_PARTIAL") {
        const details = e.details as { steps: CreateStep[] };
        setReport({ ...report, ok: false, steps: details.steps });
      } else {
        setError(errorText(e));
      }
      setStage("done");
    }
  }

  function startOver() {
    setStage("form");
    setReport(null);
    setName("");
    setGeo("");
    setOfferInput("");
    setError(null);
  }

  if (stage !== "form") {
    const failed = report !== null && !report.ok;
    return (
      <>
        <div className="page-head">
          <h1>{stage === "running" ? "Создаём кампанию…" : failed ? "Кампания создана не полностью" : "Кампания создана"}</h1>
        </div>
        <div className="created">
          {stage === "running" && (
            <p className="muted" role="status">
              <span className="spin" aria-hidden="true" /> Создаём кампанию и потоки в Keitaro…
            </p>
          )}
          {stage === "done" && report && (
            <>
              <ul className="steps" role="status">
                {report.steps.map((step) => (
                  <li key={step.name} className={step.status}>
                    <span className="ic">{STEP_ICON[step.status]}</span>
                    <span>
                      {step.description}
                      {step.error && <div>Ошибка Keitaro: {step.error}</div>}
                    </span>
                  </li>
                ))}
              </ul>
              {failed ? (
                <div className="note err" role="alert">
                  <div className="grow">
                    <strong>Кампания создана не полностью.</strong> Кампанию и созданные потоки мы не удаляли: повторите
                    создание потока 2 или поправьте остальное в Keitaro.
                  </div>
                </div>
              ) : (
                <div className="note ok" role="status">
                  <span className="grow">Кампания «{report.name}» создана в Keitaro. Откройте редактор, чтобы добавлять офферы.</span>
                </div>
              )}
              {error && (
                <div className="note err" role="alert">
                  <div className="grow">{error}</div>
                </div>
              )}
              <div className="btns">
                {failed && report.campaign_id && (
                  <button className="btn primary" onClick={retryStream2}>
                    Повторить создание потока 2
                  </button>
                )}
                {report.campaign_id && (
                  <button className={`btn${failed ? "" : " primary"}`} onClick={() => void onOpenCampaign(report.campaign_id as number)}>
                    Открыть в редакторе
                  </button>
                )}
                <button className="btn" onClick={startOver}>
                  Создать ещё одну
                </button>
              </div>
            </>
          )}
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <h1>Новая кампания</h1>
        <div className="meta">Название, страна и оффер. Остальное подставим сами.</div>
      </div>

      {error && (
        <div className="note err" role="alert">
          <div className="grow">{error}</div>
        </div>
      )}

      <div className="cwrap">
        <form className="form" onSubmit={submit} noValidate>
          <div className="field">
            <label htmlFor={ids.name}>Название кампании</label>
            <input id={ids.name} value={name} autoComplete="off" onChange={(e) => setName(e.target.value)} />
            <div className="hint">{alias ? `Алиас: ${alias} (изменить можно в Keitaro)` : "Алиас построится из названия"}</div>
          </div>

          <div className="field">
            <label htmlFor={ids.geo}>Страна (код)</label>
            <input
              id={ids.geo}
              value={geo}
              maxLength={2}
              placeholder="AU"
              autoComplete="off"
              onChange={(e) => setGeo(e.target.value.toUpperCase())}
            />
            <div className={`hint${geoHint.bad ? " bad" : ""}`}>{geoHint.text}</div>
          </div>

          <div className="field">
            <label htmlFor={ids.offer}>Оффер</label>
            <input
              id={ids.offer}
              value={offerInput}
              placeholder="ID оффера"
              autoComplete="off"
              onChange={(e) => setOfferInput(e.target.value)}
            />
            <div className={`hint${offerHint.bad ? " bad" : ""}`}>{offerHint.text}</div>
          </div>

          <div className="selrow">
            <RefSelect id={ids.domain} label="Домен" value={domainId} items={refs?.domains} onChange={setDomainId} />
            <RefSelect id={ids.group} label="Группа" value={groupId} items={refs?.groups} onChange={setGroupId} />
            <RefSelect id={ids.source} label="Источник" value={sourceId} items={refs?.sources} onChange={setSourceId} />
          </div>
          <div className="field">
            <div className="hint">
              Подставили значения по умолчанию. Любое поле можно оставить «Не выбрано»: кампанию создадим без него, задать можно позже в Keitaro.
            </div>
            {refs && refs.defaults.missing.length > 0 && (
              <div className="hint bad">В Keitaro не нашли значения по умолчанию: {refs.defaults.missing.join(", ")}.</div>
            )}
          </div>

          <div className="btns">
            <button className="btn primary" type="submit" disabled={!valid}>
              Создать кампанию
            </button>
          </div>
        </form>

        <aside className="cprev" aria-label="Что будет создано">
          <h2>Что будет создано в Keitaro</h2>
          <div className="pv">
            <span className="pk">Кампания</span>
            <strong>{name.trim() || "Название кампании"}</strong>
            <span className="pm">
              алиас {alias || "алиас"} · домен {nameOf(refs?.domains, domainId) ?? "не задан"} · группа{" "}
              {nameOf(refs?.groups, groupId) ?? "не задана"} · источник {nameOf(refs?.sources, sourceId) ?? "не задан"} · ротация по весу
            </span>
          </div>
          <div className="pv">
            <span className="pk">Поток 1</span>
            <span>
              Страна <strong>{geoOk ? geo.toUpperCase() : "страна"}</strong> принимается, редирект на https://google.com
            </span>
          </div>
          <div className="pv">
            <span className="pk">Поток 2</span>
            <span>
              Все остальные идут на{" "}
              {offer ? (
                <strong>
                  {offer.offer_id} {offer.name}
                </strong>
              ) : (
                <strong>оффер</strong>
              )}
              , доля 100%
            </span>
          </div>
        </aside>
      </div>
    </>
  );
}

function RefSelect(props: {
  id: string;
  label: string;
  value: string;
  items: { id: number; name: string }[] | undefined;
  onChange: (value: string) => void;
}) {
  return (
    <div className="field">
      <label htmlFor={props.id}>{props.label}</label>
      <select id={props.id} value={props.value} onChange={(e) => props.onChange(e.target.value)}>
        <option value="">Не выбрано</option>
        {props.items?.map((item) => (
          <option key={item.id} value={String(item.id)}>
            {item.name}
          </option>
        ))}
      </select>
    </div>
  );
}
