import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/** Open the themed Radix select by its accessible label and pick an option. */
export async function pickSelect(label: RegExp | string, option: RegExp | string): Promise<void> {
  await userEvent.click(screen.getByRole("combobox", { name: label }));
  await userEvent.click(await screen.findByRole("option", { name: option }));
}
