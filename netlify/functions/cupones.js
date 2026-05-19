exports.handler = async function(event, context) {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json"
  };

  try {
    const credentials = Buffer.from("es_mundopromos:Q5YbNq63sWcAgk27").toString("base64");

    const resp = await fetch("https://coupons.valassis.eu/capi/coupons", {
      headers: {
        "Authorization": "Basic " + credentials,
        "Content-Type": "application/json"
      }
    });

    if (!resp.ok) {
      const err = await resp.text();
      return { statusCode: resp.status, headers, body: JSON.stringify({ error: "API error " + resp.status, detail: err }) };
    }

    const data = await resp.json();
    return { statusCode: 200, headers, body: JSON.stringify(data) };

  } catch(e) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: e.message }) };
  }
};
