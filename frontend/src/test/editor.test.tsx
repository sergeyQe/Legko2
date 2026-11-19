import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CampaignEditorPage } from "../pages/CampaignEditorPage";
import { campaign, offer, preview, stream } from "./fixtures";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  const fn = () => vi.fn();
  return {
    ...actual,
    api: {
      campaign: fn(), fetchCampaign: fn(), addOffer: fn(), removeOffer: fn(), restoreOffer: fn(), pinOffer: fn(),
      cancelStream: fn(), preview: fn(), push: fn(), searchOffers: fn(),
    },
  };
});

import { ApiError, api } from "../api/client";

const mocked = vi.mocked(api);

const clean = stream(2, [offer(11109, 33), offer(11110, 33), offer(11111, 34)]);
const afterAdd = stream(
  2,
  [offer(11109, 25, { kt_weight: 33 }), offer(11110, 25, { kt_weight: 33 }), offer(11111, 25, { kt_weight: 34 }), offer(11112, 25, { state: "added", kt_weight: 0 })],
  { dirty: true },
);

function open() {
  return render(<CampaignEditorPage campaignId={1} keitaroUrl="" />);
}

beforeEach(() => {
  vi.resetAllMocks();
  mocked.campaign.mockResolvedValue(campaign([stream(1, []), clean]));
  mocked.searchOffers.mockResolvedValue([]);
});

