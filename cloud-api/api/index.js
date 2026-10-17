import checkout from "../handlers/checkout.js";
import stripeWebhook from "../handlers/stripe-webhook.js";
import licenseStatus from "../handlers/license-status.js";

const handlers = {
  "checkout": checkout,
  "stripe-webhook": stripeWebhook,
  "license-status": licenseStatus
};

export const config = {api: {bodyParser: false}};

async function parseJsonBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks);
  if (!raw.length) return {};
  try {
    return JSON.parse(raw.toString("utf8"));
  } catch {
    return {};
  }
}

export default async function handler(req, res) {
  const route = String(req.query?.route || "");
  const target = handlers[route];
  if (!target) {
    res.status(404).json({error: "Unknown route."});
    return;
  }
  // stripe-webhook verifies its own raw body/signature and must not have the
  // body consumed here first.
  if (route !== "stripe-webhook" && req.method === "POST") {
    req.body = await parseJsonBody(req);
  }
  return target(req, res);
}
