export function cors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader("Cache-Control", "no-store, max-age=0");
}

export function send(res, status, body) {
  cors(res);
  res.status(status).json(body);
}

export function env(name) {
  // Trim defensively: a stray leading/trailing newline from a dashboard paste
  // turns "Bearer <key>" into an invalid HTTP header value, and the runtime's
  // own error for that includes the full header — i.e. the secret — in its
  // message. Trimming here closes that off at the source.
  const value = String(process.env[name] || "").trim();
  if (!value) throw new Error("Missing server setting: " + name);
  return value;
}

// Never let a raw error reach the client: a header-construction failure's
// message can contain the Authorization header itself (the secret key).
// Log the real error server-side only; the caller gets a safe, generic one.
function safeFail(error, publicMessage) {
  console.error("VibeBridge cloud-api error:", error?.message || error);
  throw new Error(publicMessage);
}

// No Stripe SDK dependency: a thin REST wrapper keeps the deployed bundle
// small and matches the pattern already used by the Autofill cloud-api.
export async function stripe(path, options = {}) {
  const body = options.body instanceof URLSearchParams ? options.body.toString() : options.body;
  let response;
  try {
    response = await fetch("https://api.stripe.com/v1" + path, {
      method: options.method || "GET",
      headers: {
        "Authorization": "Bearer " + env("STRIPE_SECRET_KEY"),
        ...(body ? {"Content-Type": "application/x-www-form-urlencoded"} : {}),
        ...(options.headers || {})
      },
      body
    });
  } catch (error) {
    return safeFail(error, "Stripe request could not be sent.");
  }
  const data = await response.json();
  // Stripe's own error message is safe to surface: it comes from Stripe's
  // response body, never from our request construction, so it cannot contain
  // the secret key.
  if (!response.ok) throw new Error(data?.error?.message || "Stripe request failed.");
  return data;
}

export async function getCustomer(customerId) {
  return stripe("/customers/" + encodeURIComponent(customerId));
}

export async function updateCustomerMetadata(customerId, metadata) {
  const p = new URLSearchParams();
  for (const [key, value] of Object.entries(metadata || {})) p.set("metadata[" + key + "]", String(value ?? ""));
  return stripe("/customers/" + encodeURIComponent(customerId), {method: "POST", body: p});
}

// The device token is the only identity VibeBridge needs; it is stored as
// Stripe Customer metadata instead of a separate database, same as Autofill.
export async function findCustomerByDeviceToken(deviceToken) {
  const query = "metadata['vibebridge_device_token']:'" + String(deviceToken).replace(/'/g, "\\'") + "'";
  const data = await stripe("/customers/search?query=" + encodeURIComponent(query));
  return Array.isArray(data?.data) ? data.data[0] || null : null;
}

export async function activeSubscriptionFor(customerId) {
  const data = await stripe("/subscriptions?customer=" + encodeURIComponent(customerId) + "&status=all&limit=5");
  const subscriptions = Array.isArray(data?.data) ? data.data : [];
  return subscriptions.find(sub => sub.status === "active" || sub.status === "trialing") || null;
}

export function isValidDeviceToken(value) {
  return typeof value === "string" && /^[A-Za-z0-9_-]{16,128}$/.test(value);
}
