import { createBrowserClient, createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/*
 * Read-only Supabase clients for the dashboard. Anon key only — the dashboard
 * never writes; service-role credentials must never reach this layer.
 */

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) {
    throw new Error(`Missing ${name}. See web/.env.local.example.`);
  }
  return v;
}

export function getSupabaseUrl(): string {
  return requireEnv("NEXT_PUBLIC_SUPABASE_URL");
}

export function getSupabaseAnonKey(): string {
  return requireEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY");
}

export async function createServerSupabase() {
  const cookieStore = await cookies();
  return createServerClient(getSupabaseUrl(), getSupabaseAnonKey(), {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll() {
        // Read-only dashboard — no auth flow yet, nothing to write back.
      },
    },
  });
}

export function createClientSupabase() {
  return createBrowserClient(getSupabaseUrl(), getSupabaseAnonKey());
}
