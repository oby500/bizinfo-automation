import type { OAuthConfig, OAuthUserConfig } from "next-auth/providers"

export interface KakaoProfile extends Record<string, any> {
  id: number
  kakao_account: {
    profile: {
      nickname: string
      profile_image_url?: string
    }
    email?: string
  }
}

export default function Kakao<P extends KakaoProfile>(
  options: OAuthUserConfig<P>
): OAuthConfig<P> {
  return {
    id: "kakao",
    name: "Kakao",
    type: "oauth",
    authorization: {
      url: "https://kauth.kakao.com/oauth/authorize",
      params: { scope: "account_email profile_nickname" },
    },
    token: "https://kauth.kakao.com/oauth/token",
    userinfo: "https://kapi.kakao.com/v2/user/me",
    profile(profile) {
      return {
        id: profile.id.toString(),
        name: profile.kakao_account?.profile?.nickname,
        email: profile.kakao_account?.email,
        image: profile.kakao_account?.profile?.profile_image_url,
      }
    },
    options,
  }
}
