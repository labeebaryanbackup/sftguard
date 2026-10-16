import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("SFTGuard report viewer", () => {
  it("renders all decision states and the local-only import boundary", () => {
    const html = renderToStaticMarkup(<App />);

    expect(html).toContain("PASS");
    expect(html).toContain("FAIL");
    expect(html).toContain("ABSTAIN");
    expect(html).toContain("Choose local file");
    expect(html).toContain("Nothing is uploaded");
    expect(html).toContain("Claim boundary");
    expect(html).toContain("Privacy boundary");
    expect(html).toContain("Unverified — digest not recomputed");
    expect(html).not.toContain("dangerouslySetInnerHTML");
    expect(html).not.toMatch(/Ã|Â|â€|�/u);
  });

  it("uses accessible landmarks and explicit progress semantics", () => {
    const html = renderToStaticMarkup(<App />);

    expect(html).toContain('href="#report-main"');
    expect(html).toContain('<main id="report-main"');
    expect(html).toContain('aria-label="Available reports"');
    expect(html).toContain('type="file"');
    expect(html).toContain('aria-live="polite"');
  });

});
