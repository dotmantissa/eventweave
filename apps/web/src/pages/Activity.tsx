import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { usePrivy } from "@privy-io/react-auth";
import { ExternalLink, RefreshCw, Mail } from "lucide-react";
import { api, request } from "../api";
import { useOperation } from "../use-operation";
import { type Operation } from "@eventweave/protocol";
import { Status, Notice, Empty, PageIntro, Feedback } from "../components/ui";

export default function Activity() {
  const { authenticated, login, getAccessToken } = usePrivy();
  const [items, setItems] = useState<Operation[]>([]);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const op = useOperation();
  useEffect(() => {
    if (!authenticated) return;
    let mounted = true;
    getAccessToken()
      .then((t) => api.activity(t!))
      .then((d) => {
        if (mounted) {
          setItems(d.items);
          setError("");
        }
      })
      .catch((e) => {
        if (mounted) setError(e.message);
      });
    const timer = setTimeout(() => setRefresh((x) => x + 1), 10000);
    return () => {
      mounted = false;
      clearTimeout(timer);
    };
  }, [authenticated, getAccessToken, refresh]);
  async function assess(item: Operation) {
    try {
      const detail = await request<{ args: string[] }>(
        "/operations/" + item.operation_id,
        { headers: { Authorization: "Bearer " + (await getAccessToken()) } },
      );
      const parsed = JSON.parse(detail.args[0]);
      await op.run("court", "assess", [parsed.envelope.request_id]);
      setRefresh((x) => x + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assessment could not start.");
    }
  }
  return (
    <div className="page">
      <PageIntro
        title="Follow the thread."
        action={
          <button
            className="button button-outline"
            onClick={() => setRefresh((x) => x + 1)}
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        }
      >
        Signed requests, network decisions and delivery acknowledgements.
        Pending is progress, not permission.
      </PageIntro>
      {!authenticated ? (
        <Empty title="Your activity is yours.">
          <button className="button button-primary" onClick={() => login()}>
            <Mail size={17} />
            Sign in with email
          </button>
        </Empty>
      ) : error ? (
        <Notice error>{error}</Notice>
      ) : items.length ? (
        <div className="activity-ledger">
          {items.map((item) => (
            <article className="activity-row" key={item.operation_id}>
              <div>
                <h3>{item.method.replaceAll("_", " ")}</h3>
                <p className="hash-text">{item.operation_id}</p>
                <small>{new Date(item.created_at).toLocaleString()}</small>
              </div>
              <Status status={item.status} />
              <div className="activity-actions">
                {item.transaction_hash && (
                  <a
                    className="source-link"
                    href={
                      "https://studio.genlayer.com/transactions/" +
                      item.transaction_hash
                    }
                    target="_blank"
                    rel="noreferrer"
                  >
                    Receipt <ExternalLink size={14} />
                  </a>
                )}
                {item.method === "compare_records" &&
                  item.status === "finalized" && (
                    <button
                      className="button button-outline"
                      disabled={op.busy}
                      onClick={() => assess(item)}
                    >
                      Assess records
                    </button>
                  )}
                {item.method === "compare_records" && item.args && (
                  <Link
                    className="source-link"
                    to={
                      "/workspace?request=" +
                      JSON.parse(String(item.args[0])).envelope.request_id
                    }
                  >
                    Open docket
                  </Link>
                )}
                {["assess", "publish_alias", "retry_delivery"].includes(
                  item.method,
                ) &&
                  item.args && (
                    <Link
                      className="source-link"
                      to={"/workspace?request=" + String(item.args[0])}
                    >
                      Read decision and delivery
                    </Link>
                  )}
                {item.error && (
                  <span className="operation-error">{item.error}</span>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="No loose ends yet.">
          Your signed requests will appear here when you register, compare or
          challenge a record.
        </Empty>
      )}
      <Feedback message={op.message} />
    </div>
  );
}
