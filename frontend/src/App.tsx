/** Каркас приложения: шапка, навигация, тема и выбор страницы по адресу. */
import { useCallback, useEffect, useState } from "react";

import { api } from "./api/client";
import type { Meta } from "./api/types";
import { useRoute } from "./lib/route";
import { themeLabel, useTheme } from "./lib/theme";
import { CampaignEditorPage } from "./pages/CampaignEditorPage";
import { CampaignListPage } from "./pages/CampaignListPage";
import { CreateCampaignPage } from "./pages/CreateCampaignPage";

export function App() {
  const [route, navigate] = useRoute();
  const [theme, cycleTheme] = useTheme();
  const [meta, setMeta] = useState<Meta | null>(null);

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

        <main className="main">
          {route.name === "campaigns" && (
            <CampaignListPage onOpen={(id) => navigate(`/campaign/${id}`)} onCreate={() => navigate("/create")} />
          )}
          {route.name === "campaign" && (
            <CampaignEditorPage campaignId={route.id} keitaroUrl={meta?.keitaro_url ?? ""} onBack={() => navigate("/campaigns")} />
          )}
          {route.name === "create" && <CreateCampaignPage onOpenCampaign={openCampaignByKeitaroId} campaignPrefix={meta?.campaign_prefix ?? ""} />}
        </main>
      </div>
    </div>
  );
}
