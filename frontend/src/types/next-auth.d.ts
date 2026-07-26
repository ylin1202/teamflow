import NextAuth, { DefaultSession, DefaultUser } from "next-auth";
import { JWT } from "next-auth/jwt";

declare module "next-auth" {
  /**
   * 擴充 session.user 裡面的型別定義
   */
  interface Session {
    user: {
      backendToken?: string;
    } & DefaultSession["user"];
  }

  /**
   * 擴充 signIn/callbacks 時 user 物件的型別定義
   */
  interface User extends DefaultUser {
    backendToken?: string;
  }
}

declare module "next-auth/jwt" {
  /**
   * 擴充 NextAuth JWT token 物件的型別定義
   */
  interface JWT {
    backendToken?: string;
  }
}