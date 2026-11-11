import { Agent, EnvHttpProxyAgent, setGlobalDispatcher } from "undici";
import { setDefaultResultOrder } from "node:dns";
setDefaultResultOrder("ipv4first");
// Pin one address per connection and allow the TLS handshake time to complete.
setGlobalDispatcher(
  process.env.HTTPS_PROXY || process.env.HTTP_PROXY
    ? new EnvHttpProxyAgent()
    : new Agent({ connect: { autoSelectFamily: false, timeout: 30000 } }),
);
