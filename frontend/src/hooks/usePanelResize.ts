import { useCallback, useEffect, useRef, useState } from "react";

interface ResizeOptions {
  initial: number;
  min: number;
  max: number;
  axis: "x" | "y";
  invert?: boolean;
}

export function usePanelResize({
  initial,
  min,
  max,
  axis,
  invert = false,
}: ResizeOptions) {
  const [size, setSize] = useState(initial);
  const dragRef = useRef<{ origin: number; startSize: number } | null>(null);

  const stopDragging = useCallback(() => {
    dragRef.current = null;
    document.body.classList.remove("is-resizing");
  }, []);

  useEffect(() => {
    const onPointerMove = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      const pointer = axis === "x" ? event.clientX : event.clientY;
      const rawDelta = pointer - drag.origin;
      const delta = invert ? -rawDelta : rawDelta;
      setSize(Math.min(max, Math.max(min, drag.startSize + delta)));
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", stopDragging);
    window.addEventListener("pointercancel", stopDragging);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", stopDragging);
      window.removeEventListener("pointercancel", stopDragging);
    };
  }, [axis, invert, max, min, stopDragging]);

  const onPointerDown = useCallback(
    (event: React.PointerEvent) => {
      const origin = axis === "x" ? event.clientX : event.clientY;
      dragRef.current = { origin, startSize: size };
      document.body.classList.add("is-resizing");
      event.currentTarget.setPointerCapture?.(event.pointerId);
      event.preventDefault();
    },
    [axis, size],
  );

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      const direction =
        event.key === "ArrowRight" || event.key === "ArrowDown"
          ? 1
          : event.key === "ArrowLeft" || event.key === "ArrowUp"
            ? -1
            : 0;
      if (!direction) return;
      const adjustedDirection = invert ? -direction : direction;
      setSize((current) =>
        Math.min(max, Math.max(min, current + adjustedDirection * 12)),
      );
      event.preventDefault();
    },
    [invert, max, min],
  );

  return { size, onPointerDown, onKeyDown };
}
