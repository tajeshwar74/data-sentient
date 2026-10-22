import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
};

export function Button({ className, variant = "primary", size = "md", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
        variant === "primary" && "bg-[#237b62] text-white hover:bg-[#196950]",
        variant === "secondary" && "border border-[#e5e9e7] bg-white text-[#25342f] hover:bg-[#f5f8f6]",
        variant === "ghost" && "text-[#67736e] hover:bg-[#f2f5f3] hover:text-[#25342f]",
        size === "sm" ? "h-8 px-3 text-xs" : "h-10 px-4 text-sm",
        className,
      )}
      {...props}
    />
  );
}
