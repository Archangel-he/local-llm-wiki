import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import App from "./App";

vi.mock("./components/GraphWorkspace", () => ({
  GraphWorkspace: ({
    onSelectPage,
  }: {
    onSelectPage: (pageId: string) => void;
    selectedPageId: string;
    maximized: boolean;
    onToggleMaximize: () => void;
  }) => (
    <section data-testid="graph-panel">
      <button
        type="button"
        data-testid="graph-node-node-b"
        onClick={() => onSelectPage("page-b")}
      >
        Lin
      </button>
    </section>
  ),
}));

describe("App", () => {
  it("renders the Obsidian-style workspace regions", () => {
    render(<App />);
    expect(screen.getByTestId("file-tree")).toBeInTheDocument();
    expect(screen.getByTestId("graph-panel")).toBeInTheDocument();
    expect(screen.getByTestId("query-panel")).toBeInTheDocument();
    expect(screen.getByTestId("wiki-panel")).toBeInTheDocument();
    expect(screen.getByText("Graph view")).toBeInTheDocument();
  });

  it("shows the local model and degraded health without blocking content", () => {
    render(<App />);
    expect(screen.getByText(/Local Ollama · qwen3:8b/)).toBeInTheDocument();
    expect(screen.getByTestId("health-trigger")).toHaveTextContent("Degraded");
    expect(screen.getByTestId("wiki-title")).toHaveTextContent(
      "Project Aurora",
    );
  });

  it("updates the inspector when a graph node is selected", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByTestId("graph-node-node-b"));
    expect(screen.getByTestId("wiki-title")).toHaveTextContent("Lin");
    expect(screen.getByTestId("wiki-panel")).toHaveAttribute(
      "data-page-id",
      "page-b",
    );
  });

  it("keeps every pane separator keyboard operable", () => {
    render(<App />);
    const left = screen.getByTestId("left-resizer");
    const right = screen.getByTestId("right-resizer");
    const ask = screen.getByTestId("query-resizer");
    expect(left).toHaveAttribute("aria-valuenow", "248");
    expect(right).toHaveAttribute("aria-valuenow", "310");
    expect(ask).toHaveAttribute("aria-valuenow", "218");

    fireEvent.keyDown(left, { key: "ArrowRight" });
    fireEvent.keyDown(right, { key: "ArrowLeft" });
    fireEvent.keyDown(ask, { key: "ArrowUp" });

    expect(left).toHaveAttribute("aria-valuenow", "260");
    expect(right).toHaveAttribute("aria-valuenow", "322");
    expect(ask).toHaveAttribute("aria-valuenow", "230");
  });

  it("reopens the right sidebar from the right side of the tab bar", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "关闭右侧栏" }));
    expect(screen.queryByTestId("wiki-panel")).not.toBeInTheDocument();

    const reopen = screen.getByRole("button", { name: "展开右侧栏" });
    expect(reopen).toBeVisible();
    await user.click(reopen);
    expect(screen.getByTestId("wiki-panel")).toBeVisible();
  });
});
