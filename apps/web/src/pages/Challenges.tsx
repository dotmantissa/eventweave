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
              A newer, delivered DISTINCT certificate must cover the same
              subject and consumer bindings.
            </p>
            <label className="field">
              Successor request ID
              <input
                name="successor_id"
                required
                placeholder="A finalized DISTINCT correction"
                value={correction}
                onChange={(e) => setCorrection(e.target.value)}
              />
            </label>
            <label className="field">
              What did the original merge miss?
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
              <h2>Restore the original identities</h2>
              <p className="muted">
                Once the correction and invalidation have finalized, split the
                affected cluster into its original records. Then deliver the
                successor notice from its docket to restore the application
                counts.
              </p>
              <button
                className="button button-outline"
                disabled={op.busy || !correction}
                onClick={async () => {
                  try {
                    await op.run("directory", "recover_component", [
                      inspected.scope,
                      inspected.left,
                      correction,
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
            Recovery splits records conservatively before fresh reuse.
          </p>
          <Link to="/workspace">
            Open a successor comparison <ChevronRight size={16} />
          </Link>
        </aside>
      </div>
    </div>
  );
}
