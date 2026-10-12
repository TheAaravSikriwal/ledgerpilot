import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import type { SyncRun } from "./types";

// A sync that inserts more than this (e.g. a demo reset) is not "live" news worth highlighting.
const HIGHLIGHT_LIMIT = 25;
const HIGHLIGHT_MS = 6000;

interface LiveState {
  connected: boolean;
  newIds: ReadonlySet<number>;
  lastEvent: SyncRun | null;
  syncNow: () => void;
  syncing: boolean;
}

const LiveContext = createContext<LiveState | null>(null);

/** Subscribes to the backend's server-sent events and refreshes every query on change. */
export function LiveSyncProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);
  const [newIds, setNewIds] = useState<ReadonlySet<number>>(new Set());
  const [lastEvent, setLastEvent] = useState<SyncRun | null>(null);
  const clearTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    const source = new EventSource("/api/events");
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.addEventListener("sync", (event) => {
      const run = JSON.parse((event as MessageEvent).data) as SyncRun;
      setLastEvent(run);
      if (run.new_ids?.length && run.new_count <= HIGHLIGHT_LIMIT) {
        setNewIds(new Set(run.new_ids));
        window.clearTimeout(clearTimer.current);
        clearTimer.current = window.setTimeout(() => setNewIds(new Set()), HIGHLIGHT_MS);
      }
      void queryClient.invalidateQueries();
    });
    source.addEventListener("updated", () => void queryClient.invalidateQueries());
    return () => {
      source.close();
      window.clearTimeout(clearTimer.current);
    };
  }, [queryClient]);

  const sync = useMutation({ mutationFn: api.sync });

  return (
    <LiveContext.Provider
      value={{ connected, newIds, lastEvent, syncNow: () => sync.mutate(), syncing: sync.isPending }}
    >
      {children}
    </LiveContext.Provider>
  );
}

export function useLive(): LiveState {
  const ctx = useContext(LiveContext);
  if (!ctx) throw new Error("useLive must be used inside LiveSyncProvider");
  return ctx;
}
