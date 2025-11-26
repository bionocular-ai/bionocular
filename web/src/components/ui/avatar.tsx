"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  name?: string
  email?: string
  src?: string
  fallback?: string
}

// Color palette based on brand colors with variations
const AVATAR_COLORS = [
  { bg: "from-blue-600 to-blue-700", border: "border-blue-500/30" },
  { bg: "from-cyan-600 to-cyan-700", border: "border-cyan-500/30" },
  { bg: "from-indigo-600 to-indigo-700", border: "border-indigo-500/30" },
  { bg: "from-purple-600 to-purple-700", border: "border-purple-500/30" },
  { bg: "from-pink-600 to-pink-700", border: "border-pink-500/30" },
  { bg: "from-rose-600 to-rose-700", border: "border-rose-500/30" },
  { bg: "from-orange-600 to-orange-700", border: "border-orange-500/30" },
  { bg: "from-amber-600 to-amber-700", border: "border-amber-500/30" },
  { bg: "from-emerald-600 to-emerald-700", border: "border-emerald-500/30" },
  { bg: "from-teal-600 to-teal-700", border: "border-teal-500/30" },
] as const

// Generate a consistent color index based on string input
const getColorIndex = (str: string): number => {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash) % AVATAR_COLORS.length
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, name, email, src, fallback, ...props }, ref) => {
    // Generate initials from name or email
    const getInitials = () => {
      if (fallback) return fallback
      if (name) {
        const parts = name.trim().split(/\s+/)
        if (parts.length >= 2) {
          return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
        }
        return name.substring(0, 2).toUpperCase()
      }
      if (email) {
        const emailPart = email.split('@')[0]
        if (emailPart.length >= 2) {
          return emailPart.substring(0, 2).toUpperCase()
        }
        return emailPart[0].toUpperCase() + emailPart[0].toUpperCase()
      }
      return "U"
    }

    const initials = getInitials()
    
    // Get color based on user identifier for consistency
    const colorKey = name || email || "default"
    const colorIndex = getColorIndex(colorKey)
    const colorScheme = AVATAR_COLORS[colorIndex]

    return (
      <div
        ref={ref}
        className={cn(
          "relative flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full",
          `bg-gradient-to-br ${colorScheme.bg}`,
          `border-2 ${colorScheme.border}`,
          "text-white text-sm font-semibold shadow-lg ring-2 ring-white/20",
          className
        )}
        {...props}
      >
        {src ? (
          <img
            src={src}
            alt={name || email || "User"}
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="select-none">{initials}</span>
        )}
      </div>
    )
  }
)
Avatar.displayName = "Avatar"

export { Avatar }

