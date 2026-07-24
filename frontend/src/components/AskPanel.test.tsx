import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AskPanel } from "./AskPanel";

describe("AskPanel", () => {
  it("shows the selected model without presenting a fake answer", async () => {
    const user = userEvent.setup();
    render(
      <AskPanel
        open
        maximized={false}
        onToggleMaximize={() => undefined}
        model={{
          id: "profile-1",
          displayName: "DeepSeek",
          provider: "openai_compatible",
          endpointOrigin: "https://api.deepseek.com",
          modelName: "deepseek-v4-pro",
          hasCredential: true,
          status: "active",
          lastTestedAt: null,
          latencyMs: 824,
          capabilities: { streaming: true, structuredOutput: true },
        }}
      />,
    );

    expect(screen.getByText("LLM Wiki answer")).toBeInTheDocument();
    expect(screen.getByTestId("query-model")).toHaveTextContent(
      "DeepSeek · deepseek-v4-pro",
    );
    await user.selectOptions(screen.getByLabelText("Answer scope"), "workspace");
    await user.type(
      screen.getByLabelText("Ask about this knowledge space..."),
      "When did Aurora start?",
    );
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(screen.getByTestId("query-notice")).toHaveTextContent(
      "does not run a real query yet",
    );
    expect(document.body).not.toHaveTextContent("2025-03-01");
  });
});
