import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CreateReport, References } from "../api/types";
import { CreateCampaignPage } from "../pages/CreateCampaignPage";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    api: { references: vi.fn(), searchOffers: vi.fn(), createCampaign: vi.fn(), retryStream2: vi.fn() },
  };
});

import { ApiError, api } from "../api/client";

const mocked = vi.mocked(api);

const refs: References = {
  domains: [{ id: 1, name: "in.posdk.xyz" }, { id: 2, name: "go.demo-track.net" }],
  groups: [{ id: 1, name: "FORTESTS" }],
  sources: [{ id: 1, name: "FORTESTS" }],
  defaults: { domain_id: 1, group_id: 1, source_id: 1, missing: [] },
};

const okReport: CreateReport = {
  ok: true,
  campaign_id: 93301,
  name: "Тест кампания",
  alias: "test-kampaniya",
  steps: [
    { name: "campaign", description: "Кампания «Тест кампания» (алиас test-kampaniya)", status: "ok", error: null },
    { name: "stream1", description: "Поток 1: страна AU принимается, редирект на https://google.com", status: "ok", error: null },
    { name: "stream2", description: "Поток 2: оффер 11112, доля 100%", status: "ok", error: null },
  ],
};

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Название кампании"), "Тест кампания");
  await user.type(screen.getByLabelText("Страна (код)"), "au");
  await user.type(screen.getByLabelText("Оффер"), "11112");
  await screen.findByText(/Oxys BE · Бельгия/);
}

beforeEach(() => {
  vi.resetAllMocks();
  mocked.references.mockResolvedValue(refs);
  mocked.searchOffers.mockResolvedValue([{ offer_id: 11112, name: "Oxys BE", geo: "Бельгия" }]);
});

