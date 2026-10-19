import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { LazyMotion, MotionConfig } from "motion/react";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { ThemeProvider } from "./components/ThemeProvider";
import "./index.css";

const queryClient = new QueryClient();

// The motion engine is its own chunk; nothing above the fold waits for it.
const loadFeatures = () => import("./lib/motionFeatures").then((mod) => mod.domMax);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* One motion contract for the tree. LazyMotion keeps the feature bundle
        out of the critical path and `m` components render static-first, so
        content is visible even before the features arrive. A visitor who asks
        their OS for less motion keeps opacity and color feedback and loses
        travel, scale and layout choreography everywhere at once. */}
    <LazyMotion features={loadFeatures} strict>
      <MotionConfig reducedMotion="user">
        <ThemeProvider>
          <QueryClientProvider client={queryClient}>
            <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
              <App />
            </BrowserRouter>
          </QueryClientProvider>
        </ThemeProvider>
      </MotionConfig>
    </LazyMotion>
  </StrictMode>,
);
