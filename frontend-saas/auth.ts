import NextAuth from "next-auth"
import Google from "next-auth/providers/google"
import Credentials from "next-auth/providers/credentials"
import Kakao from "@/lib/auth/providers/kakao"
import Naver from "@/lib/auth/providers/naver"
import { db } from "@/lib/db/drizzle"
import { users } from "@/lib/db/schema"
import { eq } from "drizzle-orm"
import bcrypt from "bcryptjs"

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Google({
      clientId: process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    Kakao({
      clientId: process.env.NEXT_PUBLIC_KAKAO_CLIENT_ID!,
      clientSecret: "",
    }),
    Naver({
      clientId: process.env.NEXT_PUBLIC_NAVER_CLIENT_ID!,
      clientSecret: process.env.NAVER_CLIENT_SECRET!,
    }),
    Credentials({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null
        }

        const [user] = await db
          .select()
          .from(users)
          .where(eq(users.email, credentials.email as string))
          .limit(1)

        if (!user || !user.passwordHash) {
          return null
        }

        const isPasswordValid = await bcrypt.compare(
          credentials.password as string,
          user.passwordHash
        )

        if (!isPasswordValid) {
          return null
        }

        return {
          id: user.id.toString(),
          email: user.email,
          name: user.name,
        }
      }
    }),
  ],
  callbacks: {
    async signIn({ user, account, profile }) {
      // Credentials provider는 authorize에서 이미 처리됨
      if (account?.provider === 'credentials') {
        return true
      }

      // OAuth providers (Google, Kakao, Naver)
      if (!user.email) return false

      try {
        const [existingUser] = await db
          .select()
          .from(users)
          .where(eq(users.email, user.email))
          .limit(1)

        if (!existingUser) {
          // 새 사용자 생성
          await db.insert(users).values({
            email: user.email,
            name: user.name || '',
          })
        }

        return true
      } catch (error) {
        console.error('[AUTH] 사용자 생성/조회 오류:', error)
        return false
      }
    },
    async session({ session, token }) {
      // 세션에 사용자 ID 추가
      if (session.user && token.email) {
        try {
          const [dbUser] = await db
            .select()
            .from(users)
            .where(eq(users.email, token.email as string))
            .limit(1)

          if (dbUser) {
            session.user.id = dbUser.id.toString()
          }
        } catch (error) {
          console.error('[AUTH] 세션 사용자 조회 오류:', error)
        }
      }
      return session
    },
  },
  pages: {
    signIn: '/login',
  },
  session: {
    strategy: "jwt",
  },
})
