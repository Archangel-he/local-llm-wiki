import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingsDialog } from "./SettingsDialog";

describe("SettingsDialog", () => {
  it("never echoes a saved API key", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open onClose={() => undefined} />);

    await user.click(
      screen.getByRole("tab", { name: "OpenAI-compatible API" }),
    );
    const apiKey = screen.getByTestId("api-key-input");
    await user.type(apiKey, "super-secret-value");
    await user.click(screen.getByRole("button", { name: "Save credential" }));

    expect(apiKey).toHaveValue("");
    expect(screen.getByTestId("credential-state")).toHaveTextContent(
      "cannot be read",
    );
    expect(document.body).not.toHaveTextContent("super-secret-value");
  });
});
