import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { usePrivy } from "@privy-io/react-auth";
import { RefreshCw, GitMerge, Send, ShieldCheck } from "lucide-react";
import {
  type Docket,
  type MergeProposal,
  attributes,
} from "@eventweave/protocol";
import { request } from "../api";
import { useOperation } from "../use-operation";
import { Notice, Status, Feedback } from "./ui";

export function DocketFlow({ requestId }: { requestId: string }) {
  const [id, setId] = useState(requestId);
  const [docket, setDocket] = useState<Docket | null>(null);
  const [error, setError] = useState("");
  const [reading, setReading] = useState(false);
  const [relations, setRelations] = useState("");
  const [mergeId, setMergeId] = useState("");
  const [proposal, setProposal] = useState<MergeProposal | null>(null);
  const { getAccessToken } = usePrivy();
  const op = useOperation();
  async function inspect(e?: FormEvent) {
    e?.preventDefault();
    setReading(true);
    setError("");
    try {
      const value = await request<Docket>("/dockets/" + encodeURIComponent(id));
      setDocket(value);
      if (!relations) setRelations(id);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "This docket could not be read.",
      );
    } finally {
      setReading(false);
    }
  }
  async function act(
    method: string,
    args: string[],
    contract: "court" | "directory" = "court",
  ) {
    try {
      setError("");
      await op.run(contract, method, args);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "The request could not be sent.",
      );
    }
  }
  async function propose() {
    if (!docket) return;
    try {
      const value = await request<{ proof_json: string }>("/merges/prepare", {
        method: "POST",
        headers: { Authorization: "Bearer " + (await getAccessToken()) },
        body: JSON.stringify({
          left: docket.request.left,
          right: docket.request.right,
          relations: relations.split(/\s+/).filter(Boolean),
        }),
      });
      const proof = JSON.parse(value.proof_json) as { operation_id: string };
      await op.run("directory", "propose_merge", [value.proof_json]);
      setMergeId(proof.operation_id);
      setProposal(null);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "This proof could not be proposed.",
      );
    }
  }
  async function inspectMerge() {
    try {
      setProposal(
        await request<MergeProposal>("/merges/" + encodeURIComponent(mergeId)),
      );
      setError("");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "This merge is not available yet.",
      );
    }
  }
  const result = docket?.result;
  const finalized = docket?.delivery.status === "finalized";
  return (
    <section className="docket-flow" aria-labelledby="docket-heading">
      <h2 id="docket-heading">Pick up a comparison</h2>
      <p className="muted">
        Open a docket, check its decision, then carry the identity into an
        application.
      </p>
      <form className="lookup-form" onSubmit={inspect}>
        <label className="field">
          Comparison request ID
          <input
            required
            maxLength={128}
            value={id}
            onChange={(e) => {
              setId(e.target.value);
              setDocket(null);
              setProposal(null);
            }}
            placeholder="The ID from your comparison"
          />
        </label>
        <button className="button button-ink" disabled={reading}>
          <RefreshCw size={16} />
          {reading ? "Reading…" : "Read docket"}
        </button>
      </form>
      {docket && (
        <>
          <div className="docket-state">
            <div>
              <h3 className="hash-text">
                {docket.request.left} / {docket.request.right}
              </h3>
              <p>
                Generation {docket.request.envelope.generation}. Bound to the
                application and committed evidence.
              </p>
            </div>
            <Status
              status={docket.delivery.status || result?.status || "pending"}
            />
          </div>
          {!result ? (
            <div className="docket-actions">
              <p>No assessment has been recorded yet.</p>
              <button
                className="button button-primary"
                disabled={op.busy}
                onClick={() => act("assess", [id])}
              >
                <ShieldCheck size={17} />
                Assess committed records
              </button>
            </div>
          ) : (
            <>
              <div className="decision-vector">
                <Status status={result.decision} />
                <dl className="facts-list compact">
                  {attributes.map((a) => (
                    <div key={a}>
                      <dt>{a.replaceAll("_", " ")}</dt>
                      <dd>
                        <Status status={result.vector[a]} />
                        <small className="witness-list">
                          {result.witnesses[a]?.join(" / ")}
                        </small>
                      </dd>
                    </div>
                  ))}
                </dl>
                <p className="muted">
                  Rules: {result.controlling_rules.join(", ")}.{" "}
                  {result.unresolved
                    ? "Evidence remains incomplete. References stay reserved without reuse."
                    : "The decision covers the required evidence."}
                </p>
              </div>
              <div className="delivery-state">
                <span>Court delivery</span>
                <Status status={docket.delivery.status || "pending"} />
                <span>Application acknowledgement</span>
                <Status status={docket.consumer_ack.status || "pending"} />
              </div>
              {!docket.delivery.request_id && (
                <button
                  className="button button-outline"
                  disabled={op.busy}
                  onClick={() => act("retry_delivery", [id])}
                >
                  Retry finalized delivery
                </button>
              )}
              {finalized && result.decision === "SAME" && (
                <div className="merge-proof">
                  <h3>A complete proof, please.</h3>
                  <p className="muted">
                    Every pair in the combined cluster needs a current,
                    delivered SAME certificate. Six records means fifteen pairs.
                    A known DISTINCT witness refuses the merge.
                  </p>
                  <label className="field">
                    Certificate request IDs, one per line
                    <textarea
                      rows={4}
                      value={relations}
                      onChange={(e) => setRelations(e.target.value)}
                      maxLength={2000}
                    />
                  </label>
                  <button
                    className="button button-primary"
                    disabled={op.busy || !relations.trim()}
                    onClick={propose}
                  >
                    <GitMerge size={17} />
                    Propose complete merge
                  </button>
                  <div className="lookup-form">
                    <label className="field">
                      Merge operation ID
                      <input
                        value={mergeId}
                        onChange={(e) => setMergeId(e.target.value)}
                        maxLength={128}
                      />
                    </label>
                    <button
                      className="button button-outline"
                      disabled={!mergeId}
                      onClick={inspectMerge}
                    >
                      Read merge
                    </button>
                  </div>
                  {proposal && (
                    <div className="merge-outcome">
                      <Status status={proposal.status} />
                      <p>Combined records: {proposal.members.join(", ")}</p>
                      {proposal.witness && (
                        <Notice>
                          Merge refused by DISTINCT witness {proposal.witness}.
                        </Notice>
                      )}
                      {proposal.status === "pending" && (
                        <button
                          className="button button-ink"
                          disabled={op.busy}
                          onClick={() =>
                            act("finalize_alias", [mergeId], "directory")
                          }
                        >
                          Finalize identity alias
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
              {docket.delivery.request_id &&
                !["superseded", "quarantined"].includes(result.status) && (
                  <div className="docket-actions">
                    <p>
                      Publication delivers a finalized notice to the bound
                      application. Refresh to confirm its acknowledgement.
                    </p>
                    <button
                      className="button button-ink"
                      disabled={
                        op.busy ||
                        (result.decision === "SAME" &&
                          proposal?.status !== "finalized")
                      }
                      onClick={() => act("publish_alias", [id], "directory")}
                    >
                      <Send size={16} />
                      {docket.consumer_ack.request_id
                        ? "Replay application notice"
                        : "Deliver to application"}
                    </button>
                  </div>
                )}
              <Link className="source-link" to={"/challenges?relation=" + id}>
                Inspect a correction or challenge
              </Link>
            </>
          )}
        </>
      )}
      <Feedback message={op.message} />
      {error && <Notice error>{error}</Notice>}
    </section>
  );
}
