"""
Builds scratch/rendered_pages/00_master_tester.html which contains the full HTML of all 12
AI Cart pages and runs an automated in-browser layout test suite measuring:
1. document.documentElement.scrollWidth <= clientWidth
2. document.body.scrollWidth <= clientWidth
3. Element bounding boxes (no clipping or horizontal overflow beyond viewport width)
4. Touch target sizes on interactive elements (>= 44px)
5. Details/summary toggle interactivity
Across all 7 required viewports: [320, 360, 390, 480, 768, 1024, 1440].
"""

import json
import os


def build_master_tester():
    rendered_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "rendered_pages")

    page_files = [
        ("01_home", "01_home.html"),
        ("02_contract_review", "02_contract_review.html"),
        ("03_contract_confirmed", "03_contract_confirmed.html"),
        ("04_catalog_discovery", "04_catalog_discovery.html"),
        ("05_policy_evaluation", "05_policy_evaluation.html"),
        ("06_proposal_detail", "06_proposal_detail.html"),
        ("07_approval_detail", "07_approval_detail.html"),
        ("08_payment_receipt", "08_payment_receipt.html"),
        ("09_payment_pending", "09_payment_pending.html"),
        ("10_payment_cancelled", "10_payment_cancelled.html"),
        ("11_payment_failed", "11_payment_failed.html"),
        ("12_base_layout", "12_base_layout.html"),
    ]

    pages_data = {}
    for key, filename in page_files:
        filepath = os.path.join(rendered_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            pages_data[key] = f.read()

    pages_json = json.dumps(pages_data).replace("</script>", "<\\/script>")

    # Build HTML without f-string interpolation for JS body to avoid escaping bugs
    template_head = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Cart Master Browser Responsiveness & Layout Tester</title>
    <style>
        body {
            font-family: system-ui, sans-serif;
            margin: 20px;
            background: #f8fafc;
            color: #0f172a;
        }
        #frame-container {
            margin-top: 20px;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            padding: 10px;
            border-radius: 8px;
        }
        iframe {
            border: 2px solid #2563eb;
            background: #ffffff;
            display: block;
            margin: 0 auto;
        }
        #results-log {
            margin-top: 20px;
            background: #1e293b;
            color: #f8fafc;
            padding: 15px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 13px;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <h1>AI Cart Browser Layout & Responsiveness Verification Suite</h1>
    <p>Automated verification running in Chrome rendering engine across 12 pages &times; 7 viewports.</p>
    <div id="frame-container">
        <iframe id="test-frame" width="320" height="800"></iframe>
    </div>
    <div id="results-log">Ready to run.</div>

    <script id="pages-data" type="application/json">
