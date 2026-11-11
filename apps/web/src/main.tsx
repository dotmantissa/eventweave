import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { PrivyProvider } from "@privy-io/react-auth";
import { defineChain } from "viem";
import App from "./App";
import "@fontsource/bodoni-moda/500.css";
import "@fontsource/bodoni-moda/600.css";
import "@fontsource-variable/public-sans";
import "./styles.css";
const studio = defineChain({
  id: 61999,
  name: "GenLayer Studio",
  nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
  rpcUrls: { default: { http: ["https://studio.genlayer.com/api"] } },
  testnet: true,
});
const appId = import.meta.env.VITE_PRIVY_APP_ID;
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      {appId ? (
        <PrivyProvider
          appId={appId}
          config={{
            loginMethods: ["email"],
            appearance: {
              theme: "light",
              accentColor: "#EE4D1B",
              logo: "/favicon.svg",
              showWalletLoginFirst: false,
            },
            embeddedWallets: {
              ethereum: { createOnLogin: "users-without-wallets" },
            },
            supportedChains: [studio],
            defaultChain: studio,
          }}
        >
          <App />
        </PrivyProvider>
      ) : (
        <div className="configuration-error">
          <img src="/favicon.svg" alt="" />
          <h1>Almost ready.</h1>
          <p>
            Email sign in needs the public Privy app ID. Add VITE_PRIVY_APP_ID
            to your environment and rebuild.
          </p>
        </div>
      )}
    </BrowserRouter>
  </React.StrictMode>,
);
