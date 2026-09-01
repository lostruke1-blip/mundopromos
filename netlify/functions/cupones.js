const CACHE_TTL = 3600000;
let cache = null;
let cacheTime = 0;

exports.handler = async function(event, context) {
  const headers = {"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"};

  if (cache && (Date.now() - cacheTime) < CACHE_TTL) {
    return {statusCode: 200, headers: headers, body: JSON.stringify(cache)};
  }

  const user = process.env.SAVI_USER;
  const pass = process.env.SAVI_PASS;

  if (!user || !pass) {
    return {statusCode: 500, headers: headers, body: JSON.stringify({error: "Faltan las variables de entorno SAVI_USER y SAVI_PASS en Netlify"})};
  }

  const auth = "Basic " + Buffer.from(user + ":" + pass).toString("base64");

  try {
    const synResp = await fetch("https://coupons.valassis.eu/capi/syndications", {
      headers: {"Authorization": auth}
    });
    if (!synResp.ok) {
      return {statusCode: synResp.status, headers: headers, body: JSON.stringify({error: "No se pudo conectar con Savi"})};
    }
    const synData = await synResp.json();
    const syndications = synData.syndication || [];
    if (!syndications.length) {
      return {statusCode: 200, headers: headers, body: JSON.stringify({coupons: []})};
    }
    const synName = syndications[0].name;
    const feedResp = await fetch("https://coupons.valassis.eu/capi/syndications/" + encodeURIComponent(synName) + "/offers/DeepLinkFeed.xml", {
      headers: {"Authorization": auth}
    });
    if (!feedResp.ok) {
      return {statusCode: feedResp.status, headers: headers, body: JSON.stringify({error: "No se pudo leer el feed de cupones"})};
    }
    const xml = await feedResp.text();
    const coupons = [];
    const offerRegex = /<Offer>([\s\S]*?)<\/Offer>/g;
    let match;
    while ((match = offerRegex.exec(xml)) !== null) {
      const block = match[1];
      const get = function(tag) {
        const m = block.match(new RegExp("<" + tag + "[^>]*>([\\s\\S]*?)<\\/" + tag + ">"));
        if (!m) { return ""; }
        let val = m[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/, "$1").trim();
        val = val.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
        return val;
      };
      const rawValue = get("OfferValue");
      const nums = rawValue.match(/[\d]+[,.]?[\d]*/);
      const cleanValue = nums ? nums[0].replace(".", ",") + " \u20ac" : rawValue;
      coupons.push({
        id: get("OfferCode"),
        name: get("OfferDescription"),
        value: cleanValue,
        brand: get("Brand"),
        image: get("CouponImage"),
        purchase: get("PurchaseDescription"),
        category: get("Category"),
        expires: get("SiteExpiryOn").split("T")[0]
      });
    }
    cache = {coupons: coupons, total: coupons.length};
    cacheTime = Date.now();
    return {statusCode: 200, headers: headers, body: JSON.stringify(cache)};
  } catch (e) {
    return {statusCode: 500, headers: headers, body: JSON.stringify({error: e.message})};
  }
};
