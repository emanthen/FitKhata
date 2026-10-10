"use client";

import { useQuery } from "@tanstack/react-query";
import { getMySubscription } from "@fitkhata/api-client";

/** Pure resolution — mirrors saas.services.has_feature's own "undeclared
 * keys are open by default" fallback, and covers the subscription query
 * still being in flight (features undefined). Kept separate from the hook
 * below so it's testable without a QueryClientProvider (see
 * lib/use-feature.test.ts).
 */
export function resolveFeature(features: Record<string, boolean> | undefined, key: string): boolean {
  return features?.[key] ?? true;
}

/** FR-11.2. */
export function useFeature(key: string): boolean {
  const { data } = useQuery({
    queryKey: ["saas", "subscription"],
    queryFn: getMySubscription,
  });
  return resolveFeature(data?.features, key);
}

export function useSubscription() {
  return useQuery({ queryKey: ["saas", "subscription"], queryFn: getMySubscription });
}
