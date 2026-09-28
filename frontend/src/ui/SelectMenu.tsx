import { Check, ChevronDown } from "lucide-react";
import * as SelectPrimitive from "@radix-ui/react-select";

export interface SelectOption {
  value: string;
  label: string;
}

/** Themed single-select built on Radix Select so the popup matches the
 *  console theme instead of the browser's native dropdown rendering. */
export function SelectMenu({ value, onValueChange, options, ariaLabel, id, disabled = false, placeholder }: {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  ariaLabel: string;
  id?: string;
  disabled?: boolean;
  placeholder?: string;
}) {
  const current = options.find((option) => option.value === value);

  return <SelectPrimitive.Root value={value} onValueChange={onValueChange}>
    <SelectPrimitive.Trigger className="select-trigger" id={id} aria-label={ariaLabel} disabled={disabled}>
      <SelectPrimitive.Value placeholder={placeholder ?? "Select"}>{current?.label}</SelectPrimitive.Value>
      <SelectPrimitive.Icon className="select-trigger-icon"><ChevronDown size={14} aria-hidden="true" /></SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content className="select-content" position="popper" sideOffset={4} aria-label={undefined}>
        <SelectPrimitive.Viewport className="select-viewport">
          {options.map((option) => <SelectPrimitive.Item className="select-item" key={option.value} value={option.value}>
            <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
            <SelectPrimitive.ItemIndicator className="select-item-indicator"><Check size={13} aria-hidden="true" /></SelectPrimitive.ItemIndicator>
          </SelectPrimitive.Item>)}
        </SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  </SelectPrimitive.Root>;
}
