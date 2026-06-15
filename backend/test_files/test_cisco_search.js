const axios = require('axios');

function parseCookie(cookieStr) {
  const firstPart = cookieStr.split(';')[0];
  const eqIdx = firstPart.indexOf('=');
  const name = firstPart.slice(0, eqIdx).trim();
  const value = firstPart.slice(eqIdx + 1).trim();
  return { name, value };
}

async function searchCisco() {
  const pageUrl = 'https://careers.cisco.com/global/en/search-results?q=engineer&location=India';
  const widgetsUrl = 'https://careers.cisco.com/widgets';

  const commonHeaders = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/148.0.7778.96 Safari/537.36',
    'sec-ch-ua-platform': '"Windows"',
    'sec-ch-ua': '"Chromium";v="148", "HeadlessChrome";v="148", "Not/A)Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
  };

  try {
    // 1. GET the page to get the cookies
    const pageRes = await axios.get(pageUrl, {
      headers: {
        ...commonHeaders,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
      }
    });

    const setCookies = pageRes.headers['set-cookie'] || [];
    let playSession = '';
    let phpppeAct = '';
    let cookieHeaders = [];

    for (const c of setCookies) {
      const parsed = parseCookie(c);
      if (parsed.name === 'PLAY_SESSION') {
        playSession = parsed.value;
      }
      if (parsed.name === 'PHPPPE_ACT') {
        phpppeAct = parsed.value;
      }
      cookieHeaders.push(`${parsed.name}=${parsed.value}`);
    }

    if (!playSession) {
      throw new Error('PLAY_SESSION cookie not found');
    }

    // 2. Decode PLAY_SESSION JWT payload
    const jwtParts = playSession.split('.');
    if (jwtParts.length < 2) {
      throw new Error('Invalid PLAY_SESSION cookie format');
    }
    const payloadBuf = Buffer.from(jwtParts[1], 'base64');
    const payloadJson = JSON.parse(payloadBuf.toString('utf-8'));
    const csrfToken = payloadJson.data?.csrfToken;

    console.log('Parsed CSRF Token:', csrfToken);

    // 3. Make the POST request to /widgets
    const body = {
      sortBy: "",
      subsearch: "",
      from: 0,
      jobs: true,
      counts: true,
      all_fields: ["category", "raasJobRequisitionType", "country", "state", "city", "type", "RemoteType"],
      pageName: "search-results",
      size: 10,
      clearAll: false,
      jdsource: "facets",
      isSliderEnable: false,
      pageId: "page4",
      siteType: "external",
      keywords: "engineer",
      global: true,
      selected_fields: {
        location: ["India"]
      },
      lang: "en_global",
      deviceType: "desktop",
      country: "global",
      refNum: "CISCISGLOBAL",
      ddoKey: "eagerLoadRefineSearchSession"
    };

    const widgetsRes = await axios.post(widgetsUrl, body, {
      headers: {
        ...commonHeaders,
        'Content-Type': 'application/json',
        'Referer': pageUrl,
        'x-csrf-token': csrfToken,
        'Cookie': cookieHeaders.join('; ')
      }
    });

    console.log('Widgets Status:', widgetsRes.status);
    const result = widgetsRes.data.eagerLoadRefineSearchSession;
    if (result) {
      console.log('eagerLoad Status:', result.status);
      const data = result.data;
      if (data) {
        console.log('Total hits:', data.totalHits || data.hits);
        if (data.jobs && data.jobs.length > 0) {
          console.log(`Successfully retrieved ${data.jobs.length} jobs!`);
          console.log('First job title:', data.jobs[0].title);
        }
      }
    } else {
      console.log('Full response body:', JSON.stringify(widgetsRes.data, null, 2));
    }

  } catch (err) {
    console.error('Error:', err.message);
    if (err.response) {
      console.error('Response:', err.response.data);
    }
  }
}

searchCisco();
