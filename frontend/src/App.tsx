/** Каркас приложения: шапка, навигация, тема, демо-панель и выбор страницы по адресу. */
import { useCallback, useEffect, useState } from "react";

import { api } from "./api/client";
import type { Meta } from "./api/types";
import { DemoPanel } from "./components/DemoPanel";
import { useRoute } from "./lib/route";
import { themeLabel, useTheme } from "./lib/theme";
import { CampaignEditorPage } from "./pages/CampaignEditorPage";
import { CampaignListPage } from "./pages/CampaignListPage";
import { CreateCampaignPage } from "./pages/CreateCampaignPage";

export function App() {
  const [route, navigate] = useRoute();
  const [theme, cycleTheme] = useTheme();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [epoch, setEpoch] = useState(0); // меняется после сброса демо: страницы загружаются заново

  useEffect(() => {
    api.meta().then(setMeta).catch(() => setMeta(null));
  }, []);

  // после создания кампании находим её внутренний ID и открываем редактор
  const openCampaignByKeitaroId = useCallback(
    async (keitaroId: number) => {
      const campaigns = await api.campaigns();
      const found = campaigns.find((c) => c.keitaro_id === keitaroId);
      navigate(found ? `/campaign/${found.id}` : "/campaigns");
    },
    [navigate],
  );

  const current = route.name === "campaign" ? "editor" : route.name;

  return (
    <div className="app">
      {meta?.mode === "mock" && (
        <DemoPanel
          onReset={() => {
            // после сброса ID кампаний меняются: из редактора уходим к списку (он загрузится заново),
            // на других страницах просто перезагружаем данные
            if (route.name === "campaign") navigate("/campaigns");
            else setEpoch((n) => n + 1);
          }}
        />
      )}
      <div className="shell">
        <header className="top">
          <span className="brand">Adrobot · Keitaro</span>
          <nav className="nav" aria-label="Разделы">
            <button aria-current={current === "campaigns" ? "page" : undefined} onClick={() => navigate("/campaigns")}>
              Кампании
            </button>
            <button aria-current={current === "create" ? "page" : undefined} onClick={() => navigate("/create")}>
              Создать кампанию
            </button>
          </nav>
          <button className="btn sm spacer" onClick={cycleTheme}>
            {themeLabel(theme)}
          </button>
        </header>

        <main className="main" key={epoch}>
          {route.name === "campaigns" && (
            <CampaignListPage onOpen={(id) => navigate(`/campaign/${id}`)} onCreate={() => navigate("/create")} />
          )}
          {route.name === "campaign" && (
            <CampaignEditorPage campaignId={route.id} keitaroUrl={meta?.keitaro_url ?? ""} onBack={() => navigate("/campaigns")} />
          )}
          {route.name === "create" && <CreateCampaignPage onOpenCampaign={openCampaignByKeitaroId} />}
        </main>
      </div>
    </div>
  );
}
