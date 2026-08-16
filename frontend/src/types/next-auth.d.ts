import NextAuth, { DefaultSession, DefaultUser } from "next-auth";
import { JWT } from "next-auth/jwt";

declare module "next-auth" {
  /**
   * Extends the shape of `session.user`
   */
  interface Session {
    user: {
      backendToken?: string;
    } & DefaultSession["user"];
  }

  /**
   * Extends the shape of `user` in signIn/callbacks
   */
  interface User extends DefaultUser {
    backendToken?: string;
  }
}

declare module "next-auth/jwt" {
  /**
   * Extends the shape of NextAuth JWT token
   */
  interface JWT {
    backendToken?: string;
  }
}