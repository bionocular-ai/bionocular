import { auth } from "@/auth"
import { NextResponse } from "next/server"
import { ROUTES, PUBLIC_ROUTES } from "@/lib/constants"

// Next.js 16 middleware pattern - using auth as proxy
export default auth((req) => {
  const { pathname } = req.nextUrl
  const isLoggedIn = !!req.auth

  // Check if route is public
  const isPublicRoute = PUBLIC_ROUTES.includes(pathname as typeof PUBLIC_ROUTES[number])

  // If user is not logged in and trying to access protected route
  if (!isLoggedIn && !isPublicRoute) {
    const loginUrl = new URL(ROUTES.LOGIN, req.url)
    // Validate callbackUrl to prevent open redirects
    if (pathname.startsWith('/') && !pathname.startsWith('//')) {
      loginUrl.searchParams.set("callbackUrl", pathname)
    }
    return NextResponse.redirect(loginUrl)
  }

  // If user is logged in and trying to access login page, redirect to dashboard
  if (isLoggedIn && pathname === ROUTES.LOGIN) {
    return NextResponse.redirect(new URL(ROUTES.DASHBOARD, req.url))
  }

  return NextResponse.next()
})

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - static media files (images, videos, etc.)
     */
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|mp4|webm|mov|avi|ico)$).*)",
  ],
}

