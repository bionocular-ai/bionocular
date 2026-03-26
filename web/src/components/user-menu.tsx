"use client"

import { signOut } from "@/lib/supabase/hooks";
import { Avatar } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { LogOut, Settings, CreditCard } from "lucide-react"
import { useEffect, useRef } from "react"

interface UserMenuProps {
  email?: string | null
  name?: string | null
  image?: string | null
}

export function UserMenu({ email, name, image }: UserMenuProps) {
  const displayName = name || email?.split("@")[0] || "User"
  const buttonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const button = buttonRef.current
    if (!button) return

    const handleBlur = () => {
      // Remove any focus styles when clicking away
      button.style.outline = 'none'
      button.style.boxShadow = 'none'
    }

    button.addEventListener('blur', handleBlur)
    return () => button.removeEventListener('blur', handleBlur)
  }, [])

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button 
          ref={buttonRef}
          className="rounded-full transition-transform hover:scale-105 active:scale-95 focus:outline-none focus-visible:outline-none focus:ring-0 focus-visible:ring-0"
          style={{ outline: 'none !important', boxShadow: 'none !important' } as React.CSSProperties}
        >
          <Avatar
            name={name || undefined}
            email={email || undefined}
            src={image || undefined}
            className="cursor-pointer hover:shadow-md transition-all duration-200"
          />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="px-3 py-2.5">
          <div className="flex flex-col space-y-0.5">
            <p className="text-sm font-semibold leading-tight text-gray-900">{displayName}</p>
            {email && (
              <p className="text-xs leading-tight text-gray-500 mt-0.5">{email}</p>
            )}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="cursor-pointer">
          <Settings className="mr-2 h-4 w-4 text-gray-600" />
          <span>Profile Settings</span>
        </DropdownMenuItem>
        <DropdownMenuItem className="cursor-pointer">
          <CreditCard className="mr-2 h-4 w-4 text-gray-600" />
          <span>Billing/Team</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="cursor-pointer text-red-600 hover:text-red-700 hover:bg-red-50 focus:text-red-700 focus:bg-red-50"
          onClick={() => signOut({ callbackUrl: "/" })}
        >
          <LogOut className="mr-2 h-4 w-4" />
          <span>Sign out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

