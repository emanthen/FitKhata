"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { redeemMemberPass } from "@fitkhata/api-client";

import { setCachedPass } from "@/lib/member/pass";

/** One-time redemption of the staff-issued pass link. Caches the secret
 * locally and hands off to /m, which is the page a member actually keeps
 * open/bookmarked — redeeming again on every visit would both hit the
 * network needlessly and defeat the "works offline after login" goal.
 */
export default function RedeemPassPage() {
  const params = useParams<{ token: string }>();
  const router = useRouter();
  const t = useTranslations("member");
  const [error, setError] = useState(false);

  useEffect(() => {
    redeemMemberPass(params.token)
      .then((data) => {
        setCachedPass({
          member_code: data.member_code,
          full_name: data.full_name,
          gym_code: data.gym_code,
          qr_secret_hex: data.qr_secret_hex,
          token: params.token,
        });
        router.replace("/m");
      })
      .catch(() => setError(true));
  }, [params.token, router]);

  if (error) return <p className="text-sm text-red-600">{t("passError")}</p>;
  return <p className="opacity-70">{t("passLoading")}</p>;
}
