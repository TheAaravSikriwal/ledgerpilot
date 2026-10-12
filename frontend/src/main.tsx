import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./App";
import "./index.css";
import { LiveSyncProvider } from "./lib/live";

const queryClient = new QueryClient({
  defaultOptions: {
    // Retries cover the few seconds the backend needs on first run to build the demo data.
    queries: { staleTime: 15_000, refetchOnWindowFocus: false, retry: 4 },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <LiveSyncProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </LiveSyncProvider>
    </QueryClientProvider>
  </StrictMode>,
);
