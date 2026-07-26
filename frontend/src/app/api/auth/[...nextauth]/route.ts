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
          // 傳送 account.access_token 給 Django 進行 Google 驗證
          const response = await axios.post(
            `${BACKEND_URL}/api/auth/google/`,
            {
              access_token: account.access_token,
            }
          );
    
          // 儲存 Django 核發的 JWT Key
          user.backendToken = response.data.key;
          return true;
        } catch (error: any) {
          if (error.response) {
            console.error("Django Auth 錯誤細節:", error.response.data);
          } else {
            console.error("後端 Google Auth 換照失敗:", error.message);
          }
          return false;
        }
      }
      return true;
    },
    async jwt({ token, user }) {
      if (user) {
        token.backendToken = user.backendToken;
      }
      return token;
    },
    async session({ session, token }) {
      session.backendToken = token.backendToken;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
};

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };