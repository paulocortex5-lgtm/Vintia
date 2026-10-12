import type { MetadataRoute } from "next";

import { baseUrl } from "@/lib/settings";

// robots.txt: the public surface is crawlable, the hidden /admin panel is
// explicitly disallowed (it is also noindexed per-page and absent from the
// sitemap — three independent layers, tests enforce the first two).
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: "/admin",
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
