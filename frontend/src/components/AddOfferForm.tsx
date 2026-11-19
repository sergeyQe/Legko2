/** Форма добавления оффера: поле с подсказками из базы Keitaro и кнопка «Добавить». */
import { FormEvent, useEffect, useId, useState } from "react";

import { api } from "../api/client";
import type { OfferSearchResult } from "../api/types";
import { parseOfferId } from "../lib/format";

const SEARCH_DELAY_MS = 250; // пауза после ввода перед поиском

interface Props {
  disabled: boolean;
  onAdd: (offerId: number) => Promise<boolean>; // true — оффер добавлен, поле можно очистить
  onProblem: (message: string) => void; // сообщение о неверном вводе
}

export function AddOfferForm({ disabled, onAdd, onProblem }: Props) {
  const [value, setValue] = useState("");
  const [options, setOptions] = useState<OfferSearchResult[]>([]);
  const listId = useId();

  // подсказки: ищем в базе Keitaro после небольшой паузы
  useEffect(() => {
    const query = value.trim();
    if (query.length < 2) {
      setOptions([]);
      return;
    }
    const timer = setTimeout(() => {
      api.searchOffers(query).then(setOptions).catch(() => setOptions([]));
    }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [value]);

  async function submit(event: FormEvent) {
    event.preventDefault();

    // определяем оффер: число из ввода или единственный найденный по названию
    let offerId = parseOfferId(value);
    if (offerId === null) {
      const found = value.trim() ? await api.searchOffers(value.trim()).catch(() => []) : [];
      if (found.length === 1) offerId = found[0].offer_id;
      else {
        onProblem(found.length === 0 ? "Введите ID оффера или выберите оффер из подсказок." : "Нашлось несколько офферов: выберите один из подсказок.");
        return;
      }
    }

    if (await onAdd(offerId)) setValue("");
  }

  return (
    <form className="add-row" onSubmit={submit}>
      <input
        type="text"
        value={value}
        list={listId}
        placeholder="ID или название оффера"
        aria-label="ID или название оффера"
        autoComplete="off"
        onChange={(e) => setValue(e.target.value)}
      />
      <datalist id={listId}>
        {options.map((o) => (
          <option key={o.offer_id} value={String(o.offer_id)}>
            {o.name}
          </option>
        ))}
      </datalist>
      <button className="btn" type="submit" disabled={disabled}>
        Добавить
      </button>
    </form>
  );
}
