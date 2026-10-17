import {send, findCustomerByDeviceToken, activeSubscriptionFor, isValidDeviceToken} from "./_lib.js";

export default async function handler(req, res) {
  if (req.method === "OPTIONS") return send(res, 204, {});
  if (req.method !== "GET") return send(res, 405, {error: "Method not allowed"});

  const deviceToken = String(req.query?.token || "").trim();
  if (!isValidDeviceToken(deviceToken)) {
    return send(res, 400, {error: "Invalid device token."});
  }

  try {
    const customer = await findCustomerByDeviceToken(deviceToken);
    if (!customer) return send(res, 200, {active: false, status: "no-subscription"});

    const subscription = await activeSubscriptionFor(customer.id);
    if (!subscription) return send(res, 200, {active: false, status: "no-subscription"});

    return send(res, 200, {
      active: true,
      status: subscription.status,
      trialEnd: subscription.trial_end || null,
      currentPeriodEnd: subscription.current_period_end || null
    });
  } catch (error) {
    return send(res, 400, {error: error.message || "Could not check license status."});
  }
}
