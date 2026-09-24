import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "./HomePage";


describe("HomePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify([{ id: "orders", name: "Orders", status: "ready" }]),
          {
            headers: { "Content-Type": "application/json" },
            status: 200,
          },
        ),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the generated app shell and loaded modules", async () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { name: "Generated Application" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Orders")).toBeInTheDocument();
    expect(screen.getByText("Implementation Area")).toBeInTheDocument();
  });
});

