import { describe, expect, it } from "vitest";

import {
  DEFAULT_CONFIG,
  activeProfile,
  matchesUrlPattern,
} from "../src/shared/config";

describe("matchesUrlPattern", () => {
  it("matches the dev app URL against the Mock profile's app pattern", () => {
    const profile = activeProfile(DEFAULT_CONFIG);
    expect(profile).toBeDefined();
    expect(
      matchesUrlPattern(profile!.appUrlPattern, "http://localhost:3010/record-description"),
    ).toBe(true);
  });

  it("rejects a different origin trying to pose as the app page", () => {
    const pattern = "http://localhost:3010/*";
    expect(matchesUrlPattern(pattern, "http://evil.example/record-description")).toBe(false);
    expect(matchesUrlPattern(pattern, "https://localhost:3011/")).toBe(false);
  });

  it("treats '*' as a wildcard segment boundary in a wildcard pattern", () => {
    expect(matchesUrlPattern("https://*.szpital.pl/*", "https://crm.szpital.pl/pacjent")).toBe(
      true,
    );
    expect(matchesUrlPattern("https://*.szpital.pl/*", "https://crm.other.pl/pacjent")).toBe(false);
  });

  it("is a plain anchored match when the pattern has no wildcard", () => {
    expect(matchesUrlPattern("http://localhost:3010/", "http://localhost:3010/")).toBe(true);
    expect(matchesUrlPattern("http://localhost:3010/", "http://localhost:3010/x")).toBe(false);
  });
});
