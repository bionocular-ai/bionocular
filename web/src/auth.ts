import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"
import { env } from "@/lib/env"
import { isValidEmail, sanitizeInput, validatePassword, rateLimiter } from "@/lib/auth-utils"

export const { handlers, signIn, signOut, auth } = NextAuth({
  secret: env.auth.secret,
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        try {
          // Validate input
          if (!credentials?.email || !credentials?.password) {
            return null
          }

          const email = sanitizeInput(credentials.email as string)
          const password = credentials.password as string

          // Validate email format
          if (!isValidEmail(email)) {
            return null
          }

          // Check rate limiting
          if (rateLimiter.isRateLimited(email)) {
            // Don't reveal that the account exists, just fail silently
            // In production, log this for security monitoring
            console.warn(`Rate limit exceeded for email: ${email}`)
            return null
          }

          // Validate password format
          const passwordValidation = validatePassword(password)
          if (!passwordValidation.valid) {
            return null
          }

          // TODO: Replace with actual database authentication in production
          // Example production implementation:
          // const user = await db.user.findUnique({ where: { email } })
          // if (!user) return null
          // const isValid = await bcrypt.compare(password, user.passwordHash)
          // if (!isValid) return null
          // return { id: user.id, email: user.email, name: user.name }

          // Demo authentication (works in both development and production)
          // Uses DEMO_EMAIL and DEMO_PASSWORD environment variables
          if (email === env.demo.email && password === env.demo.password) {
            rateLimiter.reset(email) // Reset on successful login
            return {
              id: "demo-user-1",
              email: env.demo.email,
              name: "Demo User",
            }
          }

          // If we reach here, credentials are invalid
          // Don't reveal whether email exists or password is wrong
          return null
        } catch (error) {
          // Log error but don't expose details to client
          console.error("Authentication error:", error instanceof Error ? error.message : "Unknown error")
          return null
        }
      },
    }),
  ],
  pages: {
    signIn: "/login",
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id
      }
      return token
    },
    async session({ session, token }) {
      if (session.user && token.id) {
        session.user.id = token.id as string
      }
      return session
    },
  },
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  // Security settings
  trustHost: true, // Required for production deployments
})

