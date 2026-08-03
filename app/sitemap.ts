import { MetadataRoute } from 'next'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = 'https://diamond-education.uz';
  const routes: MetadataRoute.Sitemap = [
    {
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: 'yearly',
      priority: 1,
    },
    {
      url: `${baseUrl}/about`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/courses`,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 0.9,
    },
    {
      url: `${baseUrl}/videos`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.8,
    },
    {
      url: `${baseUrl}/results`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.8,
    },
  ];

  try {
    const apiBase = process.env.BACKEND_INTERNAL_URL || 'http://127.0.0.1:3001';
    
    // Videolarni olish
    try {
      const vRes = await fetch(`${apiBase}/public/videos?limit=1000`, { next: { revalidate: 3600 } });
      if (vRes.ok) {
        const vData = await vRes.json();
        if (vData?.items && Array.isArray(vData.items)) {
          vData.items.forEach((v: any) => {
            if (v.id) {
              routes.push({
                url: `${baseUrl}/videos/${v.id}`,
                lastModified: new Date(),
                changeFrequency: 'monthly',
                priority: 0.7,
              });
            }
          });
        }
      }
    } catch (err) {
      console.warn("Sitemap: Videolarni yuklab bo'lmadi", err);
    }

    // Natijalarni olish
    try {
      const rRes = await fetch(`${apiBase}/public/results?limit=1000`, { next: { revalidate: 3600 } });
      if (rRes.ok) {
        const rData = await rRes.json();
        if (rData?.items && Array.isArray(rData.items)) {
          rData.items.forEach((r: any) => {
            if (r.id) {
              routes.push({
                url: `${baseUrl}/results/${r.id}`,
                lastModified: new Date(),
                changeFrequency: 'monthly',
                priority: 0.6,
              });
            }
          });
        }
      }
    } catch (err) {
      console.warn("Sitemap: Natijalarni yuklab bo'lmadi", err);
    }
  } catch (err) {
    //
  }

  return routes;
}
