import { useEffect, useState } from "react";
import { api } from "../api";
import { type Identity } from "@eventweave/protocol";

export function useEvents(q = "", kind = "") {
  const [items, setItems] = useState<Identity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [total, setTotal] = useState(0);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      api
        .events(q, kind, controller.signal)
        .then((data) => {
          setItems(data.items);
          setTotal(data.total);
          setError("");
        })
        .catch((e) => {
          if (!controller.signal.aborted) setError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 200);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [q, kind, refresh]);
  return {
    items,
    loading,
    error,
    total,
    reload: () => setRefresh((x) => x + 1),
  };
}
