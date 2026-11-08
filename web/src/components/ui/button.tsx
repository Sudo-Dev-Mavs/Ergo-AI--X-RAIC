// Botón mínimo con la API de shadcn/ui que espera halo-toast de Cult UI.
import type { ButtonHTMLAttributes } from "react"

import { cn } from "@/lib/utils"

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "ghost"; size?: "default" | "icon" }

export function Button({ className, variant = "default", size = "default", ...props }: Props) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-2",
        variant === "ghost" ? "hover:bg-accent" : "bg-primary text-primary-foreground hover:opacity-90",
        size === "icon" ? "size-9" : "h-9 px-4",
        className,
      )}
      {...props}
    />
  )
}