describe("создание кампании", () => {
  it("значения по умолчанию подставлены, а кнопка заблокирована, пока форма не заполнена", async () => {
    render(<CreateCampaignPage onOpenCampaign={vi.fn()} />);
    await waitFor(() => expect(screen.getByLabelText("Домен")).toHaveValue("1"));
    expect(screen.getByLabelText("Группа")).toHaveValue("1");
    expect(screen.getByLabelText("Источник")).toHaveValue("1");
    expect(screen.getByRole("button", { name: "Создать кампанию" })).toBeDisabled();
  });

  it("код страны приводится к верхнему регистру, показывается название страны и алиас", async () => {
    const user = userEvent.setup();
    render(<CreateCampaignPage onOpenCampaign={vi.fn()} />);
    await user.type(screen.getByLabelText("Страна (код)"), "au");
    expect(screen.getByLabelText("Страна (код)")).toHaveValue("AU");
    expect(screen.getByText("Австралия")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Название кампании"), "Тест кампания");
    expect(screen.getByText(/Алиас: test-kampaniya/)).toBeInTheDocument();
  });

  it("неверный код страны подсвечивается", async () => {
    const user = userEvent.setup();
    render(<CreateCampaignPage onOpenCampaign={vi.fn()} />);
    await user.type(screen.getByLabelText("Страна (код)"), "A");
    expect(screen.getByText("Нужны две латинские буквы")).toHaveClass("bad");
  });

  it("находит оффер и показывает его название; неизвестный оффер помечается", async () => {
    const user = userEvent.setup();
    render(<CreateCampaignPage onOpenCampaign={vi.fn()} />);
    await user.type(screen.getByLabelText("Оффер"), "11112");
    expect(await screen.findByText(/Oxys BE · Бельгия/)).toBeInTheDocument();

    mocked.searchOffers.mockResolvedValue([]);
    await user.clear(screen.getByLabelText("Оффер"));
    await user.type(screen.getByLabelText("Оффер"), "99999");
    expect(await screen.findByText("Оффер не найден в Keitaro")).toHaveClass("bad");
  });

  it("предпросмотр отражает ввод и выбор справочников, «Не выбрано» допустимо", async () => {
    const user = userEvent.setup();
    render(<CreateCampaignPage onOpenCampaign={vi.fn()} />);
    await waitFor(() => expect(screen.getByLabelText("Домен")).toHaveValue("1"));
    await fillValidForm(user);
    const preview = screen.getByLabelText("Что будет создано");
    expect(preview).toHaveTextContent("домен in.posdk.xyz");
    expect(preview).toHaveTextContent("Страна AU принимается");

    await user.selectOptions(screen.getByLabelText("Домен"), "");
    expect(preview).toHaveTextContent("домен не задан");
    expect(screen.getByRole("button", { name: "Создать кампанию" })).toBeEnabled();
  });

  it("успешное создание отправляет выбранные значения и показывает итог", async () => {
    mocked.createCampaign.mockResolvedValue(okReport);
    const onOpen = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<CreateCampaignPage onOpenCampaign={onOpen} />);
    await waitFor(() => expect(screen.getByLabelText("Домен")).toHaveValue("1"));
    await fillValidForm(user);
    await user.selectOptions(screen.getByLabelText("Источник"), "");
    await user.click(screen.getByRole("button", { name: "Создать кампанию" }));

    expect(mocked.createCampaign).toHaveBeenCalledWith({
      name: "Тест кампания", geo: "AU", offer_id: 11112, domain_id: 1, group_id: 1, source_id: null,
    });
    expect(await screen.findByRole("heading", { name: "Кампания создана" })).toBeInTheDocument();
    expect(screen.getByText(/Поток 2: оффер 11112/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Открыть в редакторе" }));
    expect(onOpen).toHaveBeenCalledWith(93301);
  });

  it("частичное создание: показаны шаги и ошибка Keitaro, можно повторить поток 2", async () => {
    mocked.createCampaign.mockRejectedValue(
      new ApiError(502, "CREATE_PARTIAL", "Кампания создана не полностью.", {
        steps: [
          { name: "campaign", description: "Кампания", status: "ok", error: null },
          { name: "stream1", description: "Поток 1", status: "ok", error: null },
          { name: "stream2", description: "Поток 2", status: "failed", error: "Offer not found" },
        ],
        campaign_id: 93301,
        name: "Тест кампания",
        alias: "test-kampaniya",
      }),
    );
    mocked.retryStream2.mockResolvedValue(okReport);
    const user = userEvent.setup();
    render(<CreateCampaignPage onOpenCampaign={vi.fn()} />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Создать кампанию" }));

    expect(await screen.findByRole("heading", { name: "Кампания создана не полностью" })).toBeInTheDocument();
    expect(screen.getByText(/Ошибка Keitaro: Offer not found/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("не удаляли");

    await user.click(screen.getByRole("button", { name: "Повторить создание потока 2" }));
    expect(mocked.retryStream2).toHaveBeenCalledWith(93301, 11112, "Тест кампания", "test-kampaniya");
    expect(await screen.findByRole("heading", { name: "Кампания создана" })).toBeInTheDocument();
  });

  it("если сервер не прислал описания шагов, показываются запасные подписи", async () => {
    mocked.createCampaign.mockRejectedValue(
      new ApiError(502, "CREATE_PARTIAL", "Кампания создана не полностью.", {
        steps: [
          { name: "campaign", status: "ok", error: null },
          { name: "stream1", status: "ok", error: null },
          { name: "stream2", status: "failed", error: "Offer not found" },
        ],
        campaign_id: 1,
        name: "Тест",
        alias: "test",
      }),
    );
    const user = userEvent.setup();
    render(<CreateCampaignPage onOpenCampaign={vi.fn()} />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Создать кампанию" }));
    expect(await screen.findByText(/Поток 2: оффер, доля 100%/)).toBeInTheDocument();
    expect(screen.getByText("Кампания")).toBeInTheDocument();
  });

  it("обычная ошибка возвращает к форме с сообщением, введённое сохраняется", async () => {
    mocked.createCampaign.mockRejectedValue(new ApiError(422, "KEITARO_REJECTED", "Keitaro отклонил запрос. Причина: Alias already exists"));
    const user = userEvent.setup();
    render(<CreateCampaignPage onOpenCampaign={vi.fn()} />);
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Создать кампанию" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Alias already exists");
    expect(screen.getByLabelText("Название кампании")).toHaveValue("Тест кампания");
  });

  it("предупреждает, если значения по умолчанию не найдены в Keitaro", async () => {
    mocked.references.mockResolvedValue({ ...refs, defaults: { domain_id: null, group_id: 1, source_id: 1, missing: ["in.posdk.xyz"] } });
    render(<CreateCampaignPage onOpenCampaign={vi.fn()} />);
    expect(await screen.findByText(/не нашли значения по умолчанию: in\.posdk\.xyz/)).toBeInTheDocument();
    expect(screen.getByLabelText("Домен")).toHaveValue("");
  });
});
