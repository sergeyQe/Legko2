import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LABEL_MIN_WEIGHT, ShareBar } from "../components/ShareBar";

describe("ShareBar", () => {
  it("рисует сегмент на каждый оффер с весом больше нуля", () => {
    render(<ShareBar items={[{ weight: 25, pinned: false }, { weight: 25, pinned: true }, { weight: 0, pinned: false }, { weight: 50, pinned: false }]} />);
    const segments = screen.getAllByTestId("segment");
    expect(segments).toHaveLength(3);
    expect(segments.map((s) => (s as HTMLElement).style.flexGrow)).toEqual(["25", "25", "50"]);
  });

  it("помечает закреплённый вес", () => {
    render(<ShareBar items={[{ weight: 40, pinned: true }, { weight: 60, pinned: false }]} />);
    const [first, second] = screen.getAllByTestId("segment");
    expect(first).toHaveClass("pinned");
    expect(second).not.toHaveClass("pinned");
  });

  it("подписывает процент только в достаточно широких сегментах", () => {
    render(<ShareBar items={[{ weight: LABEL_MIN_WEIGHT - 1, pinned: false }, { weight: 100 - LABEL_MIN_WEIGHT + 1, pinned: false }]} />);
    const [small, big] = screen.getAllByTestId("segment");
    expect(small).toHaveTextContent("");
    expect(big).toHaveTextContent(`${100 - LABEL_MIN_WEIGHT + 1}%`);
  });

  it("описывает распределение для скринридеров", () => {
    render(<ShareBar items={[{ weight: 33, pinned: false }, { weight: 67, pinned: false }]} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Распределение долей: 33%, 67%");
  });

  it("при отсутствии активных офферов показывает пояснение", () => {
    render(<ShareBar items={[{ weight: 0, pinned: false }]} />);
    expect(screen.getByText("Нет активных офферов")).toBeInTheDocument();
  });
});
