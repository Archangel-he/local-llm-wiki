import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AskPanel } from "./AskPanel";

describe("AskPanel", () => {
  it("returns the deterministic mock answer with a citation", async () => {
    const user = userEvent.setup();
    render(
      <AskPanel
        open
        onToggle={() => undefined}
        maximized={false}
        onToggleMaximize={() => undefined}
      />,
    );

    await user.selectOptions(screen.getByLabelText("问答范围"), "workspace");
    await user.type(screen.getByLabelText("输入问题"), "Aurora 什么时候启动？");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(screen.getByTestId("mock-answer")).toHaveTextContent("2025-03-01");
    expect(screen.getByTestId("mock-answer")).toHaveTextContent("aurora-a.md");
    expect(screen.getByRole("button", { name: "Save to Wiki" })).toBeEnabled();
  });
});
