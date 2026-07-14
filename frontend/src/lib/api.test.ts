import { describe, expect, it } from "vitest";
import { fmtDay, fmtDayLong, fmtMin, fmtTime } from "./api";

describe("fmtMin", () => {
  it("formats minutes as h/m", () => {
    expect(fmtMin(450)).toBe("7h 30m");
    expect(fmtMin(60)).toBe("1h 00m");
  });
  it("handles null/undefined", () => {
    expect(fmtMin(null)).toBe("—");
    expect(fmtMin(undefined)).toBe("—");
  });
});

describe("fmtTime", () => {
  it("renders local wall-clock time in the session timezone", () => {
    expect(fmtTime("2026-06-01T22:00:00+00:00", "Europe/London")).toBe("23:00");
    expect(fmtTime(null)).toBe("—");
  });
});

describe("fmtDay / fmtDayLong", () => {
  it("shows weekday and dd/mm for chart axes", () => {
    expect(fmtDay("2026-07-13")).toBe("Mon 13/07");
    expect(fmtDay("2026-05-20")).toBe("Wed 20/05");
  });
  it("shows full weekday and dd/mm/yyyy for tooltips", () => {
    expect(fmtDayLong("2026-07-13")).toBe("Monday 13/07/2026");
  });
});
