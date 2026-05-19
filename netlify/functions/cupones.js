const { XMLParser } = require("fast-xml-parser");

exports.handler = async function(event, context) {
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Content-Type": "application/json"
  };

  const credentials = Buffer.from("es_mundopromos:Q5YbNq63sWcAgk27").toString("base64");
  const auth = "Basic " + credentials;

  try {
    // Step 1: get syndications
    const synResp = await fetch("https://coupons.valassis.eu/capi/syndications", {
      headers: { "Authorization": auth }
    });

    if (!synResp.ok) {
      const err = await synResp.text();
      return { statusCode: synResp.status, headers, body: JSON.stringify({ error: "Syndications error " + synResp.status, detail: err }) };
    }

    const synData = await synResp.json();
    const syndications = synData.syndication || [];

    if (!syndications.length) {
      return { statusCode: 200, headers, body: JSON.stringify({ coupons: [], debug: "No syndications found" }) };
    }

    // Use first syndication
    const synName = syndications[0].name;

    // Step 2: fetch DeepLinkFeed XML
    const feedResp = await fetch(`https://coupons.valassis.eu/capi/syndications/${encodeURIComponent(synName)}/offers/DeepLinkFeed.xml`, {
      headers: { "Authorization": auth }
    });

    if (!feedResp.ok) {
      const err = await feedResp.text();
      return { statusCode: feedResp.status, headers, body: JSON.stringify({ error: "Feed error " + feedResp.status, detail: err, synName }) };
    }

    const xml = await feedResp.text();

    // Parse XML manually (simple regex since no npm in netlify functions without package.json)
    const coupons = [];
    const offerRegex = /<Offer>([\s\S]*?)<\/Offer>/g;
    let match;
    while ((match = offerRegex.exec(xml)) !== null) {
      const block = match[1];
      const get = (tag) => {
        const m = block.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`));
        return m ? m[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/, '$1').trim() : '';
      };
      coupons.push({
        id: get('OfferCode'),
        name: get('OfferDescription'),
        value: get('OfferValue'),
        brand: get('Brand'),
        brandIcon: get('BrandIconUrl'),
        image: get('CouponImage'),
        purchase: get('PurchaseDescription'),
        category: get('Category'),
        expires: get('SiteExpiryOn'),
      });
    }

    return { statusCode: 200, headers, body: JSON.stringify({ coupons, synName, total: coupons.length }) };

  } catch(e) {
    return { statusCode: 500, headers, body: JSON.stringify({ error: e.message }) };
  }
};
