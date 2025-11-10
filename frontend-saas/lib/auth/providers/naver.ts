import type { OAuthConfig, OAuthUserConfig } from "next-auth/providers"

export interface NaverProfile extends Record<string, any> {
  resultcode: string
  message: string
  response: {
    id: string
    email?: string
    name?: string
    profile_image?: string
  }
}

export default function Naver<P extends NaverProfile>(
  options: OAuthUserConfig<P>
): OAuthConfig<P> {
  return {
    id: "naver",
    name: "Naver",
    type: "oauth",
    authorization: {
      url: "https://nid.naver.com/oauth2.0/authorize",
      params: { scope: "name email" },
    },
    token: "https://nid.naver.com/oauth2.0/token",
    userinfo: "https://openapi.naver.com/v1/nid/me",
    profile(profile) {
      return {
        id: profile.response.id,
        name: profile.response.name,
        email: profile.response.email,
        image: profile.response.profile_image,
      }
    },
    options,
  }
}
