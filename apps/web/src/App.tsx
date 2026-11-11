import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import { usePrivy } from "@privy-io/react-auth";
import { Sun, Moon, Check, ExternalLink, X, Menu, Mail } from "lucide-react";
import { api } from "./api";
import { Mark, PageIntro } from "./components/ui";
import Registry from "./pages/Registry";
import EventDetail from "./pages/EventDetail";
import Workspace from "./pages/Workspace";
import NewEvent from "./pages/NewEvent";
import Challenges from "./pages/Challenges";
import Applications from "./pages/Applications";
import Activity from "./pages/Activity";
import Guide from "./pages/Guide";

export default function App() {
  const { ready, authenticated, login, logout, user } = usePrivy();
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || "light",
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [network, setNetwork] = useState<
    "connecting" | "ready" | "unavailable"
  >("connecting");
  useEffect(() => {
    api
      .config()
      .then((c) => setNetwork(c.ready ? "ready" : "unavailable"))
      .catch(() => setNetwork("unavailable"));
  }, []);
  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    localStorage.setItem("eventweave.theme", next);
  }
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <Link className="brand" to="/" aria-label="EventWeave home">
          <Mark />
          <span>EventWeave</span>
        </Link>
        <nav
          className={mobileOpen ? "primary-nav open" : "primary-nav"}
          aria-label="Main navigation"
        >
          {[
            ["/", "Registry"],
            ["/workspace", "Compare"],
            ["/challenges", "Challenges"],
            ["/applications", "Applications"],
          ].map(([to, label]) => (
            <NavLink
              key={to}
              end={to === "/"}
              to={to}
              onClick={() => setMobileOpen(false)}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="header-actions">
          <button
            className="icon-button"
            onClick={toggleTheme}
            aria-label={
              theme === "light" ? "Switch to dark mode" : "Switch to light mode"
            }
          >
            {theme === "light" ? <Moon size={19} /> : <Sun size={19} />}
          </button>
          <button
            className="button button-ink login-button"
            disabled={!ready}
            onClick={() => (authenticated ? logout() : login())}
          >
            {authenticated ? (
              <>
                <Check size={16} />
                <span>
                  {user?.email?.address?.split("@")[0] || "Signed in"}
                </span>
              </>
            ) : (
              <>
                <Mail size={16} />
                <span>Sign in</span>
              </>
            )}
          </button>
          <button
            className="icon-button menu-toggle"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle navigation"
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>
      <main id="main">
        <Routes>
          <Route path="/" element={<Registry />} />
          <Route path="/events/:id" element={<EventDetail />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/new" element={<NewEvent />} />
          <Route path="/challenges" element={<Challenges />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/guide" element={<Guide />} />
          <Route
            path="*"
            element={
              <div className="page">
                <PageIntro title="This thread ends here.">
                  We couldn’t find that page. The registry is a good place to
                  pick things up.
                </PageIntro>
                <Link to="/" className="button button-primary">
                  Back to the registry
                </Link>
              </div>
            }
          />
        </Routes>
      </main>
      <footer className="site-footer">
        <Link to="/" className="footer-brand">
          <Mark small />
          <span>A history worth keeping.</span>
        </Link>
        <div className="footer-links">
          <Link to="/guide">How it works</Link>
          <Link to="/activity">Your activity</Link>
          <a
            href="https://github.com/dotmantissa/corrigenda"
            target="_blank"
            rel="noreferrer"
          >
            Source code <ExternalLink size={13} />
          </a>
        </div>
        <span className={"network-state " + network}>
          <span />
          {network === "ready"
            ? "GenLayer Studio"
            : network === "connecting"
              ? "Connecting to Studio"
              : "Studio connection unavailable"}
        </span>
      </footer>
    </>
  );
}
