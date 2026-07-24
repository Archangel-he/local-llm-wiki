import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { FileExplorer } from "./FileExplorer";

describe("FileExplorer", () => {
  it("expands, collapses, filters, and selects a page", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <FileExplorer selectedPageId="page-a" onSelectPage={onSelect} />,
    );

    const wikiSection = screen.getByTestId("tree-section-wiki");
    expect(wikiSection).toHaveAttribute("aria-expanded", "true");
    await user.click(wikiSection);
    expect(wikiSection).toHaveAttribute("aria-expanded", "false");
    await user.click(wikiSection);
    await user.click(screen.getByTestId("tree-item-wiki-entities"));
    expect(onSelect).toHaveBeenCalledWith("page-b");

    await user.type(screen.getByLabelText("Filter files..."), "orphan");
    expect(screen.getByTestId("tree-item-lint-orphan")).toBeVisible();
    expect(screen.queryByTestId("tree-item-raw-a")).not.toBeInTheDocument();
  });
});
