import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { usePrivy } from "@privy-io/react-auth";
import { ChevronRight, ShieldCheck, Layers } from "lucide-react";
import { request } from "../api";
import { useOperation } from "../use-operation";
import { type Certificate } from "@eventweave/protocol";
import { Status, Notice, PageIntro, Feedback } from "../components/ui";

export default function Challenges() {
  const [params] = useSearchParams();
  const { getAccessToken } = usePrivy();
  const op = useOperation();
  const [error, setError] = useState("");
  const [relation, setRelation] = useState(params.get("relation") || "");
  const [inspected, setInspected] = useState<Certificate | null>(null);
  const [correction, setCorrection] = useState("");
  const [recoveryRelations, setRecoveryRelations] = useState("");
  async function inspect() {
    try {
      setInspected(
        await request<Certificate>(
          "/relations/" + encodeURIComponent(relation),
        ),
      );
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Relation could not be read.");
    }
  }
  async function challenge(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    try {
      const successor = String(form.get("successor_id"));
      await request("/challenges", {
        method: "POST",
        headers: { Authorization: "Bearer " + (await getAccessToken()) },
        body: JSON.stringify({
          relation_id: relation,
          successor_id: successor,
          reason: form.get("reason"),
        }),
      });
      await op.run("court", "supersede_relation", [
        relation,
        successor,
        String(form.get("reason")),
      ]);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "The correction could not be submitted.",
      );
    }
  }
  return (
    <div className="page">
      <PageIntro title="History can be corrected.">
        When a merge gets it wrong, challenge the relation. Keep the records.
        Change what they’re allowed to share.
      </PageIntro>
      <div className="document-layout">
        <section>
          <form
            className="lookup-form"
            onSubmit={(e) => {
              e.preventDefault();
              inspect();
            }}
          >
            <label className="field">
              Relation request ID
              <input
                value={relation}
                onChange={(e) => setRelation(e.target.value)}
                placeholder="The request ID of the original relation"
                required
              />
            </label>
            <button className="button button-ink">Inspect relation</button>
          </form>
          {inspected && (
            <div className="inspected-relation">
              <Status status={inspected.decision} />
              <h2>
                {inspected.left} / {inspected.right}
              </h2>
              <p>
                Generation {inspected.generation}.{" "}
                <Status status={inspected.status} />
              </p>
              <dl className="facts-list compact">
                <div>
                  <dt>Controlling rules</dt>
                  <dd>{inspected.controlling_rules.join(", ")}</dd>
                </div>
                <div>
                  <dt>Superseded by</dt>
                  <dd>{inspected.superseded_by || "No successor"}</dd>
                </div>
              </dl>
            </div>
          )}
          <form onSubmit={challenge} className="challenge-form">
            <h2>Apply a correction</h2>
            <p>
              A newer, delivered SAME or DISTINCT certificate must cover the
              same subject and consumer bindings.
            </p>
            <label className="field">
              Successor request ID
              <input
                name="successor_id"
                required
                placeholder="A finalized correction"
                value={correction}
                onChange={(e) => setCorrection(e.target.value)}
              />
            </label>
            <label className="field">
              What did the original decision miss?
              <textarea
                name="reason"
                required
                minLength={20}
                maxLength={2000}
                rows={5}
                placeholder="Point to the discriminating fact and its committed public source."
              />
            </label>
            <button
              className="button button-primary"
              disabled={!relation || op.busy}
            >
              <ShieldCheck size={17} />
              {op.busy ? "Submitting correction…" : "Supersede relation"}
            </button>
          </form>
          {inspected && (
            <section className="correction-recovery">
              <h2>Restore corrected identities</h2>
              <p className="muted">
                For a DISTINCT correction, wait for every invalidation
                acknowledgement, then recover the affected cluster. Recovery
                restores every affected reference using a complete partition
                proof. For clusters larger than two records, assess and deliver
                every pair again: SAME within each occurrence and DISTINCT
                between occurrences. For a SAME correction, submit a fresh
                complete merge proof and deliver its notice.
              </p>
              <label className="field">
                Additional recovery relation IDs
                <textarea
                  rows={3}
                  value={recoveryRelations}
                  onChange={(e) => setRecoveryRelations(e.target.value)}
                  placeholder="One delivered current pair certificate per line. The correction is included automatically."
                />
              </label>
              <button
                className="button button-outline"
                disabled={op.busy || !correction}
                onClick={async () => {
                  try {
                    await op.run("directory", "recover_component", [
                      inspected.scope,
                      inspected.left,
                      correction,
                      JSON.stringify(
                        recoveryRelations.split(/[\s,]+/).filter(Boolean),
                      ),
                    ]);
                  } catch (e) {
                    setError(
                      e instanceof Error
                        ? e.message
                        : "Recovery could not be requested.",
                    );
                  }
                }}
              >
                <Layers size={17} />
                Recover corrected cluster
              </button>
              {correction && (
                <Link
                  className="source-link"
                  to={"/workspace?request=" + correction}
                >
                  Read successor delivery
                </Link>
              )}
            </section>
          )}
          <Feedback message={op.message} />
          {error && <Notice error>{error}</Notice>}
        </section>
        <aside className="document-margin">
          <h3>
            <Layers size={18} />
            Nothing gets erased
          </h3>
          <p>Original consumer references remain attributed to their owners.</p>
          <p>
            The affected cluster is restricted while aliases are invalidated.
            Recovery requires evidence for every member’s corrected identity.
          </p>
          <Link to="/workspace">
            Open a successor comparison <ChevronRight size={16} />
          </Link>
        </aside>
      </div>
    </div>
  );
}
