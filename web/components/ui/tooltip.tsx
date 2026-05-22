"use client";

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import type { ComponentPropsWithoutRef, ComponentRef } from "react";
import { forwardRef } from "react";

/*
 * Thin styled wrapper around Radix Tooltip. Uses Peerbench design tokens
 * directly (docs/design.md). Not a shadcn-vendored component because shadcn
 * init would overwrite the existing @theme palette in app/globals.css; the
 * tokens are the source of truth.
 *
 * Usage:
 *   <TooltipProvider delayDuration={150}>
 *     <Tooltip>
 *       <TooltipTrigger asChild>...</TooltipTrigger>
 *       <TooltipContent>...</TooltipContent>
 *     </Tooltip>
 *   </TooltipProvider>
 *
 * The Provider is mounted once at the root (app/layout.tsx).
 */

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export const TooltipContent = forwardRef<
  ComponentRef<typeof TooltipPrimitive.Content>,
  ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={[
        "z-50 max-w-xs rounded-sm border border-border bg-surface px-2 py-1.5",
        "text-table-data text-text shadow-sm",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = "TooltipContent";
