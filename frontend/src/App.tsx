import { Navigate, Route, Routes } from "react-router-dom";

import { useMe } from "./api/hooks";
import { Layout } from "./components/Layout";
import { AnalysisDetailPage } from "./pages/AnalysisDetailPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ReposPage } from "./pages/ReposPage";

function Splash() {
  return (
    <div className="grid min-h-[100dvh] place-items-center">
      <div className="flex flex-col items-center gap-4">
        <span
          aria-hidden="true"
          className="anim-blink h-10 w-10"
          style={{
            background: "radial-gradient(circle at 35% 30%, var(--accent-strong), var(--accent))",
            boxShadow: "0 0 40px var(--accent-glow)",
          }}
        />
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