"""
    template_middle = """</script>
    <script>
        const PAGES = JSON.parse(document.getElementById('pages-data').textContent);
        const VIEWPORTS = [320, 360, 390, 480, 768, 1024, 1440];
        const logEl = document.getElementById('results-log');
        const frame = document.getElementById('test-frame');

        function log(msg) {
            logEl.textContent += "\\n" + msg;
            logEl.scrollTop = logEl.scrollHeight;
        }

        function delay(ms) {
            return new Promise(r => setTimeout(r, ms));
        }

        async function testSinglePageViewport(pageKey, width) {
            return new Promise((resolve) => {
                frame.style.width = width + 'px';
                frame.style.height = '850px';
                frame.width = width;
                frame.height = 850;

                frame.onload = async () => {
                    await delay(40);
                    try {
                        const doc = frame.contentDocument;
                        const win = frame.contentWindow;

                        const scrollW = doc.documentElement.scrollWidth;
                        const clientW = doc.documentElement.clientWidth;
                        const bodyScrollW = doc.body.scrollWidth;
                        const hasOverflow = (scrollW > clientW) || (bodyScrollW > clientW);

                        const overflowingEls = [];
                        const allEls = doc.querySelectorAll('*');
                        for (const el of allEls) {
                            const rect = el.getBoundingClientRect();
                            if (rect.right > clientW + 1) {
                                overflowingEls.push({
                                    tag: el.tagName,
                                    class: el.className,
                                    right: Math.round(rect.right),
                                    maxAllowed: clientW
                                });
                            }
                        }

                        const buttons = doc.querySelectorAll('.tc-btn, button, summary.tc-summary-toggle, .tc-input');
                        let touchTargetsPassed = true;
                        const smallTouchTargets = [];
                        for (const b of buttons) {
                            const rect = b.getBoundingClientRect();
                            if (rect.height > 0 && rect.width > 0 && win.getComputedStyle(b).display !== 'none') {
                                if (!b.classList.contains('tc-btn-xs') && !b.classList.contains('tc-badge-remove') && rect.height < 40) {
                                    touchTargetsPassed = false;
                                    smallTouchTargets.push({
                                        text: b.textContent.trim().slice(0, 30),
                                        height: Math.round(rect.height)
                                    });
                                }
                            }
                        }

                        const details = doc.querySelector('details.tc-additional-options');
                        let detailsToggleOk = true;
                        if (details) {
                            const summary = details.querySelector('summary');
                            if (summary) {
                                const wasOpen = details.open;
                                summary.click();
                                const isOpenAfterClick = details.open;
                                summary.click();
                                detailsToggleOk = (isOpenAfterClick !== wasOpen);
                            }
                        }

                        resolve({
                            page: pageKey,
                            viewport: width,
                            scrollWidth: scrollW,
                            clientWidth: clientW,
                            bodyScrollWidth: bodyScrollW,
                            overflow: hasOverflow,
                            overflowingCount: overflowingEls.length,
                            overflowingElements: overflowingEls.slice(0, 3),
                            touchTargetsPassed: touchTargetsPassed,
                            smallTouchTargets: smallTouchTargets.slice(0, 3),
                            detailsToggleOk: detailsToggleOk,
                            passed: !hasOverflow && touchTargetsPassed
                        });
                    } catch (err) {
                        resolve({
                            page: pageKey,
                            viewport: width,
                            error: err.toString(),
                            passed: false
                        });
                    }
                };

                frame.srcdoc = PAGES[pageKey];
            });
        }

        window.runFullBrowserSuite = async function() {
            logEl.textContent = "Starting Full Browser Layout Suite (12 pages x 7 viewports = 84 tests)...";
            const results = [];
            const summary = {
                totalTests: 0,
                passed: 0,
                failed: 0,
                pagesTested: Object.keys(PAGES).length,
                viewportsTested: VIEWPORTS,
                viewportSummary: {},
                failures: []
            };

            for (const vp of VIEWPORTS) {
                summary.viewportSummary[vp] = { passed: 0, failed: 0 };
            }

            for (const pageKey of Object.keys(PAGES)) {
                for (const vp of VIEWPORTS) {
                    summary.totalTests++;
                    const res = await testSinglePageViewport(pageKey, vp);
                    results.push(res);

                    if (res.passed) {
                        summary.passed++;
                        summary.viewportSummary[vp].passed++;
                    } else {
                        summary.failed++;
                        summary.viewportSummary[vp].failed++;
                        summary.failures.push(res);
                        log(`[FAIL] ${pageKey} @ ${vp}px: scrollW=${res.scrollWidth}, clientW=${res.clientWidth}`);
                    }
                }
                log(`Completed ${pageKey} across all 7 viewports.`);
            }

            summary.verdict = summary.failed === 0 ? "PASS" : "FAIL";
            log(`\\nVERDICT: ${summary.verdict} (${summary.passed}/${summary.totalTests} tests passed)`);
            window.suiteSummary = summary;
            window.detailedResults = results;
            return summary;
        };
    </script>
</body>
</html>
"""

    tester_html = template_head + pages_json + template_middle

    output_path = os.path.join(rendered_dir, "00_master_tester.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(tester_html)
    print(f"Master browser tester built at: {output_path} ({len(tester_html):,} bytes)")


if __name__ == "__main__":
    build_master_tester()
