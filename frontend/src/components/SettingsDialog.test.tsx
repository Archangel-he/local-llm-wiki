import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { ModelProfile } from "../mvp1/contracts";
import { SettingsDialog } from "./SettingsDialog";

describe("SettingsDialog", () => {
  it("never echoes a saved API key", async () => {
    const user = userEvent.setup();
    render(<SettingsDialog open onClose={() => undefined} />);

    const apiKey = screen.getByTestId("api-key-input");
    await user.type(apiKey, "super-secret-value");
    await user.click(
      screen.getByRole("button", { name: "Connect & load models" }),
    );
    await user.click(
      screen.getByLabelText(
        "I understand source content may be sent to this external endpoint.",
      ),
    );
    await user.click(
      screen.getByRole("button", { name: "Save configuration" }),
    );

    expect(apiKey).toHaveValue("");
    expect(screen.getByTestId("credential-state")).toHaveTextContent(
      "stored securely",
    );
    expect(document.body).not.toHaveTextContent("super-secret-value");
  });

  it("shows connection progress and deletes a saved profile after confirmation", async () => {
    const user = userEvent.setup();
    const profile: ModelProfile = {
      id: "profile-1",
      displayName: "DeepSeek",
      provider: "openai_compatible" as const,
      endpointOrigin: "https://api.deepseek.com",
      modelName: "deepseek-v4-pro",
      hasCredential: true,
      status: "untested" as const,
      lastTestedAt: null,
      latencyMs: null,
      capabilities: { streaming: false, structuredOutput: false },
    };
    let finishTest: ((value: ModelProfile) => void) | undefined;
    const onTestProfile = vi.fn(
      () =>
        new Promise<ModelProfile>((resolve) => {
          finishTest = resolve;
        }),
    );
    const onDeleteProfile = vi.fn(async () => undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <SettingsDialog
        open
        onClose={() => undefined}
        profiles={[profile]}
        onTestProfile={onTestProfile}
        onDeleteProfile={onDeleteProfile}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Test" }));
    expect(screen.getByRole("button", { name: "Testing" })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Testing DeepSeek. Please wait",
    );
    finishTest?.({ ...profile, status: "active", latencyMs: 868 });
    expect(await screen.findByRole("status")).toHaveTextContent("868 ms");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(window.confirm).toHaveBeenCalled();
    expect(onDeleteProfile).toHaveBeenCalledWith("profile-1");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "DeepSeek was deleted",
    );
  });
});
