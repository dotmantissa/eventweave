import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { usePrivy } from "@privy-io/react-auth";
import { Plus, FileText, ShieldCheck } from "lucide-react";
import { request } from "../api";
import { useOperation } from "../use-operation";
import { descriptorSchema, type Source } from "@eventweave/protocol";
import { Notice, PageIntro, Feedback } from "../components/ui";

export default function NewEvent() {
  const op = useOperation();
  const [error, setError] = useState("");
  const [source, setSource] = useState<Source | null>(null);
  const { getAccessToken } = usePrivy();
  const navigate = useNavigate();
  const [inspecting, setInspecting] = useState(false);
  async function inspect(form: HTMLFormElement) {
    const data = new FormData(form);
    setInspecting(true);
    setError("");
    try {
      const token = await getAccessToken();
      const value = await request<{ source: Source }>("/sources/commit", {
        method: "POST",
        headers: { Authorization: "Bearer " + token },
        body: JSON.stringify({
          url: data.get("url"),
          authority_id: data.get("authority_id"),
          record_id: data.get("event_id"),
          revision: data.get("revision"),
        }),
      });
      setSource(value.source);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "The source could not be read.",
      );
    } finally {
      setInspecting(false);
    }
  }
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    const data = new FormData(e.currentTarget);
    try {
      if (!source)
        throw new Error("Commit the public source before registering.");
      const value = descriptorSchema.parse({
        event_id: data.get("event_id"),
        schema_id: data.get("schema_id"),
        schema_revision: 1,
        title: data.get("title"),
        issuer: data.get("issuer"),
        place: data.get("place"),
        interval_start: new Date(
          String(data.get("interval_start")),
        ).toISOString(),
        interval_end: new Date(String(data.get("interval_end"))).toISOString(),
        occurrence_type: data.get("occurrence_type"),
        official_reference: data.get("official_reference"),
        source,
      });
      await op.run("registry", "open_event", [JSON.stringify(value)]);
      navigate("/activity");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "This event could not be registered.",
      );
    }
  }
  return (
    <div className="page">
      <PageIntro title="Give the occurrence a home.">
        A bounded descriptor keeps the evidence useful. A catchy name is
        welcome, but it can’t do the work alone.
      </PageIntro>
      <form className="registration-form" onSubmit={submit}>
        <div className="form-main">
          <h2>The occurrence</h2>
          <label className="field">
            Report title
            <input
              name="title"
              required
              minLength={3}
              maxLength={180}
              placeholder="The name used in the public report"
            />
          </label>
          <div className="field-pair">
            <label className="field">
              Event ID
              <input
                name="event_id"
                required
                pattern="[a-zA-Z0-9_.:]+"
                maxLength={128}
                placeholder="issuer.reference.revision"
              />
            </label>
            <label className="field">
              Occurrence type
              <select name="occurrence_type">
                <option value="release">Software release</option>
                <option value="security_incident">Security incident</option>
                <option value="operational_notice">Operational notice</option>
              </select>
            </label>
          </div>
          <div className="field-pair">
            <label className="field">
              Issuer
              <input
                name="issuer"
                required
                maxLength={128}
                placeholder="Who published the record?"
              />
            </label>
            <label className="field">
              Place or service
              <input
                name="place"
                required
                maxLength={128}
                placeholder="Where did it occur?"
              />
            </label>
          </div>
          <div className="field-pair">
            <label className="field">
              Interval starts
              <input type="datetime-local" name="interval_start" required />
            </label>
            <label className="field">
              Interval ends
              <input type="datetime-local" name="interval_end" required />
            </label>
          </div>
          <p className="field-help">
            Your local times are converted to UTC. Use the source’s occurrence
            interval.
          </p>
          <div className="field-pair">
            <label className="field">
              Official reference
              <input
                name="official_reference"
                required
                maxLength={128}
                placeholder="Version, incident ID or notice reference"
              />
            </label>
            <label className="field">
              Registered policy ID
              <input
                name="schema_id"
                required
                placeholder="occurrence.v1"
                defaultValue="occurrence.v1"
              />
            </label>
          </div>
          <h2 className="subheading">The public source</h2>
          <label className="field">
            Source URL
            <input
              type="url"
              name="url"
              required
              placeholder="https://…"
              onChange={() => setSource(null)}
            />
          </label>
          <div className="field-pair">
            <label className="field">
              Configured authority ID
              <input
                name="authority_id"
                required
                placeholder="authority:1"
                onChange={() => setSource(null)}
              />
            </label>
            <label className="field">
              Source revision
              <input
                name="revision"
                required
                placeholder="Immutable commit or published revision"
                onChange={() => setSource(null)}
              />
            </label>
          </div>
          <button
            className="button button-outline"
            type="button"
            disabled={inspecting}
            onClick={(e) => inspect(e.currentTarget.form!)}
          >
            <FileText size={17} />
            {inspecting
              ? "Reading the complete source…"
              : source
                ? "Source committed"
                : "Inspect and commit source"}
          </button>
          {source && (
            <Notice>
              {source.byte_length.toLocaleString()} bytes committed. All five
              span locators recorded.
            </Notice>
          )}
          <Feedback message={op.message} />
          {error && <Notice error>{error}</Notice>}
          <div className="form-submit">
            <Link className="text-button" to="/">
              Cancel
            </Link>
            <button
              className="button button-primary"
              disabled={op.busy || !source}
              type="submit"
            >
              <Plus size={18} />
              {op.busy ? "Registering…" : "Register event"}
            </button>
          </div>
        </div>
        <aside className="document-margin">
          <h3>
            <ShieldCheck size={18} />
            Before you publish
          </h3>
          <p>
            Only the principal configured for this authority can attest its
            records. Email sign in creates your secure signing account, but
            doesn’t give it issuer permissions.
          </p>
          <p>
            Sources must be public, authentic and within the complete inspection
            budget. Private documents and secrets do not belong here.
          </p>
          <p>
            A changed source needs a new revision. Old history stays exactly
            where it belongs.
          </p>
        </aside>
      </form>
    </div>
  );
}
