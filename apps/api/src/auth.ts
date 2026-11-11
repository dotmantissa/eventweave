import { PrivyClient } from "@privy-io/node";
import type { FastifyRequest } from "fastify";
import { configuration } from "./config.js";
let privy: PrivyClient | undefined;
export class HttpError extends Error {
  constructor(
    readonly statusCode: number,
    message: string,
  ) {
    super(message);
  }
}
export async function authenticate(request: FastifyRequest) {
  const bearer = request.headers.authorization;
  if (!bearer?.startsWith("Bearer ") || bearer.length > 8192)
    throw new HttpError(401, "Sign in with email to continue.");
  const config = configuration();
  privy ??= new PrivyClient({
    appId: config.PRIVY_APP_ID,
    appSecret: config.PRIVY_APP_SECRET,
  });
  try {
    const claims = await privy
      .utils()
      .auth()
      .verifyAccessToken(bearer.slice(7));
    const user = await privy.users()._get(claims.user_id);
    const email = user.linked_accounts.find(
      (account) => account.type === "email",
    );
    const wallet = user.linked_accounts.find(
      (account) =>
        account.type === "wallet" &&
        account.wallet_client_type === "privy" &&
        account.chain_type === "ethereum",
    );
    if (!email || !wallet || wallet.type !== "wallet")
      throw new HttpError(
        403,
        "This action requires an email account and its secure signing account.",
      );
    return {
      user_id: claims.user_id,
      signer: wallet.address.toLowerCase() as `0x${string}`,
    };
  } catch (error) {
    if (error instanceof HttpError) throw error;
    throw new HttpError(
      401,
      "Your email session could not be verified. Sign in again.",
    );
  }
}
