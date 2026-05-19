exports.handler = async function(event, context) {
  const headers = {"Access-Control-Allow-Origin": "*","Content-Type": "application/json"};
  const credentials = Buffer.from("es_mundopromos:Q5YbNq63sWcAgk27").toString("base64");
  const auth = "Basic " + credentials;
  try {
    const synResp = await fetch("https://coupons.valassis.eu/capi/syndications", {headers: {"Authorization": auth}});
    if (!synResp.ok) {
      const err = await synResp.text();
      return {statusCode: synResp.status, headers, body: JSON.stringify({error: "Syndications error " + synResp.status, detail: err})};
    }
    const synData = await synResp.json();
    const syndications = synData.syndication || [];
    if (!syndications.length) {
      return {statusCode: 200, headers, body: JSON.stringify({coupons: [], debug: "No syndications found"})};
    }
    const synName = syndications[0].name;
    const synUrl = syndications[0].url || syndications[0].synUrl || "";

    const feedResp = await fetch("https://coupons.valassis.eu/capi/syndications/" + encodeURIComponent(synName) + "/offers/DeepLinkFeed.xml", {headers: {"Authorization": auth}});
    if (!feedResp.ok) {
      const err = await feedResp.text();
      return {statusCode: feedResp.status, headers, body: JSON.stringify({error: "Feed error " + feedResp.status, detail: err, synName: synName})};
    }
    const xml = await feedResp.text();
    const coupons = [];
    const offerRegex = /<Offer>([\s\S]*?)<\/Offer>/g;
    let match;
    while ((match = offerRegex.exec(xml)) !== null) {
      const block = match[1];
      const get = function(tag) {
        const m = block.match(new RegExp("<" + tag + "[^>]*>([\\s\\S]*?)<\\/" + tag + ">"));
        if (!m) return "";
        let val = m[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/, "$1").trim();
        val = val.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
        return val;
      };
      const offerCode = get("OfferCode");
      const rawValue = get("OfferValue");
      const nums = rawValue.match(/[\d]+[,\.]?[\d]*/);
      const cleanValue = nums ? nums[0].replace(".", ",") + " €" : rawValue;
      const couponUrl = synUrl ? synUrl + "?offer=" + offerCode : "";

      coupons.push({
        id: offerCode,
        name: get("OfferDescription"),
        value: cleanValue,
        brand: get("Brand"),
        brandIcon: get("BrandIconUrl"),
        image: get("CouponImage"),
        purchase: get("PurchaseDescription"),
        category: get("Category"),
        expires: get("SiteExpiryOn").split("T")[0],
        url: couponUrl
      });
    }
    return {statusCode: 200, headers, body: JSON.stringify({coupons: coupons, synName: synName, total: coupons.length})};
  } catch(e) {
    return {statusCode: 500, headers, body: JSON.stringify({error: e.message})};
  }
};
