// Cult UI (MIT) · https://github.com/nolly-studio/cult-ui · registry/default/ui/halo-segmented.tsx
"use client"

/**
 * Segmented control (single-select toggle group) aligned with `HaloButtonPolished`:
 * frosted track, gradient rim, sliding thumb using the same layout spring as the button.
 */
import {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react"
import { Toggle } from "@base-ui/react/toggle"
import { ToggleGroup } from "@base-ui/react/toggle-group"
import { motion, useReducedMotion } from "motion/react"

import { cn } from "@/lib/utils"

/** Matches `layoutSpring` in `halo-button-polished.tsx`. */
const layoutSpring = {
  type: "spring" as const,
  bounce: 0.12,
  damping: 34,
  stiffness: 420,
}

export interface HaloSegmentedItem {
  value: string
  label: ReactNode
  disabled?: boolean
}

export interface HaloSegmentedProps {
  items: HaloSegmentedItem[]
  /** Selected value; omit for uncontrolled usage with `defaultValue`. */
  value?: string
  defaultValue?: string
  onValueChange?: (next: string) => void
  className?: string
  /** Frosted track + backdrop blur (matches card/button translucent mode). */
  translucent?: boolean
  disabled?: boolean
}

export function HaloSegmented({
  items,
  value: valueProp,
  defaultValue,
  onValueChange,
  className,
  translucent = true,
  disabled = false,
}: HaloSegmentedProps) {
  const reduceMotion = useReducedMotion() ?? false
  const trackRef = useRef<HTMLDivElement>(null)
  const itemRefs = useRef<Map<string, HTMLButtonElement>>(new Map())
  const [thumb, setThumb] = useState({ x: 0, width: 0 })

  const isControlled = valueProp !== undefined
  const [uncontrolled, setUncontrolled] = useState(
    defaultValue ?? items[0]?.value ?? ""
  )
  const selected = isControlled ? (valueProp ?? "") : uncontrolled

  const setSelected = useCallback(
    (next: string) => {
      if (!isControlled) {
        setUncontrolled(next)
      }
      onValueChange?.(next)
    },
    [isControlled, onValueChange]
  )

  const groupValue = useMemo(() => (selected ? [selected] : []), [selected])

  const measureThumb = useCallback(() => {
    const track = trackRef.current
    const active = selected ? itemRefs.current.get(selected) : undefined
    if (!(track && active)) {
      setThumb({ x: 0, width: 0 })
      return
    }
    const tr = track.getBoundingClientRect()
    const br = active.getBoundingClientRect()
    setThumb({
      x: br.left - tr.left,
      width: br.width,
    })
  }, [selected])

  useLayoutEffect(() => {
    measureThumb()
  }, [measureThumb])

  useLayoutEffect(() => {
    const track = trackRef.current
    if (!track || typeof ResizeObserver === "undefined") {
      return
    }
    const ro = new ResizeObserver(() => measureThumb())
    ro.observe(track)
    // Adaptación ErgoAI: también al cambiar el ancho de cada opción y al terminar de cargar la fuente.
    itemRefs.current.forEach((item) => ro.observe(item))
    let vigente = true
    void document.fonts?.ready.then(() => vigente && measureThumb())
    return () => {
      vigente = false
      ro.disconnect()
    }
  }, [measureThumb])

  /** Modo industrial (translucent=false): grupo denso estilo software de planta, no píldoras móviles. */
  const industrial = !translucent
  const radio = industrial ? "rounded-md" : "rounded-full"

  return (
    <div
      className={cn(
        "relative inline-flex max-w-full p-px",
        radio,
        className
      )}
    >
      {!industrial && (
        <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", radio)}>
          <motion.div
            animate={{ opacity: 0.72 }}
            className="absolute inset-x-0 bottom-0 h-1/2"
            transition={{ duration: 0.25, ease: "easeOut" }}
          >
            <motion.div
              animate={{ left: ["-5%", "75%", "-5%"] }}
              className="-bottom-4 absolute h-14 w-44 blur-xl"
              style={{ background: "linear-gradient(90deg, #13233b, #3a4c66, #8a99ad, #13233b)" }}
              transition={{
                duration: reduceMotion ? 0.01 : 6,
                ease: "easeInOut",
                repeat: reduceMotion ? 0 : Number.POSITIVE_INFINITY,
              }}
            />
          </motion.div>
        </div>
      )}

      <div
        className={cn(
          "relative border",
          radio,
          industrial
            ? "border-slate-200 bg-slate-100 shadow-none"
            : cn(
                "border-border/90",
                "shadow-[0_1px_0_rgba(255,255,255,0.1)_inset,0_1px_2px_rgba(0,0,0,0.04),0_4px_14px_rgba(0,0,0,0.05)]",
                "backdrop-blur-xl backdrop-saturate-150",
              ),
        )}
        style={
          industrial
            ? undefined
            : {
                background:
                  "linear-gradient(to bottom, color-mix(in oklch, var(--card) 82%, transparent) 0%, color-mix(in oklch, var(--card) 70%, transparent) 100%)",
              }
        }
      >
        <div className={cn("relative", industrial ? "p-0.5" : "p-1")} ref={trackRef}>
          <motion.div
            animate={{
              x: thumb.width > 0 ? thumb.x : 0,
              width: thumb.width,
            }}
            aria-hidden
            className={cn(
              "pointer-events-none absolute right-auto left-0",
              industrial
                ? "top-0.5 bottom-0.5 rounded-[5px] border border-[#003876]/40 bg-[#003876] shadow-none"
                : cn(
                    "top-1 bottom-1 rounded-full border border-border/70",
                    "bg-gradient-to-b from-background/95 to-muted/40",
                    "shadow-[0_1px_0_rgba(255,255,255,0.12)_inset,0_2px_8px_rgba(0,0,0,0.06)]",
                  ),
            )}
            initial={false}
            transition={reduceMotion ? { duration: 0 } : layoutSpring}
          />

          <ToggleGroup
            className="relative z-1 flex min-w-0 gap-0"
            disabled={disabled}
            multiple={false}
            onValueChange={(next) => {
              const first = next[0]
              if (typeof first === "string") {
                setSelected(first)
              }
            }}
            value={groupValue}
          >
            {items.map((item) => (
              <Toggle
                className={cn(
                  "relative flex shrink-0 flex-auto items-center justify-center whitespace-nowrap",
                  "font-medium tracking-tight antialiased outline-none transition-colors duration-200 ease-out",
                  "focus-visible:ring-2 focus-visible:ring-ring/35 focus-visible:ring-offset-1",
                  "disabled:pointer-events-none disabled:opacity-50",
                  industrial
                    ? cn(
                        "min-h-8 rounded-[5px] px-3 py-1.5 text-[13px] text-slate-600",
                        "aria-pressed:text-white",
                      )
                    : cn(
                        "min-h-9 rounded-full px-3.5 py-2 text-muted-foreground text-sm",
                        "aria-pressed:text-foreground",
                      ),
                )}
                disabled={item.disabled}
                key={item.value}
                ref={(el) => {
                  if (el) {
                    itemRefs.current.set(item.value, el)
                  } else {
                    itemRefs.current.delete(item.value)
                  }
                }}
                value={item.value}
              >
                {item.label}
              </Toggle>
            ))}
          </ToggleGroup>
        </div>
      </div>
    </div>
  )
}
