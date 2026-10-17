import { Navigate, Route, Routes } from "react-router-dom";

import { useMe } from "./api/hooks";
import { Layout } from "./components/Layout";
import { PixelIcon } from "./components/PixelIcon";
import { AnalysisDetailPage } from "./pages/AnalysisDetailPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ReposPage } from "./pages/ReposPage";

function Splash() {
  return (
    <div className="grid min-h-[100dvh] place-items-center bg-canvas">
      <div className="px-well flex flex-col items-center gap-3 p-8">
        <span className="anim-blink block text-accent">
          <PixelIcon name="logo" size={24} />
        </span>
        <p className="px-eyebrow">Loading workspace</p>
      </div>
    </div>
  );
}

export default function App() {
  const me = useMe();

  if (me.isLoading) {
    return <Splash />;
  }

  if (me.isError || !me.data) {
    return <LoginPage />;
  }

  return (
    <Layout user={me.data}>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/repos" element={<ReposPage />} />
        <Route path="/analyses/:id" element={<AnalysisDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