describe("редактор кампании", () => {
  it("показывает потоки: пустой без содержимого, второй с долями и суммой 100%", async () => {
    open();
    expect(await screen.findByText("campaign 2", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("без офферов")).toBeInTheDocument();
    expect(screen.getByTestId("offer-11109")).toHaveTextContent("33%");
    expect(screen.getByTestId("offer-11111")).toHaveTextContent("34%");
    expect(screen.getByText(/100% ✓/)).toBeInTheDocument();
    expect(screen.getByText("Опубликован")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отправить в KT" })).not.toBeInTheDocument();
  });

  it("если потоки ещё не загружали, загружает их из Keitaro", async () => {
    mocked.campaign.mockResolvedValue({ ...campaign([]), fetched_at: null });
    mocked.fetchCampaign.mockResolvedValue(campaign([stream(1, []), clean]));
    open();
    expect(await screen.findByTestId("stream-2")).toBeInTheDocument();
    expect(mocked.fetchCampaign).toHaveBeenCalledWith(1);
  });

  it("при ошибке загрузки показывает сообщение", async () => {
    mocked.campaign.mockRejectedValue(new ApiError(502, "KEITARO_UNREACHABLE", "Keitaro не отвечает."));
    open();
    expect(await screen.findByRole("alert")).toHaveTextContent("Keitaro не отвечает.");
  });

  it("добавление оффера: поток становится неопубликованным, появляются кнопки отправки и отмены", async () => {
    mocked.addOffer.mockResolvedValue(afterAdd);
    const user = userEvent.setup();
    open();
    await screen.findByTestId("stream-2");

    await user.type(screen.getByRole("combobox", { name: "ID или название оффера" }), "11112");
    await user.click(screen.getByRole("button", { name: "Добавить" }));

    expect(mocked.addOffer).toHaveBeenCalledWith(2, 11112);
    expect(await screen.findByText("Не опубликован")).toBeInTheDocument();
    expect(screen.getByTestId("offer-11112")).toHaveTextContent("25%");
    expect(screen.getByText("добавлен")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отправить в KT" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Отменить изменения" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("В Keitaro ничего не изменилось");
  });

  it("добавление по названию, если найден один оффер", async () => {
    mocked.searchOffers.mockResolvedValue([{ offer_id: 11112, name: "Oxys BE", geo: "Бельгия" }]);
    mocked.addOffer.mockResolvedValue(afterAdd);
    const user = userEvent.setup();
    open();
    await screen.findByTestId("stream-2");
    await user.type(screen.getByRole("combobox", { name: "ID или название оффера" }), "Oxys");
    await user.click(screen.getByRole("button", { name: "Добавить" }));
    expect(mocked.addOffer).toHaveBeenCalledWith(2, 11112);
  });

  it("не отправляет запрос, если оффер не выбран", async () => {
    const user = userEvent.setup();
    open();
    await screen.findByTestId("stream-2");
    await user.type(screen.getByRole("combobox", { name: "ID или название оффера" }), "что-то");
    await user.click(screen.getByRole("button", { name: "Добавить" }));
    expect(mocked.addOffer).not.toHaveBeenCalled();
    expect(await screen.findByRole("status")).toHaveTextContent("Введите ID оффера");
  });

  it("показывает ошибку сервера при добавлении", async () => {
    mocked.addOffer.mockRejectedValue(new ApiError(409, "OFFER_STATE_ERROR", "Оффер 11109 уже есть в потоке."));
    const user = userEvent.setup();
    open();
    await screen.findByTestId("stream-2");
    await user.type(screen.getByRole("combobox", { name: "ID или название оффера" }), "11109");
    await user.click(screen.getByRole("button", { name: "Добавить" }));
    expect(await screen.findByText("Оффер 11109 уже есть в потоке.")).toBeInTheDocument();
  });

  it("закрепление, убирание и возврат вызывают API", async () => {
    mocked.pinOffer.mockResolvedValue(clean);
    mocked.removeOffer.mockResolvedValue(clean);
    mocked.restoreOffer.mockResolvedValue(clean);
    const user = userEvent.setup();
    open();
    await screen.findByTestId("stream-2");

    await user.click(within(screen.getByTestId("offer-11109")).getByRole("button", { name: /Закрепить вес/ }));
    expect(mocked.pinOffer).toHaveBeenCalledWith(2, 11109, true);

    await user.click(within(screen.getByTestId("offer-11110")).getByRole("button", { name: "Убрать из потока" }));
    expect(mocked.removeOffer).toHaveBeenCalledWith(2, 11110);
  });

  it("убранный оффер серый, с кнопкой «Вернуть в поток» и без закрепления", async () => {
    const removing = stream(2, [offer(11109, 0, { state: "removing", kt_weight: 33 }), offer(11110, 50, { kt_weight: 33 }), offer(11111, 50, { kt_weight: 34 })], { dirty: true });
    mocked.campaign.mockResolvedValue(campaign([removing]));
    mocked.restoreOffer.mockResolvedValue(clean);
    const user = userEvent.setup();
    open();
    const row = await screen.findByTestId("offer-11109");
    expect(row).toHaveClass("gone");
    expect(within(row).queryByRole("button", { name: /Закрепить/ })).not.toBeInTheDocument();
    await user.click(within(row).getByRole("button", { name: "Вернуть в поток" }));
    expect(mocked.restoreOffer).toHaveBeenCalledWith(2, 11109);
  });

  it("отмена изменений возвращает поток к опубликованному виду", async () => {
    mocked.campaign.mockResolvedValue(campaign([afterAdd]));
    mocked.cancelStream.mockResolvedValue(clean);
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Отменить изменения" }));
    expect(mocked.cancelStream).toHaveBeenCalledWith(2);
    expect(await screen.findByText("Опубликован")).toBeInTheDocument();
    expect(screen.queryByTestId("offer-11112")).not.toBeInTheDocument();
  });

  it("загрузка потоков из KT обновляет кампанию", async () => {
    mocked.fetchCampaign.mockResolvedValue(campaign([stream(2, [offer(11109, 100)])]));
    const user = userEvent.setup();
    open();
    await screen.findByTestId("stream-2");
    await user.click(screen.getByRole("button", { name: "Загрузить потоки из KT" }));
    await waitFor(() => expect(screen.queryByTestId("offer-11110")).not.toBeInTheDocument());
    expect(screen.getByTestId("offer-11109")).toHaveTextContent("100%");
  });

  it("предупреждает о merge и не обещает ссылку на Keitaro в режиме mock", async () => {
    open();
    await screen.findByTestId("stream-2");
    expect(screen.getByText(/Не меняйте поток в Keitaro/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Кампания в Keitaro/ })).toBeDisabled();
  });
});

describe("отправка в Keitaro", () => {
  beforeEach(() => {
    mocked.campaign.mockResolvedValue(campaign([afterAdd]));
  });

  it("предпросмотр, затем отправка", async () => {
    const sentStream = stream(2, [offer(11109, 25), offer(11110, 25), offer(11111, 25), offer(11112, 25)]);
    mocked.preview.mockResolvedValue(
      preview(afterAdd, {
        keitaro_offers: [
          { offer_id: 11109, name: "О", geo: "", weight: 33 },
          { offer_id: 11110, name: "О", geo: "", weight: 33 },
          { offer_id: 11111, name: "О", geo: "", weight: 34 },
        ],
        changes: [
          { kind: "add", offer_id: 11112, name: "Оффер 11112", from_weight: null, to_weight: 25, note: "новый оффер в потоке" },
          { kind: "change", offer_id: 11109, name: "Оффер 11109", from_weight: 33, to_weight: 25, note: "пересчёт долей" },
        ],
      }),
    );
    mocked.push.mockResolvedValue(sentStream);
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole("button", { name: "Отправить в KT" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Отправить «Поток 2» в Keitaro?")).toBeInTheDocument();
    expect(within(dialog).getByText("Сейчас в Keitaro")).toBeInTheDocument();
    expect(within(dialog).getByText("+1 добавится")).toBeInTheDocument();
    expect(within(dialog).getByText("~1 изменится вес")).toBeInTheDocument();
    expect(mocked.preview).toHaveBeenCalledWith(2, {});

    await user.click(within(dialog).getByRole("button", { name: "Отправить в KT" }));
    expect(mocked.push).toHaveBeenCalledWith(2, {});
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(await screen.findByText("Опубликован")).toBeInTheDocument();
  });

  it("кнопка отправки заблокирована, если предпросмотр не разрешает отправку", async () => {
    mocked.preview.mockResolvedValue(preview(afterAdd, { can_push: false }));
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Отправить в KT" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("Отправить «Поток 2» в Keitaro?");
    expect(within(dialog).getByRole("button", { name: "Отправить в KT" })).toBeDisabled();
  });

  it("если активных офферов нет, диалог объясняет, почему отправить нельзя", async () => {
    const empty = stream(2, [offer(11109, 0, { state: "removing", kt_weight: 100 })], { dirty: true });
    mocked.campaign.mockResolvedValue(campaign([empty]));
    mocked.preview.mockResolvedValue(preview(empty, { can_push: false }));
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Отправить в KT" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(/не осталось активных офферов/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Отправить в KT" })).toBeDisabled();
  });

  it("ошибка отправки: диалог закрывается, на потоке плашка с причиной и «Повторить», черновик цел", async () => {
    mocked.preview.mockResolvedValue(preview(afterAdd));
    mocked.push.mockRejectedValueOnce(new ApiError(502, "KEITARO_UNREACHABLE", "Keitaro не отвечает."));
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Отправить в KT" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(await within(dialog).findByRole("button", { name: "Отправить в KT" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    const banner = screen.getByRole("alert");
    expect(banner).toHaveTextContent("Не отправлено.");
    expect(banner).toHaveTextContent("Keitaro не отвечает.");
    expect(screen.getByText("Не опубликован")).toBeInTheDocument();

    // повтор проходит
    mocked.push.mockResolvedValueOnce(stream(2, [offer(11109, 25), offer(11110, 25), offer(11111, 25), offer(11112, 25)]));
    await user.click(within(banner).getByRole("button", { name: "Повторить" }));
    expect(await screen.findByText("Опубликован")).toBeInTheDocument();
    expect(screen.queryByText("Не отправлено.")).not.toBeInTheDocument();
  });

  it("спорный пункт: решение нужно выбрать, после выбора можно перейти к проверке и отправить с решением", async () => {
    const key = "11110:weight_changed_removed";
    const conflict = { key, kind: "conflict" as const, offer_id: 11110, message: "Оффер 11110 убран в черновике, а в Keitaro у него изменили вес.", resolution: null };
    const auto = { key: "11120:added_in_kt", kind: "auto" as const, offer_id: 11120, message: "Оффер 11120 добавлен в Keitaro.", resolution: null };
    mocked.preview.mockImplementation(async (_id, resolutions = {}) =>
      resolutions[key]
        ? preview(afterAdd, { merge_items: [{ ...conflict, resolution: resolutions[key] }, auto], unresolved: [] })
        : preview(afterAdd, { merge_items: [conflict, auto], unresolved: [conflict], can_push: false }),
    );
    mocked.push.mockResolvedValue(stream(2, [offer(11109, 100)]));
    const user = userEvent.setup();
    open();

    await user.click(await screen.findByRole("button", { name: "Отправить в KT" }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("В Keitaro поток изменили после загрузки")).toBeInTheDocument();
    expect(within(dialog).getByText(/Оффер 11120 добавлен в Keitaro/)).toBeInTheDocument();
    expect(within(dialog).getByText("Нужно ваше решение")).toBeInTheDocument();
    const next = within(dialog).getByRole("button", { name: "Далее: проверить" });
    expect(next).toBeDisabled();

    await user.click(within(dialog).getByRole("radio", { name: /Оставить убранным/ }));
    await waitFor(() => expect(next).toBeEnabled());
    expect(mocked.preview).toHaveBeenCalledWith(2, { [key]: "draft" });

    await user.click(next);
    expect(await within(dialog).findByText("Отправить «Поток 2» в Keitaro?")).toBeInTheDocument();
    expect(within(dialog).getByText("Учтено объединение с Keitaro")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Отправить в KT" }));
    expect(mocked.push).toHaveBeenCalledWith(2, { [key]: "draft" });
  });

  it("не выпускает фокус за пределы диалога при нажатии Tab", async () => {
    mocked.preview.mockResolvedValue(preview(afterAdd));
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Отправить в KT" }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("Отправить «Поток 2» в Keitaro?");
    for (let i = 0; i < 6; i++) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
    for (let i = 0; i < 3; i++) {
      await user.tab({ shift: true });
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  it("закрывается по Esc и по кнопке «Назад»", async () => {
    mocked.preview.mockResolvedValue(preview(afterAdd));
    const user = userEvent.setup();
    open();
    await user.click(await screen.findByRole("button", { name: "Отправить в KT" }));
    await screen.findByRole("dialog");
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Отправить в KT" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Назад" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
