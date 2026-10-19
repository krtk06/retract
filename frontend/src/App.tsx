import { Navigate, Route, Routes } from "react-router-dom";
import { Suspense, lazy } from "react";

import { useMe } from "./api/hooks";
import { Icon } from "./components/Icon";
import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ReposPage } from "./pages/ReposPage";

// The analysis workspace carries the motion library (the score reveal, the
// sliding tab rule). Lazy-loading the route keeps that weight off the dashboard
// path — the same trade as the eve client's chunk inside it.
const AnalysisDetailPage = lazy(() =>
  import("./pages/AnalysisDetailPage").then((module) => ({ default: module.AnalysisDetailPage })),
);

function Splash() {
  return (
    <div className="grid min-h-[100dvh] place-items-center bg-canvas">
      <div className="flex flex-col items-center gap-3">
        <span className="text-ink">
          <Icon name="logo" size={28} />
        </span>
        <p className="label">Loading workspace</p>
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
        <Route
          path="/"
          element={
            <Suspense fallback={null}>
              <DashboardPage />
            </Suspense>
          }
        />
        <Route
          path="/repos"
          element={
            <Suspense fallback={null}>
              <ReposPage />
            </Suspense>
          }
        />
        <Route
          path="/analyses/:id"
          element={
            <Suspense fallback={null}>
              <AnalysisDetailPage />
            </Suspense>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
