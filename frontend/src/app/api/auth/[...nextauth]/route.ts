import NextAuth, { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import axios from "axios";

// Extend NextAuth built-in types so TypeScript recognizes backendToken
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

// For server-side communication within containers, prioritize http://web:8000 to avoid localhost connection issues
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

          // Bind the JWT key returned from Django to the user object
          user.backendToken = response.data.key;
          return true;
        } catch (error) {
          console.error("Backend Google Auth token exchange failed:", error);
          return false;
        }
      }
      return true;
    },
    // Persist backendToken into the JWT token
    async jwt({ token, user }) {
      if (user) {
        token.backendToken = user.backendToken;
      }
      return token;
    },
    // Pass backendToken to the client session
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