import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/** Web container health: 200 when Next.js is serving and (if configured) the API reports its database ready. */
export async function GET() {
  const internal = (process.env.API_INTERNAL_URL || "").replace(/\/$/, "");
  if (!internal) {
    return NextResponse.json({ status: "ok", web: "ok" }, { headers: { "Cache-Control": "no-store" } });
  }
  let api = "unreachable";
  try {
    const response = await fetch(`${internal}/api/v1/ready`, { cache: "no-store", signal: AbortSignal.timeout(3000) });
    api = response.ok ? "ok" : "not_ready";
  } catch {
    api = "unreachable";
  }
  const ok = api === "ok";
  return NextResponse.json(
    { status: ok ? "ok" : "degraded", web: "ok", api },
    { status: ok ? 200 : 503, headers: { "Cache-Control": "no-store" } },
  );
}
