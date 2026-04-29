"use server";

import { revalidatePath } from "next/cache";
import { setPrimaryVariant, type Variant } from "./lessons";

export async function setPrimaryVariantAction(
  slug: string,
  variant: Variant,
): Promise<{ ok: true }> {
  await setPrimaryVariant(slug, variant);
  revalidatePath("/");
  revalidatePath(`/lessons/${slug}`);
  return { ok: true };
}
