import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, refreshCsrf } from "./api";

afterEach(() => vi.unstubAllGlobals());
describe("session transport", () => {
  it("uses same-origin cookies, JSON CSRF, and refreshes the rotated token after login", async () => {
    const transport = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrfToken: "before-login" })),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ email: "demo@example.test" })),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ csrfToken: "after-login" })),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", transport);
    await refreshCsrf();
    await api("auth/login/", "POST", {
      email: "demo@example.test",
      password: "synthetic-test-only",
    });
    await api("auth/logout/", "POST", {});
    expect(transport.mock.calls[1][1]).toMatchObject({
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": "before-login",
        "Content-Type": "application/json",
      },
    });
    expect(transport.mock.calls[2][0]).toBe("/api/v1/auth/csrf/");
    expect(transport.mock.calls[3][1].headers["X-CSRFToken"]).toBe(
      "after-login",
    );
  });
  it("surfaces API errors and does not retry non-idempotent writes", async () => {
    const transport = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { message: "Insufficient stock.", details: {} },
        }),
        { status: 409 },
      ),
    );
    vi.stubGlobal("fetch", transport);
    await expect(api("sales/", "POST", { items: [] })).rejects.toBeInstanceOf(
      ApiError,
    );
    expect(transport).toHaveBeenCalledTimes(1);
  });
});
