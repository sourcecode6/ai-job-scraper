/**
 * Cisco widgets API — understand job structure and correct India location filter.
 */
const axios = require('axios');

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

async function getSession() {
  const res = await axios.get('https://careers.cisco.com/global/en/search-results', {
    headers: { 'User-Agent': UA, 'Accept': 'text/html' },
    timeout: 20000,
  });
  const setCookies = res.headers['set-cookie'] || [];
  const cookieHeader = setCookies.map(c => c.split(';')[0]).join('; ');
  const playEntry = setCookies.find(c => c.startsWith('PLAY_SESSION='));
  const token = playEntry.split(';')[0].replace('PLAY_SESSION=', '').trim();
  const parts = token.split('.');
  const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf-8'));
  return { cookieHeader, csrf: payload.data?.csrfToken };
}

async function widgetsPost(cookieHeader, csrf, body) {
  return axios.post('https://careers.cisco.com/widgets', body, {
    headers: {
      'User-Agent': UA,
      'Content-Type': 'application/json',
      'Accept': 'application/json, text/plain, */*',
      'Referer': 'https://careers.cisco.com/global/en/search-results',
      'x-csrf-token': csrf,
      'Cookie': cookieHeader,
    },
    timeout: 20000,
  });
}

async function test() {
  console.log('Getting session...');
  const { cookieHeader, csrf } = await getSession();

  // Step 1: Get a job WITHOUT filter to see full structure
  const r1 = await widgetsPost(cookieHeader, csrf, {
    sortBy: '', subsearch: '', from: 0, jobs: true, counts: false,
    all_fields: [], pageName: 'search-results', size: 2, clearAll: false,
    jdsource: 'facets', isSliderEnable: false, pageId: 'page4',
    siteType: 'external', keywords: 'engineer', global: true,
    lang: 'en_global', deviceType: 'desktop', country: 'global',
    refNum: 'CISCISGLOBAL', ddoKey: 'refineSearch',
  });
  const jobs1 = r1.data?.refineSearch?.data?.jobs || [];
  const total1 = r1.data?.refineSearch?.data?.totalHits;
  console.log('\nNo filter: total =', total1, '| sample job keys:', jobs1[0] ? Object.keys(jobs1[0]) : 'none');
  if (jobs1[0]) {
    console.log('Sample job location fields:', {
      country: jobs1[0].country,
      state: jobs1[0].state,
      city: jobs1[0].city,
      location: jobs1[0].location,
      RemoteType: jobs1[0].RemoteType,
    });
    console.log('Full first job:', JSON.stringify(jobs1[0], null, 2).slice(0, 800));
  }

  // Step 2: Try different India filter approaches
  const filters = [
    { selected_fields: { country: ['India'] } },
    { selected_fields: { location: ['India'] } },
    { selected_fields: { country: ['IN'] } },
    { selected_fields: { country: ['IND'] } },
  ];

  for (const filter of filters) {
    try {
      const res = await widgetsPost(cookieHeader, csrf, {
        sortBy: '', subsearch: '', from: 0, jobs: true, counts: false,
        all_fields: ['country', 'city'], pageName: 'search-results', size: 5, clearAll: false,
        jdsource: 'facets', isSliderEnable: false, pageId: 'page4',
        siteType: 'external', keywords: 'engineer', global: true,
        lang: 'en_global', deviceType: 'desktop', country: 'global',
        refNum: 'CISCISGLOBAL', ddoKey: 'refineSearch',
        ...filter,
      });
      const jobs = res.data?.refineSearch?.data?.jobs || [];
      const total = res.data?.refineSearch?.data?.totalHits;
      console.log('\nFilter', JSON.stringify(filter), '=> total:', total, '| jobs:', jobs.length);
      if (jobs[0]) console.log('  First job country:', jobs[0].country, '| city:', jobs[0].city);
    } catch(e) { console.log('Filter error:', e.message); }
  }

  // Step 3: Get facets to understand what country values exist
  console.log('\n=== Getting country facets ===');
  try {
    const res = await widgetsPost(cookieHeader, csrf, {
      sortBy: '', subsearch: '', from: 0, jobs: false, counts: true,
      all_fields: ['country'], pageName: 'search-results', size: 0, clearAll: false,
      jdsource: 'facets', isSliderEnable: false, pageId: 'page4',
      siteType: 'external', keywords: 'engineer', global: true,
      lang: 'en_global', deviceType: 'desktop', country: 'global',
      refNum: 'CISCISGLOBAL', ddoKey: 'refineSearch',
    });
    const data = res.data?.refineSearch?.data;
    console.log('Data keys:', data ? Object.keys(data) : 'none');
    if (data?.facets) console.log('Facets:', JSON.stringify(data.facets).slice(0, 800));
    if (data?.counts) console.log('Counts:', JSON.stringify(data.counts).slice(0, 800));
  } catch(e) { console.log('Facets error:', e.message); }
}

test().catch(e => console.error('Fatal:', e.message));
