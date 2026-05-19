exports.handler = async function(event, context) {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json"
  };

  try {
    const authResp = await fetch("https://coupons.valassis.eu/capi/authentications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login: "es_mundopromos", password: "Q5YbNq63sWcAgk27" })
    });

    if (!authResp.ok) {
      const err = await authResp.text();
      return { statusCode: 502, headers, body: JSON.stringify({ error: "Auth failed", detail: err }) };
    }

    const authData = await authResp.json();
    const token = authData.token || authData.access_token || authData.authToken || authData.sessionToken;

    if (!token) {
      return { statusCode: 502, headers, body: JSON.stringify({ error: "No token in response", raw: authData }) };
    }

    const coupResp = await fetch("https://coupons.valassis.eu/capi/coupons?limit=30&status=active", {
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
      }
    });

    if (!coupResp.ok) {
      const err = await coupResp.text();
      return { statusCode: 502, headers, body: JSON.stringify({ error: "Coupons fetch failed", detail: err }) };
    }

    const coupData = await coupResp.json();
    return { statusCode: 200, headers, body: JSON.stringify(coupData) };

  } catch (e) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: e.message }) };
  }
};
