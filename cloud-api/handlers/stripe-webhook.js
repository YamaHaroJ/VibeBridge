import crypto from "node:crypto";
import {send, env, stripe, updateCustomerMetadata} from "./_lib.js";

// bodyParser is disabled once, for the whole function, in api/index.js —
// this handler's raw body is the untouched request stream.
function readRaw(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", chunk => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function verifyStripe(payload, signature, secret) {
  const fields = String(signature || "").split(",");
  const timestamp = (fields.find(x => x.startsWith("t=")) || "").slice(2);
  const signatures = fields.filter(x => x.startsWith("v1=")).map(x => x.slice(3));
  if (!timestamp || !signatures.length || !secret) return false;
  if (Math.abs(Date.now() / 1000 - Number(timestamp)) > 300) return false;
  const expected = crypto.createHmac("sha256", secret).update(timestamp + "." + payload.toString("utf8")).digest("hex");
  const b = Buffer.from(expected, "hex");
  return signatures.some(sig => {
    const a = Buffer.from(sig, "hex");
    return a.length === b.length && crypto.timingSafeEqual(a, b);
  });
}

// The webhook's only job is to tag the Stripe Customer created by checkout
// with the device token that started it. License status is always read
// live from Stripe afterward, so there is nothing else to persist here.
async function handleCheckoutCompleted(eventSession) {
  const session = await stripe("/checkout/sessions/" + encodeURIComponent(eventSession.id));
  const deviceToken = String(session.client_reference_id || "");
  const customerId = String(session.customer || "");
  if (!deviceToken || !customerId) return;
  await updateCustomerMetadata(customerId, {vibebridge_device_token: deviceToken});
}

export default async function handler(req, res) {
  if (req.method !== "POST") return send(res, 405, {error: "Method not allowed"});
  const raw = await readRaw(req);
  const signature = req.headers["stripe-signature"];
  if (!verifyStripe(raw, signature, env("STRIPE_WEBHOOK_SECRET"))) {
    return send(res, 400, {error: "Invalid signature"});
  }
  let event;
  try {
    event = JSON.parse(raw.toString("utf8"));
  } catch {
    return send(res, 400, {error: "Malformed payload"});
  }

  try {
    if (event.type === "checkout.session.completed") {
      await handleCheckoutCompleted(event.data.object);
    }
    return send(res, 200, {received: true});
  } catch (error) {
    // Stripe retries on non-2xx; log and still acknowledge malformed-but-handled events.
    console.error("VibeBridge webhook error:", error.message || error);
    return send(res, 200, {received: true, warning: "Processing error logged."});
  }
}
