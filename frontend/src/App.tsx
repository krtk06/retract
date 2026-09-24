import { Navigate, Route, Routes } from "react-router-dom";

import { useMe } from "./api/hooks";
import { Layout } from "./components/Layout";
import { AnalysisDetailPage } from "./pages/AnalysisDetailPage";
import { LoginPage } from "./pages/LoginPage";
import { ReposPage } from "./pages/ReposPage";

export default function App() {
  const me = useMe();

  if (me.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-zinc-400">
        Loading…
      </div>
    );
  }

  if (me.isError || !me.data) {
    return <LoginPage />;
  }

  return (
    <Layout user={me.data}>
      <Routes>
        <Route path="/" element={<ReposPage />} />
        <Route path="/analyses/:id" element={<AnalysisDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
