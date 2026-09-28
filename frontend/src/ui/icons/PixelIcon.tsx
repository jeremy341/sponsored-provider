import { pixelIconData, type PixelIconName } from "./pixelIconData";

type PixelIconBaseProps = {
  name: PixelIconName;
  size?: 16 | 20 | 24 | 32;
  className?: string;
};

type PixelIconProps = PixelIconBaseProps & (
  | { decorative?: true; label?: never }
  | { decorative: false; label: string }
);

export function PixelIcon({ name, size = 16, className, decorative = true, label }: PixelIconProps) {
  const rows = pixelIconData[name];

  if (!rows || (!decorative && !label?.trim())) return null;

  const pixels: Array<{ x: number; y: number }> = [];

  rows.forEach((row, y) => {
    Array.from(row).forEach((cell, x) => {
      if (cell === "1") pixels.push({ x, y });
    });
  });

  return <svg
    viewBox="0 0 8 8"
    width={size}
    height={size}
    className={["pixel-icon-svg", className].filter(Boolean).join(" ")}
    focusable="false"
    aria-hidden={decorative ? true : undefined}
    role={decorative ? undefined : "img"}
    aria-label={decorative ? undefined : label}
  >
    {pixels.map(({ x, y }) => <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill="currentColor" />)}
  </svg>;
}
