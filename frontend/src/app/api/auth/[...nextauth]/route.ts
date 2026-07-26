import NextAuth, { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import axios from "axios";

// 擴充 NextAuth 的內建型別，讓 TypeScript 認識 backendToken
declare module "next-auth" {
  interface Session {
    backendToken?: string;
  }
  interface User {
    backendToken?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    backendToken?: string;
  }
}

// 容器內部 Server-side 通訊優先使用 http://web:8000，避開 localhost 斷線問題
const BACKEND_URL =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://web:8000";

  export const authOptions: NextAuthOptions = {
    providers: [
      GoogleProvider({
        clientId: process.env.GOOGLE_CLIENT_ID || "",
        clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
      }),
    ],
    callbacks: {
      async signIn({ user, account }) {
        if (account?.provider === "google") {
          try {
            const BACKEND_URL =
              process.env.BACKEND_INTERNAL_URL ||
              process.env.NEXT_PUBLIC_API_BASE_URL ||
              "http://web:8000";
  
            const response = await axios.post(
              `${BACKEND_URL}/api/auth/google/`,
              {
                access_token: account.access_token,
              }
            );
  
            // 將 Django 回傳的 JWT key 綁定到 user 物件上
            user.backendToken = response.data.key;
            return true;
          } catch (error) {
            console.error("後端 Google Auth 換照失敗:", error);
            return false;
          }
        }
        return true;
      },
      // 將 backendToken 轉存至 JWT token
      async jwt({ token, user }) {
        if (user) {
          token.backendToken = user.backendToken;
        }
        return token;
      },
      // 將 backendToken 傳遞給前端 Client Session
      async session({ session, token }) {
        if (session.user) {
          session.user.backendToken = token.backendToken as string;
        }
        return session;
      },
    },
  };

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };