const CACHE_TTL = 3600000;
let cache = null;
let cacheTime = 0;

exports.handler = async function(event, context) {
  const headers = {"Access-Control-Allow-Origin": "*","Content-Type": "application/json"};
  
  if (cache && (Date.now() - cacheTime) < CACHE_TTL) {
    return {statusCode: 200, headers, body: JSON.stringify(cache)};
  }

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
      const off
