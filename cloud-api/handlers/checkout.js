import {send, env, stripe, isValidDeviceToken} from "./_lib.js";

const TRIAL_PERIOD_DAYS = 14;

export default async function handler(req, res) {
  if (req.method === "OPTIONS") return send(res, 204, {});
  if (req.method !== "POST") return send(res, 405, {error: "Method not allowed"});

  const deviceToken = String(req.body?.deviceToken || "").trim();
  if (!isValidDeviceToken(deviceToken)) {
    return send(res, 400, {error: "Invalid device token."});
  }

  try {
    const p = new URLSearchParams();
    p.set("mode", "subscription");
    p.set("line_items[0][price]", env("VIBEBRIDGE_PRICE_ID"));
    p.set("line_items[0][quantity]", "1");
    p.set("subscription_data[trial_period_days]", String(TRIAL_PERIOD_DAYS));
    // Links the resulting Customer/Subscription back to this device without
    // requiring the extension to have an account or session of its own.
    p.set("client_reference_id", deviceToken);
    p.set("success_url", env("CHECKOUT_SUCCESS_URL"));
    p.set("cancel_url", env("CHECKOUT_CANCEL_URL"));

    const session = await stripe("/checkout/sessions", {method: "POST", body: p});
    return send(res, 200, {url: session.url});
  } catch (error) {
    return send(res, 400, {error: error.message || "Could not start checkout."});
  }
}
