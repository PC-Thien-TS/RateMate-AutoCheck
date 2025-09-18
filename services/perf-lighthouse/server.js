import express from 'express';
import lighthouse from 'lighthouse';
import chromeLauncher from 'chrome-launcher';

const app = express();
app.use(express.json());

app.get('/healthz', (_req, res) => res.json({ ok: true }));

app.post('/run', async (req, res) => {
  const url = (req.body?.url || req.query?.url || '').toString();
  if (!url) return res.status(400).json({ error: 'url required' });
  const flags = {
    chromeFlags: ['--headless', '--no-sandbox', '--disable-dev-shm-usage'],
    output: 'json'
  };
  let chrome;
  try {
    chrome = await chromeLauncher.launch({ chromeFlags: flags.chromeFlags, 
      chromePath: process.env.CHROME_PATH });
    const options = { ...flags, port: chrome.port, logLevel: 'error' };
    const runnerResult = await lighthouse(url, options);
    const lhr = runnerResult.lhr;
    const cat = lhr.categories?.performance?.score;
    const audits = lhr.audits || {};
    const out = {
      url,
      performance_score: typeof cat === 'number' ? Math.round(cat * 100) : null,
      metrics: {
        lcp: audits['largest-contentful-paint']?.numericValue,
        cls: audits['cumulative-layout-shift']?.numericValue,
        tti: audits['interactive']?.numericValue,
        tbt: audits['total-blocking-time']?.numericValue,
        si: audits['speed-index']?.numericValue
      },
      auditsSummary: {
        'first-contentful-paint': audits['first-contentful-paint']?.score,
        'largest-contentful-paint': audits['largest-contentful-paint']?.score,
        'cumulative-layout-shift': audits['cumulative-layout-shift']?.score,
        'total-blocking-time': audits['total-blocking-time']?.score
      },
      lhr
    };
    res.json(out);
  } catch (e) {
    res.status(500).json({ error: (e?.message || String(e)) });
  } finally {
    try { if (chrome) await chrome.kill(); } catch (_) {}
  }
});

const port = process.env.PORT || 3001;
app.listen(port, () => console.log(`perf-lighthouse listening on ${port}`));

